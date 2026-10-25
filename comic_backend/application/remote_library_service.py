"""引用式入库：把声明了 library.sync.* 的插件扫出来的内容并进预览库。

为什么落点是预览库，不是本地库——

    本地库的语义是「条目背后有一个能打开的本地文件」：Video 实体的字段是
    local_video_path / local_source_path / source_origin，全是本地路径。
    而「不下载、只引用」的内容，这个项目里本来就有落点：预览库
    （RECOMMENDATION_JSON_FILE / VIDEO_RECOMMENDATION_JSON_FILE）。
    TeleDrive 那个名叫 library-sync 的接口，写进去的也是这两个文件。

    所以本模块只做一件事：把插件的扫描结果规范化成预览库记录，
    字节一律不搬——播放时按 file id 现取。

记录里的远程信息存在 display.remote，与 display.teledrive 平行。
读取侧（recommendation_app_service / video_app_service）需要同时认这两个键。
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from core.constants import RECOMMENDATION_JSON_FILE, VIDEO_RECOMMENDATION_JSON_FILE
from core.utils import get_current_time
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories import JsonDocumentRepository
from protocol.gateway import get_protocol_gateway
from protocol.provider_manager import get_provider_manager

# 与 display.teledrive 平行：远程来源的规范化载荷
REMOTE_DISPLAY_KEY = "remote"

# 漫画暂时只解析、不写库：
# 预览库的漫画记录一旦带上远程载荷，阅读器会走「远程取页」那条链路，
# 而那条链路目前只有 TeleDrive 的桥实现。先写进去只会得到「能看见、点开报错」，
# 比不写更糟。等远程取页通道接上再打开这个开关。
COMIC_SYNC_ENABLED = False

SYNC_PREVIEW_CAPABILITY = "library.sync.preview"
SYNC_APPLY_CAPABILITY = "library.sync.apply"

VIDEO_PROXY_PATH = "/api/v1/video/proxy2"
COMIC_PROXY_PATH = "/api/v1/video/proxy2"


def _proxied(url: str) -> str:
    """把插件给的占位地址包成宿主代理地址，浏览器才拿得到字节。"""
    target = str(url or "").strip()
    if not target:
        return ""
    if target.startswith("/"):
        return target
    encoded = base64.b64encode(target.encode("utf-8")).decode("ascii")
    return f"{VIDEO_PROXY_PATH}?url={encoded}"


def _first_episode_url(item: Dict[str, Any]) -> str:
    episodes = item.get("episodes") or []
    for episode in episodes:
        if isinstance(episode, dict) and str(episode.get("stream_url") or "").strip():
            return str(episode["stream_url"])
    return ""


def _cover_url(item: Dict[str, Any]) -> str:
    cover = item.get("cover")
    if isinstance(cover, dict):
        # 优先用服务端缩略图（视频自带封面），没有再退回流地址
        thumb = str(cover.get("thumbnail") or "").strip()
        if thumb:
            return _proxied(thumb)
        target = str(cover.get("stream_url") or "").strip()
        if target:
            return _proxied(target)
    return ""


def _page_urls(item: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for page in item.get("pages") or []:
        if isinstance(page, dict) and str(page.get("stream_url") or "").strip():
            urls.append(_proxied(str(page["stream_url"])))
    return urls


class RemoteLibraryService:
    """按能力找插件、扫内容、写预览库。对具体平台一无所知。"""

    # ---------- 发现 ----------

    @staticmethod
    def list_sync_plugins() -> List[Dict[str, Any]]:
        gateway = get_protocol_gateway()
        manifests = list(
            gateway.list_manifests(capability=SYNC_APPLY_CAPABILITY)
        )
        plugins: List[Dict[str, Any]] = []
        for manifest in manifests:
            plugins.append(
                {
                    "plugin_id": manifest.plugin_id,
                    "label": manifest.name,
                    "media_types": manifest.media_types,
                    "capabilities": manifest.capability_keys,
                }
            )
        return plugins

    @staticmethod
    def _ensure_supported(plugin_id: str, capability: str) -> None:
        gateway = get_protocol_gateway()
        manifest = gateway.registry.get_manifest(plugin_id)
        if manifest is None:
            raise RuntimeError(f"没有这个插件：{plugin_id}")
        if not manifest.has_capability(capability):
            raise RuntimeError(f"插件 {plugin_id} 没有声明 {capability} 能力。")

    @staticmethod
    def _call(plugin_id: str, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        RemoteLibraryService._ensure_supported(plugin_id, capability)
        manager = get_provider_manager()
        result = manager.execute(plugin_id, capability, dict(params or {}))
        return dict(result or {}) if isinstance(result, dict) else {}

    # ---------- 规范化 ----------

    @staticmethod
    def _base_record(item: Dict[str, Any], plugin_id: str, label: str, kind: str) -> Dict[str, Any]:
        now = get_current_time()
        folder_id = str(item.get("folder_id") or "")
        path = str(item.get("path") or "")
        record_id = str(item.get("id") or f"{plugin_id}::{folder_id}")
        return {
            "id": record_id,
            "title": str(item.get("title") or folder_id),
            "desc": f"{label}: {path}" if path else label,
            "score": 8.0,
            "tag_ids": [],
            "list_ids": [],
            "is_deleted": False,
            "platform": label,
            "plugin_id": plugin_id,
            "plugin_name": label,
            "source_missing": False,
            "storage_path_relative": f"{plugin_id}://folder/{folder_id}",
            "storage_path_kind": "dir",
            "display": {
                REMOTE_DISPLAY_KEY: {
                    "provider_key": plugin_id,
                    "provider_label": label,
                    "plugin_id": plugin_id,
                    "plugin_name": label,
                    "type": kind,
                    "folder_id": folder_id,
                    "path": path,
                }
            },
            "create_time": now,
        }

    @classmethod
    def to_video_record(cls, item: Dict[str, Any], plugin_id: str, label: str) -> Dict[str, Any]:
        record = cls._base_record(item, plugin_id, label, "video")
        episodes = [dict(entry) for entry in (item.get("episodes") or []) if isinstance(entry, dict)]
        thumbnails = [dict(entry) for entry in (item.get("thumbnails") or []) if isinstance(entry, dict)]
        now = get_current_time()
        record.update(
            {
                "title_jp": "",
                "creator": "",
                "code": "",
                "date": "",
                "series": "",
                "magnets": [],
                "actor_refs": [],
                "actors": [],
                "total_units": len(episodes),
                "current_unit": 1,
                "last_access_time": now,
                "cover_path": _cover_url(item),
                "cover_path_local": "",
                "preview_video": _proxied(_first_episode_url(item)),
                "preview_video_local": "",
                "thumbnail_images": [
                    _proxied(str(entry.get("stream_url") or "")) for entry in thumbnails
                ],
                "thumbnail_images_local": [],
            }
        )
        record["display"][REMOTE_DISPLAY_KEY].update(
            {"episodes": episodes, "cover": item.get("cover") or {}, "thumbnails": thumbnails}
        )
        return record

    @classmethod
    def to_comic_record(cls, item: Dict[str, Any], plugin_id: str, label: str) -> Dict[str, Any]:
        record = cls._base_record(item, plugin_id, label, "comic")
        pages = [dict(entry) for entry in (item.get("pages") or []) if isinstance(entry, dict)]
        page_urls = _page_urls(item)
        now = get_current_time()
        preview_pages = list(range(1, min(len(page_urls), 3) + 1))
        record.update(
            {
                "title_jp": "",
                "author": "",
                "total_page": len(pages),
                "current_page": 1,
                "last_read_time": now,
                "cover_path": _cover_url(item) or (page_urls[0] if page_urls else ""),
                "preview_image_urls": [page_urls[index - 1] for index in preview_pages if index <= len(page_urls)],
                "preview_pages": preview_pages,
            }
        )
        record["display"][REMOTE_DISPLAY_KEY].update({"pages": pages, "cover": item.get("cover") or {}})
        return record

    # ---------- 写库 ----------

    @staticmethod
    def _merge(
        file_path: str,
        root_key: str,
        count_key: str,
        new_items: List[Dict[str, Any]],
        *,
        plugin_id: str,
        kind: str,
    ) -> Dict[str, int]:
        repo = JsonDocumentRepository(file_path, root_key, count_key)
        added = updated = unchanged = missing_marked = 0
        seen = {str(item.get("id") or "") for item in new_items if str(item.get("id") or "")}

        def update_items(existing_items: List[dict]) -> List[dict]:
            nonlocal added, updated, unchanged, missing_marked
            items = [dict(entry or {}) for entry in existing_items if isinstance(entry, dict)]
            index = {str(entry.get("id") or ""): entry for entry in items if str(entry.get("id") or "")}

            for new_item in new_items:
                item_id = str(new_item.get("id") or "")
                if not item_id:
                    continue
                if item_id not in index:
                    items.append(dict(new_item))
                    index[item_id] = items[-1]
                    added += 1
                    continue
                current = index[item_id]
                # 用户改过的字段不让同步覆盖（与 TeleDrive 的合并语义一致）
                preserved = ("title", "score", "tag_ids", "list_ids", "is_deleted", "current_page", "current_unit")
                merged = dict(current)
                for key, value in new_item.items():
                    if key in preserved and current.get(key) not in (None, "", [], {}):
                        continue
                    merged[key] = value
                if merged != current:
                    current.clear()
                    current.update(merged)
                    updated += 1
                else:
                    unchanged += 1

            for entry in items:
                if str(entry.get("plugin_id") or "") != plugin_id:
                    continue
                display = entry.get("display") if isinstance(entry.get("display"), dict) else {}
                remote = display.get(REMOTE_DISPLAY_KEY) if isinstance(display.get(REMOTE_DISPLAY_KEY), dict) else {}
                if str(remote.get("type") or "") != kind:
                    continue
                item_id = str(entry.get("id") or "")
                if item_id and item_id not in seen and not bool(entry.get("source_missing")):
                    entry["source_missing"] = True
                    missing_marked += 1
            return items

        repo.update_items(update_items)
        return {"added": added, "updated": updated, "unchanged": unchanged, "missing_marked": missing_marked}

    # ---------- 对外入口 ----------

    def sync(self, plugin_id: str, *, dry_run: bool) -> Dict[str, Any]:
        capability = SYNC_PREVIEW_CAPABILITY if dry_run else SYNC_APPLY_CAPABILITY
        payload = self._call(plugin_id, capability, {"dry_run": bool(dry_run)})

        gateway = get_protocol_gateway()
        manifest = gateway.registry.get_manifest(plugin_id)
        label = manifest.name if manifest is not None else plugin_id

        items = [entry for entry in (payload.get("items") or []) if isinstance(entry, dict)]
        video_records = [self.to_video_record(item, plugin_id, label) for item in items if item.get("kind") == "video"]
        comic_records = [self.to_comic_record(item, plugin_id, label) for item in items if item.get("kind") == "comic"]

        result: Dict[str, Any] = {
            "dry_run": bool(dry_run),
            "plugin_id": plugin_id,
            "label": label,
            "skipped": payload.get("skipped") or [],
            "stats": {
                "videos": len(video_records),
                "comics": len(comic_records),
                "skipped": len(payload.get("skipped") or []),
            },
        }
        if dry_run:
            result["videos"] = [
                {"id": record["id"], "title": record["title"], "units": record["total_units"]}
                for record in video_records
            ]
            result["comics"] = [
                {"id": record["id"], "title": record["title"], "pages": record["total_page"]}
                for record in comic_records
            ]
            if comic_records and not COMIC_SYNC_ENABLED:
                result["comics_writable"] = False
                result["comics_note"] = "远程取页通道未接通，漫画本次只报告、不写库。"
            return result

        if video_records:
            result["stats"].update(
                self._merge(
                    VIDEO_RECOMMENDATION_JSON_FILE,
                    "video_recommendations",
                    "total_video_recommendations",
                    video_records,
                    plugin_id=plugin_id,
                    kind="video",
                )
            )
        if comic_records and not COMIC_SYNC_ENABLED:
            result["comics_writable"] = False
            result["comics_note"] = "远程取页通道未接通，漫画本次只报告、不写库。"
        elif comic_records:
            result["stats"].update(
                self._merge(
                    RECOMMENDATION_JSON_FILE,
                    "recommendations",
                    "total_recommendations",
                    comic_records,
                    plugin_id=plugin_id,
                    kind="comic",
                )
            )
        app_logger.info("[remote-library] %s -> %s", plugin_id, result["stats"])
        return result


_service: Optional[RemoteLibraryService] = None


def get_remote_library_service() -> RemoteLibraryService:
    global _service
    if _service is None:
        _service = RemoteLibraryService()
    return _service
