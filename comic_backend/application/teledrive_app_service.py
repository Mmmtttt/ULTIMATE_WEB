from __future__ import annotations

import os
import posixpath
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlencode

import requests

from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE, VIDEO_RECOMMENDATION_JSON_FILE
from core.utils import get_current_time, get_preview_pages
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories import JsonDocumentRepository
from protocol.base import ProtocolProvider
from protocol.runtime_config import ProtocolConfigStore


TELEDRIVE_CONFIG_KEY = "teledrive"
DEFAULT_BRIDGE_BASE_URL = "http://127.0.0.1:8892"
DEFAULT_LIMIT = 100
DEFAULT_TIMEOUT_SECONDS = 30
TOKEN_MASK_VALUES = {"", "********", "******", "__KEEP__"}
TELEDRIVE_PLUGIN_ID = "storage.teledrive"
TELEDRIVE_PLUGIN_NAME = "TeleDrive"
TELEDRIVE_PLATFORM = "TeleDrive"
TELEDRIVE_COMIC_ROOT = "/comic"
TELEDRIVE_VIDEO_ROOT = "/video"
TELEDRIVE_COMIC_ID_PREFIX = "TD-COMIC-"
TELEDRIVE_VIDEO_ID_PREFIX = "TD-VIDEO-"
TELEDRIVE_STORAGE_KIND_DIR = "teledrive_dir"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi", ".ts", ".m3u8"}
COVER_FILENAMES = {"cover.jpg"}
KNOWN_PLATFORM_SEGMENTS = {
    "JM",
    "JMCOMIC",
    "JMC",
    "EH",
    "EX",
    "EXHENTAI",
    "NH",
    "NHENTAI",
    "HITOMI",
    "PIXIV",
    "MISSAV",
    "JABLE",
}


class TeleDriveBridgeError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int = 502,
        response_data: Optional[Any] = None,
    ):
        super().__init__(message)
        self.status_code = int(status_code or 502)
        self.response_data = response_data


@dataclass(frozen=True)
class TeleDriveConfig:
    enabled: bool = True
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    api_token: str = ""
    default_limit: int = DEFAULT_LIMIT
    convert_photos: bool = True
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @property
    def configured(self) -> bool:
        return bool(self.bridge_base_url)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "bridge_base_url": self.bridge_base_url,
            "default_limit": self.default_limit,
            "convert_photos": self.convert_photos,
            "timeout_seconds": self.timeout_seconds,
            "api_token_configured": bool(self.api_token),
        }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, default: int, minimum: int = 1, maximum: int = 10000) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _normalize_tree_path(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.rstrip("/") if normalized != "/" else "/"


def _path_segments_under(path: str, root: str) -> List[str]:
    normalized_path = _normalize_tree_path(path)
    normalized_root = _normalize_tree_path(root)
    if normalized_path == normalized_root:
        return []
    prefix = f"{normalized_root}/"
    if not normalized_path.startswith(prefix):
        return []
    return [segment for segment in normalized_path[len(prefix):].split("/") if segment]


def _file_extension(name: str) -> str:
    return os.path.splitext(str(name or "").strip().lower())[1]


def _is_supported_image(item: Dict[str, Any]) -> bool:
    mime_type = str(item.get("mime_type") or "").lower()
    category = str(item.get("category") or "").lower()
    return (
        category == "image"
        or mime_type.startswith("image/")
        or _file_extension(item.get("name", "")) in SUPPORTED_IMAGE_EXTENSIONS
    )


def _is_supported_video(item: Dict[str, Any]) -> bool:
    mime_type = str(item.get("mime_type") or "").lower()
    category = str(item.get("category") or "").lower()
    return (
        category == "video"
        or mime_type.startswith("video/")
        or _file_extension(item.get("name", "")) in SUPPORTED_VIDEO_EXTENSIONS
    )


def _natural_key(value: str) -> List[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(value or ""))]


def _is_known_platform_segment(segment: str) -> bool:
    normalized = re.sub(r"[^A-Za-z0-9]", "", str(segment or "").upper())
    return normalized in KNOWN_PLATFORM_SEGMENTS


def _safe_item_id(prefix: str, item_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", str(item_id or "").strip()).strip("-")
    return f"{prefix}{normalized}" if normalized else ""


def _teledrive_media_url(file_id: str, name: str) -> str:
    if not file_id:
        return ""
    query = urlencode({"name": str(name or "")})
    return f"/api/v1/teledrive/files/{quote(str(file_id), safe='')}/content?{query}"


def normalize_teledrive_config(payload: Dict[str, Any], *, keep_empty_token: bool = False) -> Dict[str, Any]:
    raw = dict(payload or {})
    normalized: Dict[str, Any] = {
        "enabled": _as_bool(raw.get("enabled"), True),
        "bridge_base_url": str(raw.get("bridge_base_url") or DEFAULT_BRIDGE_BASE_URL).strip().rstrip("/"),
        "default_limit": _as_int(raw.get("default_limit"), DEFAULT_LIMIT, minimum=1, maximum=10000),
        "convert_photos": _as_bool(raw.get("convert_photos"), True),
        "timeout_seconds": _as_int(raw.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, minimum=1, maximum=600),
    }

    token_value = raw.get("api_token")
    token = str(token_value or "").strip()
    if token or keep_empty_token:
        normalized["api_token"] = token
    if token in TOKEN_MASK_VALUES:
        normalized.pop("api_token", None)
    return normalized


class TeleDriveProtocolProvider(ProtocolProvider):
    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_teledrive_config(payload)

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_teledrive_config(config, keep_empty_token=True)
        public = dict(normalized)
        public.pop("api_token", None)
        public["api_token_configured"] = bool(str((config or {}).get("api_token") or "").strip())
        return public

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_teledrive_config(config, keep_empty_token=True)
        enabled = _as_bool(normalized.get("enabled"), True)
        configured = bool(str(normalized.get("bridge_base_url") or "").strip())
        return {
            "configured": bool(enabled and configured),
            "message": "" if enabled and configured else "TeleDrive Bridge is disabled or not configured.",
            "missing_fields": [] if configured else ["bridge_base_url"],
        }

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        raise RuntimeError(f"TeleDrive provider does not implement protocol capability: {capability}")


class TeleDriveAppService:
    STREAM_REQUEST_HEADERS = (
        "Range",
        "If-Range",
        "If-None-Match",
        "If-Modified-Since",
        "User-Agent",
        "Accept",
    )
    STREAM_RESPONSE_HEADERS = (
        "Accept-Ranges",
        "Cache-Control",
        "Content-Disposition",
        "Content-Length",
        "Content-Range",
        "Content-Type",
        "ETag",
        "Last-Modified",
    )

    def __init__(self, config_store: Optional[ProtocolConfigStore] = None, http_client=None):
        self._config_store = config_store or ProtocolConfigStore()
        self._http_client = http_client or requests

    def get_config(self, reload: bool = True) -> TeleDriveConfig:
        raw_config = self._config_store.get_plugin_config(TELEDRIVE_CONFIG_KEY, reload=reload)
        normalized = normalize_teledrive_config(raw_config, keep_empty_token=True)
        return TeleDriveConfig(
            enabled=bool(normalized.get("enabled", True)),
            bridge_base_url=str(normalized.get("bridge_base_url") or DEFAULT_BRIDGE_BASE_URL).strip().rstrip("/"),
            api_token=str(normalized.get("api_token") or "").strip(),
            default_limit=int(normalized.get("default_limit") or DEFAULT_LIMIT),
            convert_photos=bool(normalized.get("convert_photos", True)),
            timeout_seconds=int(normalized.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
        )

    @staticmethod
    def public_config(config: TeleDriveConfig) -> Dict[str, Any]:
        return config.public_dict()

    def build_headers(self, config: Optional[TeleDriveConfig] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        resolved = config or self.get_config()
        headers = dict(extra or {})
        if resolved.api_token:
            headers["Authorization"] = f"Bearer {resolved.api_token}"
        return headers

    def _ensure_ready(self, config: TeleDriveConfig) -> None:
        if not config.enabled:
            raise TeleDriveBridgeError("TeleDrive Bridge is disabled.", status_code=400)
        if not config.configured:
            raise TeleDriveBridgeError("TeleDrive Bridge base URL is not configured.", status_code=400)

    def _url(self, config: TeleDriveConfig, path: str, query_string: str = "") -> str:
        normalized_path = "/" + str(path or "").lstrip("/")
        url = f"{config.bridge_base_url}{normalized_path}"
        if query_string:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query_string}"
        return url

    @staticmethod
    def _parse_json_response(response) -> Any:
        if not getattr(response, "content", b""):
            return None
        try:
            return response.json()
        except Exception:
            text = getattr(response, "text", "")
            return {"raw": text} if text else None

    @staticmethod
    def _extract_error_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            if isinstance(payload.get("error"), dict):
                return str(payload["error"].get("message") or payload["error"].get("code") or fallback)
            if payload.get("error"):
                return str(payload.get("error"))
            if payload.get("message"):
                return str(payload.get("message"))
        return fallback

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        config: Optional[TeleDriveConfig] = None,
        timeout: Optional[Any] = None,
    ) -> Any:
        resolved = config or self.get_config()
        self._ensure_ready(resolved)
        headers = self.build_headers(resolved)
        if json_payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"

        try:
            response = self._http_client.request(
                method=method.upper(),
                url=self._url(resolved, path),
                params=params,
                json=json_payload,
                headers=headers,
                timeout=timeout if timeout is not None else resolved.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise TeleDriveBridgeError(f"TeleDrive Bridge request failed: {exc}", status_code=502) from exc

        payload = self._parse_json_response(response)
        if response.status_code >= 400:
            message = self._extract_error_message(payload, f"TeleDrive Bridge returned HTTP {response.status_code}")
            raise TeleDriveBridgeError(message, status_code=response.status_code, response_data=payload)
        return payload

    def get_status(self) -> Dict[str, Any]:
        config = self.get_config()
        data: Dict[str, Any] = {
            "enabled": config.enabled,
            "configured": bool(config.enabled and config.configured),
            "config": self.public_config(config),
            "bridge_health": None,
            "latest_import": None,
        }

        if not config.enabled or not config.configured:
            return data

        try:
            data["bridge_health"] = self._request_json("GET", "/health", config=config)
        except TeleDriveBridgeError as exc:
            data["bridge_health"] = {
                "ok": False,
                "error": str(exc),
                "status_code": exc.status_code,
            }
            data["error"] = str(exc)
            return data

        try:
            data["latest_import"] = self._request_json("GET", "/v1/imports/latest", config=config)
        except TeleDriveBridgeError as exc:
            data["latest_import"] = {
                "ok": False,
                "error": str(exc),
                "status_code": exc.status_code,
            }

        return data

    def import_once(self, payload: Dict[str, Any], *, dry_run: bool) -> Any:
        config = self.get_config()
        limit = _as_int((payload or {}).get("limit"), config.default_limit, minimum=1, maximum=10000)
        request_payload = {
            "limit": limit,
            "convert_photos": _as_bool((payload or {}).get("convert_photos"), config.convert_photos),
            "dry_run": bool(dry_run),
        }
        for optional_key in ("source_id", "user_id", "channel_id"):
            if optional_key in (payload or {}) and (payload or {}).get(optional_key) not in ("", None):
                request_payload[optional_key] = (payload or {}).get(optional_key)
        return self._request_json(
            "POST",
            "/v1/imports",
            json_payload=request_payload,
            config=config,
            timeout=(config.timeout_seconds, None),
        )

    def get_catalog(self, args: Dict[str, Any]) -> Any:
        config = self.get_config()
        params = dict(args or {})
        if not str(params.get("limit") or "").strip():
            params["limit"] = config.default_limit
        return self._request_json("GET", "/v1/catalog/items", params=params, config=config)

    def get_tree(self, root: str, *, limit: int = 10000) -> Dict[str, Any]:
        config = self.get_config()
        params = {
            "root": _normalize_tree_path(root),
            "limit": max(1, min(int(limit or 10000), 50000)),
        }
        data = self._request_json("GET", "/v1/tree", params=params, config=config)
        return data if isinstance(data, dict) else {"root": params["root"], "items": []}

    def sync_library(self, payload: Dict[str, Any], *, dry_run: bool) -> Dict[str, Any]:
        limit = _as_int((payload or {}).get("limit"), 10000, minimum=1, maximum=50000)
        scan = self._scan_library(limit=limit)
        result = {
            "dry_run": bool(dry_run),
            "roots": [TELEDRIVE_COMIC_ROOT, TELEDRIVE_VIDEO_ROOT],
            "comics": [self._summarize_library_item(item) for item in scan["comics"]],
            "videos": [self._summarize_library_item(item) for item in scan["videos"]],
            "skipped": scan["skipped"],
            "stats": {
                "recognized_comics": len(scan["comics"]),
                "recognized_videos": len(scan["videos"]),
                "skipped": len(scan["skipped"]),
            },
        }
        if dry_run:
            return result

        apply_stats = self._apply_library_scan(scan)
        result["stats"].update(apply_stats)
        return result

    @staticmethod
    def _summarize_library_item(item: Dict[str, Any]) -> Dict[str, Any]:
        summary = dict(item or {})
        display = summary.get("display") if isinstance(summary.get("display"), dict) else {}
        teledrive = dict(display.get("teledrive") or {}) if isinstance(display.get("teledrive"), dict) else {}
        if isinstance(teledrive.get("pages"), list):
            teledrive["page_count"] = len(teledrive.get("pages") or [])
            teledrive.pop("pages", None)
        if isinstance(teledrive.get("episodes"), list):
            teledrive["episode_count"] = len(teledrive.get("episodes") or [])
            teledrive.pop("episodes", None)
        summary["display"] = {**display, "teledrive": teledrive}
        return summary

    def _load_tree_items(self, root: str, *, limit: int) -> List[Dict[str, Any]]:
        tree = self.get_tree(root, limit=limit)
        items = tree.get("items", []) if isinstance(tree, dict) else []
        return [dict(item or {}) for item in items if isinstance(item, dict)]

    def _scan_library(self, *, limit: int) -> Dict[str, Any]:
        skipped: List[Dict[str, Any]] = []
        comic_items = self._load_tree_items(TELEDRIVE_COMIC_ROOT, limit=limit)
        video_items = self._load_tree_items(TELEDRIVE_VIDEO_ROOT, limit=limit)
        comics = self._recognize_comics(comic_items, skipped)
        videos = self._recognize_videos(video_items, skipped)
        return {
            "comics": comics,
            "videos": videos,
            "skipped": skipped,
        }

    @staticmethod
    def _index_folders(items: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        by_path: Dict[str, Dict[str, Any]] = {}
        by_id: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if str(item.get("type") or "").lower() != "folder":
                continue
            item_path = _normalize_tree_path(item.get("path", ""))
            if item_path:
                by_path[item_path] = item
            item_id = str(item.get("id") or "").strip()
            if item_id:
                by_id[item_id] = item
        return by_path, by_id

    @staticmethod
    def _item_relative_path(item: Dict[str, Any], base_path: str) -> str:
        normalized_path = _normalize_tree_path(item.get("path", ""))
        normalized_base = _normalize_tree_path(base_path)
        if normalized_path == normalized_base:
            return str(item.get("name") or "")
        prefix = f"{normalized_base}/"
        if normalized_path.startswith(prefix):
            return normalized_path[len(prefix):]
        return str(item.get("name") or "")

    def _recognize_comics(self, items: List[Dict[str, Any]], skipped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        folders_by_path, _folders_by_id = self._index_folders(items)
        groups: Dict[str, Dict[str, Any]] = {}
        direct_children = {
            path: folder
            for path, folder in folders_by_path.items()
            if len(_path_segments_under(path, TELEDRIVE_COMIC_ROOT)) == 1
        }

        for item in items:
            if str(item.get("type") or "").lower() != "file":
                continue
            path = _normalize_tree_path(item.get("path", ""))
            segments = _path_segments_under(path, TELEDRIVE_COMIC_ROOT)
            if len(segments) < 2:
                skipped.append({"path": path, "reason": "comic_file_not_under_work_dir"})
                continue
            if not _is_supported_image(item):
                skipped.append({"path": path, "reason": "unsupported_comic_file"})
                continue

            first = segments[0]
            use_platform = (
                len(segments) >= 3
                and _is_known_platform_segment(first)
                and _normalize_tree_path(posixpath.join(TELEDRIVE_COMIC_ROOT, first)) in direct_children
            )
            if use_platform:
                platform_segment = first
                work_id = segments[1]
                work_path = _normalize_tree_path(posixpath.join(TELEDRIVE_COMIC_ROOT, platform_segment, work_id))
            else:
                platform_segment = ""
                work_id = first
                work_path = _normalize_tree_path(posixpath.join(TELEDRIVE_COMIC_ROOT, work_id))

            work_folder = folders_by_path.get(work_path)
            if not work_folder:
                skipped.append({"path": path, "reason": "comic_work_folder_missing"})
                continue

            group = groups.setdefault(
                work_path,
                {
                    "folder": work_folder,
                    "work_id": work_id,
                    "platform_segment": platform_segment,
                    "pages": [],
                },
            )
            group["pages"].append(item)

        recognized: List[Dict[str, Any]] = []
        for work_path, group in sorted(groups.items(), key=lambda entry: _natural_key(entry[0])):
            folder = group["folder"]
            folder_id = str(folder.get("id") or "").strip()
            record_id = _safe_item_id(TELEDRIVE_COMIC_ID_PREFIX, folder_id)
            if not record_id:
                skipped.append({"path": work_path, "reason": "comic_folder_id_missing"})
                continue

            pages = sorted(
                group["pages"],
                key=lambda item: _natural_key(self._item_relative_path(item, work_path)),
            )
            page_payloads = [
                self._serialize_tree_file(page, base_path=work_path)
                for page in pages
            ]
            title = str(group["work_id"] or folder.get("name") or record_id).strip()
            preview_pages = get_preview_pages(len(page_payloads))
            recognized.append(
                {
                    "id": record_id,
                    "title": title,
                    "title_jp": "",
                    "author": str(group["platform_segment"] or "").strip(),
                    "desc": f"TeleDrive: {work_path}",
                    "cover_path": f"/api/v1/comic/image?comic_id={quote(record_id, safe='')}&page_num=1",
                    "total_page": len(page_payloads),
                    "current_page": 1,
                    "score": 8.0,
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": get_current_time(),
                    "last_read_time": get_current_time(),
                    "is_deleted": False,
                    "preview_image_urls": [
                        f"/api/v1/comic/image?comic_id={quote(record_id, safe='')}&page_num={page}"
                        for page in preview_pages
                    ],
                    "preview_pages": preview_pages,
                    "platform": TELEDRIVE_PLATFORM,
                    "plugin_id": TELEDRIVE_PLUGIN_ID,
                    "plugin_name": TELEDRIVE_PLUGIN_NAME,
                    "storage_path_relative": f"teledrive://folder/{folder_id}",
                    "storage_path_kind": TELEDRIVE_STORAGE_KIND_DIR,
                    "display": {
                        "teledrive": {
                            "type": "comic",
                            "root": TELEDRIVE_COMIC_ROOT,
                            "path": work_path,
                            "folder_id": folder_id,
                            "work_id": str(group["work_id"] or ""),
                            "platform_segment": str(group["platform_segment"] or ""),
                            "pages": page_payloads,
                        }
                    },
                    "source_missing": False,
                }
            )
        return recognized

    def _recognize_videos(self, items: List[Dict[str, Any]], skipped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        folders_by_path, _folders_by_id = self._index_folders(items)
        groups: Dict[str, Dict[str, Any]] = {}
        direct_children = {
            path: folder
            for path, folder in folders_by_path.items()
            if len(_path_segments_under(path, TELEDRIVE_VIDEO_ROOT)) == 1
        }

        for item in items:
            if str(item.get("type") or "").lower() != "file":
                continue
            path = _normalize_tree_path(item.get("path", ""))
            segments = _path_segments_under(path, TELEDRIVE_VIDEO_ROOT)
            if len(segments) < 2:
                skipped.append({"path": path, "reason": "video_file_not_under_work_dir"})
                continue

            first = segments[0]
            use_platform = (
                len(segments) >= 3
                and _is_known_platform_segment(first)
                and _normalize_tree_path(posixpath.join(TELEDRIVE_VIDEO_ROOT, first)) in direct_children
            )
            if use_platform:
                platform_segment = first
                work_id = segments[1]
                work_path = _normalize_tree_path(posixpath.join(TELEDRIVE_VIDEO_ROOT, platform_segment, work_id))
            else:
                platform_segment = ""
                work_id = first
                work_path = _normalize_tree_path(posixpath.join(TELEDRIVE_VIDEO_ROOT, work_id))

            work_folder = folders_by_path.get(work_path)
            if not work_folder:
                skipped.append({"path": path, "reason": "video_work_folder_missing"})
                continue

            group = groups.setdefault(
                work_path,
                {
                    "folder": work_folder,
                    "work_id": work_id,
                    "platform_segment": platform_segment,
                    "videos": [],
                    "covers": [],
                    "thumbnails": [],
                    "skipped": [],
                },
            )
            filename = str(item.get("name") or "")
            if _is_supported_video(item):
                group["videos"].append(item)
            elif filename.lower() in COVER_FILENAMES and _is_supported_image(item):
                group["covers"].append(item)
            elif self._is_video_thumbnail_item(item, work_path):
                group["thumbnails"].append(item)
            else:
                group["skipped"].append(item)

        recognized: List[Dict[str, Any]] = []
        for work_path, group in sorted(groups.items(), key=lambda entry: _natural_key(entry[0])):
            if not group["videos"]:
                for skipped_item in group["skipped"]:
                    skipped.append({"path": _normalize_tree_path(skipped_item.get("path", "")), "reason": "unsupported_video_sidecar"})
                skipped.append({"path": work_path, "reason": "video_work_has_no_video_file"})
                continue

            folder = group["folder"]
            folder_id = str(folder.get("id") or "").strip()
            record_id = _safe_item_id(TELEDRIVE_VIDEO_ID_PREFIX, folder_id)
            if not record_id:
                skipped.append({"path": work_path, "reason": "video_folder_id_missing"})
                continue

            videos = sorted(
                group["videos"],
                key=lambda item: _natural_key(self._item_relative_path(item, work_path)),
            )
            covers = sorted(
                group["covers"],
                key=lambda item: _natural_key(self._item_relative_path(item, work_path)),
            )
            thumbnails = sorted(
                group["thumbnails"],
                key=lambda item: _natural_key(self._item_relative_path(item, work_path)),
            )
            episodes = [self._serialize_tree_file(item, base_path=work_path) for item in videos]
            cover = self._serialize_tree_file(covers[0], base_path=work_path) if covers else {}
            thumbnail_files = [self._serialize_tree_file(item, base_path=work_path) for item in thumbnails]
            first_episode = episodes[0]
            cover_url = _teledrive_media_url(cover.get("file_id", ""), cover.get("name", "")) if cover else ""
            thumbnail_urls = [
                _teledrive_media_url(item.get("file_id", ""), item.get("name", ""))
                for item in thumbnail_files
                if item.get("file_id")
            ]
            preview_video = _teledrive_media_url(first_episode.get("file_id", ""), first_episode.get("name", ""))
            title = str(group["work_id"] or folder.get("name") or record_id).strip()
            recognized.append(
                {
                    "id": record_id,
                    "title": title,
                    "title_jp": "",
                    "creator": str(group["platform_segment"] or "").strip(),
                    "desc": f"TeleDrive: {work_path}",
                    "cover_path": cover_url,
                    "total_units": len(episodes),
                    "current_unit": 1,
                    "score": 8.0,
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": get_current_time(),
                    "last_access_time": get_current_time(),
                    "is_deleted": False,
                    "platform": TELEDRIVE_PLATFORM,
                    "plugin_id": TELEDRIVE_PLUGIN_ID,
                    "plugin_name": TELEDRIVE_PLUGIN_NAME,
                    "storage_path_relative": f"teledrive://folder/{folder_id}",
                    "storage_path_kind": TELEDRIVE_STORAGE_KIND_DIR,
                    "code": str(group["work_id"] or ""),
                    "date": "",
                    "series": str(group["platform_segment"] or ""),
                    "magnets": [],
                    "thumbnail_images": thumbnail_urls,
                    "preview_video": preview_video,
                    "cover_path_local": "",
                    "thumbnail_images_local": [],
                    "preview_video_local": "",
                    "actor_refs": [],
                    "actors": [],
                    "display": {
                        "teledrive": {
                            "type": "video",
                            "root": TELEDRIVE_VIDEO_ROOT,
                            "path": work_path,
                            "folder_id": folder_id,
                            "work_id": str(group["work_id"] or ""),
                            "platform_segment": str(group["platform_segment"] or ""),
                            "episodes": episodes,
                            "cover": cover,
                            "thumbnails": thumbnail_files,
                        }
                    },
                    "source_missing": False,
                }
            )
        return recognized

    @staticmethod
    def _is_video_thumbnail_item(item: Dict[str, Any], work_path: str) -> bool:
        if not _is_supported_image(item):
            return False
        relative_path = TeleDriveAppService._item_relative_path(item, work_path)
        segments = [segment for segment in str(relative_path or "").replace("\\", "/").split("/") if segment]
        return len(segments) >= 2 and segments[0].lower() == "thumbs"

    @staticmethod
    def _serialize_tree_file(item: Dict[str, Any], *, base_path: str) -> Dict[str, Any]:
        relative_path = TeleDriveAppService._item_relative_path(item, base_path)
        return {
            "file_id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "path": _normalize_tree_path(item.get("path", "")),
            "relative_path": relative_path,
            "mime_type": str(item.get("mime_type") or ""),
            "category": str(item.get("category") or ""),
            "size": int(item.get("size") or 0),
            "updated_at": str(item.get("updated_at") or ""),
        }

    def _apply_library_scan(self, scan: Dict[str, Any]) -> Dict[str, int]:
        comic_stats = self._merge_items_into_document(
            RECOMMENDATION_JSON_FILE,
            "recommendations",
            "total_recommendations",
            scan.get("comics", []),
            source_type="comic",
        )
        video_stats = self._merge_items_into_document(
            VIDEO_RECOMMENDATION_JSON_FILE,
            "video_recommendations",
            "total_video_recommendations",
            scan.get("videos", []),
            source_type="video",
        )
        return {
            "comic_added": comic_stats["added"],
            "comic_updated": comic_stats["updated"],
            "comic_unchanged": comic_stats["unchanged"],
            "comic_missing_marked": comic_stats["missing_marked"],
            "video_added": video_stats["added"],
            "video_updated": video_stats["updated"],
            "video_unchanged": video_stats["unchanged"],
            "video_missing_marked": video_stats["missing_marked"],
        }

    def _merge_items_into_document(
        self,
        file_path: str,
        root_key: str,
        count_key: str,
        new_items: List[Dict[str, Any]],
        *,
        source_type: str,
    ) -> Dict[str, int]:
        repo = JsonDocumentRepository(file_path, root_key, count_key)
        added = updated = unchanged = missing_marked = 0
        seen_ids = {str(item.get("id") or "") for item in new_items if str(item.get("id") or "")}

        def update_items(existing_items: List[dict]) -> List[dict]:
            nonlocal added, updated, unchanged, missing_marked
            items = [dict(item or {}) for item in existing_items if isinstance(item, dict)]
            index = {str(item.get("id") or ""): item for item in items if str(item.get("id") or "")}
            for new_item in new_items:
                item_id = str(new_item.get("id") or "")
                if not item_id:
                    continue
                if item_id not in index:
                    items.append(dict(new_item))
                    index[item_id] = items[-1]
                    added += 1
                    continue
                merged = self._merge_teledrive_record(index[item_id], new_item, source_type=source_type)
                if merged != index[item_id]:
                    index[item_id].clear()
                    index[item_id].update(merged)
                    updated += 1
                else:
                    unchanged += 1

            for item in items:
                if str(item.get("plugin_id") or "") != TELEDRIVE_PLUGIN_ID:
                    continue
                display = item.get("display") if isinstance(item.get("display"), dict) else {}
                teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
                if str(teledrive.get("type") or "") != source_type:
                    continue
                item_id = str(item.get("id") or "")
                if item_id and item_id not in seen_ids and not bool(item.get("source_missing")):
                    item["source_missing"] = True
                    item["source_missing_time"] = get_current_time()
                    missing_marked += 1
            return items

        repo.update_items(update_items)
        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "missing_marked": missing_marked,
        }

    @staticmethod
    def _merge_teledrive_record(existing: Dict[str, Any], new_item: Dict[str, Any], *, source_type: str) -> Dict[str, Any]:
        merged = dict(existing or {})
        user_preserved_keys = {
            "title",
            "title_jp",
            "author",
            "creator",
            "desc",
            "score",
            "tag_ids",
            "list_ids",
            "current_page",
            "current_unit",
            "last_read_time",
            "last_access_time",
            "is_deleted",
            "date",
            "series",
            "actors",
            "actor_refs",
            "magnets",
        }
        for key, value in new_item.items():
            if key in user_preserved_keys and merged.get(key) not in (None, "", [], {}):
                continue
            merged[key] = value

        # These fields are derived from the current TeleDrive directory snapshot and
        # must follow user file moves/renames.
        system_keys = {
            "cover_path",
            "total_page",
            "total_units",
            "preview_image_urls",
            "preview_pages",
            "thumbnail_images",
            "preview_video",
            "display",
            "storage_path_relative",
            "storage_path_kind",
            "platform",
            "plugin_id",
            "plugin_name",
            "source_missing",
        }
        for key in system_keys:
            if key in new_item:
                merged[key] = new_item[key]

        if source_type == "comic":
            total_page = int(new_item.get("total_page") or 0)
            current_page = int(merged.get("current_page") or 1)
            merged["current_page"] = max(1, min(current_page, total_page or current_page))
        elif source_type == "video":
            total_units = int(new_item.get("total_units") or 0)
            current_unit = int(merged.get("current_unit") or 1)
            merged["current_unit"] = max(1, min(current_unit, total_units or current_unit))
        return merged

    def get_teledrive_comic_pages(
        self,
        comic_id: str,
        *,
        include_recommendation: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        record = self._find_teledrive_comic_record(
            comic_id,
            include_recommendation=include_recommendation,
        )
        if not record:
            return None
        display = record.get("display") if isinstance(record.get("display"), dict) else {}
        teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
        pages = teledrive.get("pages") if isinstance(teledrive.get("pages"), list) else []
        return [dict(page or {}) for page in pages if isinstance(page, dict)]

    def proxy_teledrive_comic_page(
        self,
        comic_id: str,
        page_num: int,
        *,
        method: str = "GET",
        incoming_headers: Optional[Dict[str, Any]] = None,
    ):
        pages = self.get_teledrive_comic_pages(comic_id)
        if pages is None:
            raise TeleDriveBridgeError("Not a TeleDrive comic.", status_code=404)
        if page_num < 1 or page_num > len(pages):
            raise TeleDriveBridgeError("TeleDrive comic page out of range.", status_code=404)
        page = pages[page_num - 1]
        file_id = str(page.get("file_id") or "").strip()
        name = str(page.get("name") or "").strip()
        if not file_id:
            raise TeleDriveBridgeError("TeleDrive comic page has no file id.", status_code=404)
        return self.proxy_file_content(
            file_id,
            method=method,
            query_string=urlencode({"name": name}) if name else "",
            incoming_headers=incoming_headers,
        )

    @staticmethod
    def _find_teledrive_comic_record(
        comic_id: str,
        *,
        include_recommendation: bool = True,
    ) -> Optional[Dict[str, Any]]:
        normalized_id = str(comic_id or "").strip()
        if not normalized_id:
            return None
        sources = [(JSON_FILE, "comics")]
        if include_recommendation:
            sources.append((RECOMMENDATION_JSON_FILE, "recommendations"))
        for file_path, root_key in sources:
            try:
                repo = JsonDocumentRepository(file_path, root_key)
                for item in repo.read_items():
                    if str(item.get("id") or "").strip() != normalized_id:
                        continue
                    if str(item.get("plugin_id") or "") == TELEDRIVE_PLUGIN_ID:
                        display = item.get("display") if isinstance(item.get("display"), dict) else {}
                        teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
                        if str(teledrive.get("type") or "") == "comic":
                            return dict(item)
                    if file_path == JSON_FILE and not include_recommendation:
                        return None
            except Exception:
                continue
        return None

    @classmethod
    def filter_headers(cls, source_headers: Dict[str, Any], names: Iterable[str]) -> Dict[str, str]:
        filtered: Dict[str, str] = {}
        for name in names:
            try:
                value = source_headers.get(name)
            except Exception:
                value = None
            if value not in (None, ""):
                filtered[name] = str(value)
        return filtered

    def proxy_file_content(
        self,
        file_id: str,
        *,
        method: str,
        query_string: str = "",
        incoming_headers: Optional[Dict[str, Any]] = None,
    ):
        config = self.get_config()
        self._ensure_ready(config)
        normalized_file_id = quote(str(file_id or "").strip(), safe="")
        if not normalized_file_id:
            raise TeleDriveBridgeError("Missing file_id.", status_code=400)

        request_headers = self.filter_headers(dict(incoming_headers or {}), self.STREAM_REQUEST_HEADERS)
        headers = self.build_headers(config, request_headers)
        url = self._url(config, f"/v1/files/{normalized_file_id}/content", query_string=query_string)
        try:
            return self._http_client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                stream=True,
                timeout=(config.timeout_seconds, None),
            )
        except requests.RequestException as exc:
            raise TeleDriveBridgeError(f"TeleDrive Bridge stream failed: {exc}", status_code=502) from exc

    def download_file_to_path(self, file_id: str, target_path: str, *, name: str = "") -> Dict[str, Any]:
        normalized_target = os.path.abspath(str(target_path or "").strip())
        if not normalized_target:
            raise TeleDriveBridgeError("Missing target path.", status_code=400)

        upstream = self.proxy_file_content(
            file_id,
            method="GET",
            query_string=urlencode({"name": str(name or "")}) if name else "",
            incoming_headers=None,
        )
        tmp_path = f"{normalized_target}.tmp"
        written = 0
        try:
            status_code = int(getattr(upstream, "status_code", 200) or 200)
            if status_code >= 400:
                raise TeleDriveBridgeError(
                    f"TeleDrive Bridge returned HTTP {status_code}",
                    status_code=status_code,
                )

            os.makedirs(os.path.dirname(normalized_target) or ".", exist_ok=True)
            with open(tmp_path, "wb") as file_obj:
                for chunk in upstream.iter_content(chunk_size=1024 * 512):
                    if not chunk:
                        continue
                    file_obj.write(chunk)
                    written += len(chunk)
            os.replace(tmp_path, normalized_target)
            return {
                "path": normalized_target,
                "bytes": written,
                "content_type": str(getattr(upstream, "headers", {}).get("Content-Type") or ""),
            }
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise
        finally:
            self.close_response(upstream)

    @staticmethod
    def close_response(response) -> None:
        try:
            response.close()
        except Exception:
            pass


def get_teledrive_app_service() -> TeleDriveAppService:
    return TeleDriveAppService()
