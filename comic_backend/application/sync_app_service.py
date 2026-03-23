import hashlib
import json
import os
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from core.constants import (
    ACTOR_JSON_FILE,
    AUTHOR_JSON_FILE,
    CACHE_ROOT_DIR,
    COMIC_DIR,
    COVER_DIR,
    DATA_DIR,
    JSON_FILE,
    LISTS_JSON_FILE,
    META_DIR,
    RECOMMENDATION_CACHE_DIR,
    RECOMMENDATION_JSON_FILE,
    TAGS_JSON_FILE,
    USER_CONFIG_JSON_FILE,
    VIDEO_DIR,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.isoformat()


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


class SyncAppService:
    SESSION_TTL_HOURS = 24
    SCHEMA_VERSION = 1
    SESSION_STORE_FILE = os.path.join(META_DIR, "sync_sessions.json")
    EXPORT_ROOT_DIR = os.path.join(CACHE_ROOT_DIR, "sync_exports")
    MEDIA_DIRS_PER_CHUNK = 20

    _STORE_LOCK = threading.Lock()

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(self.SESSION_STORE_FILE), exist_ok=True)
        os.makedirs(self.EXPORT_ROOT_DIR, exist_ok=True)

    def create_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._STORE_LOCK:
            state = self._load_store()
            self._cleanup_expired(state)

            session_id = uuid.uuid4().hex
            created_at = _utc_now()
            expires_at = created_at + timedelta(hours=self.SESSION_TTL_HOURS)
            snapshot_generated_at = _utc_now()

            export_dir = self._session_export_dir(session_id)
            os.makedirs(export_dir, exist_ok=True)
            package_options = self._resolve_package_options(payload)
            client_media_dirs = self._extract_client_media_dirs(payload)
            packages = self._build_packages(
                session_id=session_id,
                export_dir=export_dir,
                client_media_dirs=client_media_dirs,
                options=package_options,
            )

            session = {
                "session_id": session_id,
                "schema_version": self.SCHEMA_VERSION,
                "status": "open",
                "created_at": _to_iso(created_at),
                "expires_at": _to_iso(expires_at),
                "snapshot_version": _to_iso(created_at),
                "snapshot_generated_at": _to_iso(snapshot_generated_at),
                "server_data_root_fingerprint": self._server_data_root_fingerprint(),
                "storage_roots": self._storage_roots(),
                "client": {
                    "device_id": str(payload.get("device_id", "")).strip(),
                    "client_version": str(payload.get("client_version", "")).strip(),
                    "platform": str(payload.get("platform", "")).strip(),
                },
                "packages": packages,
                "result": None,
                "exports_cleaned": False,
                "exports_cleaned_at": "",
                "exports_cleanup_error": "",
            }

            state["sessions"][session_id] = session
            self._save_store(state)
            return session

    def get_manifest(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._STORE_LOCK:
            state = self._load_store()
            session = self._get_open_or_finished_session(state, session_id)
            if not session:
                return None
            return {
                "session_id": session["session_id"],
                "schema_version": session.get("schema_version", self.SCHEMA_VERSION),
                "status": session.get("status", "open"),
                "created_at": session.get("created_at"),
                "expires_at": session.get("expires_at"),
                "snapshot_version": session.get("snapshot_version", ""),
                "snapshot_generated_at": session.get("snapshot_generated_at", ""),
                "server_data_root_fingerprint": session.get("server_data_root_fingerprint", ""),
                "storage_roots": session.get("storage_roots", {}),
                "packages": session.get("packages", []),
            }

    def resolve_package(self, session_id: str, package_name: str) -> Optional[Dict[str, Any]]:
        with self._STORE_LOCK:
            state = self._load_store()
            session = self._get_open_or_finished_session(state, session_id)
            if not session:
                return None

            normalized_name = str(package_name or "").strip()
            if not normalized_name:
                return None

            packages = session.get("packages", [])
            for item in packages:
                package_id = str(item.get("id", "")).strip()
                package_file = str(item.get("file", item.get("name", ""))).strip()
                package_alias = str(item.get("name", "")).strip()
                if normalized_name not in (package_id, package_file, package_alias):
                    continue

                resolved_file = package_file or package_alias
                if not resolved_file:
                    return None

                package_path = self._session_export_file(session_id, resolved_file)
                if not os.path.isfile(package_path):
                    return None

                return {
                    "session_id": session_id,
                    "id": package_id,
                    "name": resolved_file,
                    "path": package_path,
                    "kind": item.get("type", item.get("kind", "")),
                    "size_bytes": item.get("size_bytes", item.get("size", 0)),
                    "sha256": item.get("sha256", ""),
                }
            return None

    def finish_session(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            return None

        with self._STORE_LOCK:
            state = self._load_store()
            session = state["sessions"].get(session_id)
            if not session:
                return None

            status = str(payload.get("status", "completed")).strip().lower()
            if status not in {"completed", "failed", "cancelled"}:
                status = "completed"

            finished_at = _to_iso(_utc_now())
            failed_packages = payload.get("failed_packages", [])
            if not isinstance(failed_packages, list):
                failed_packages = []

            session["status"] = status
            session["result"] = {
                "finished_at": finished_at,
                "failed_packages": failed_packages,
                "error": str(payload.get("error", "")).strip(),
            }

            cleanup_result = self._cleanup_session_exports(session_id)
            session["exports_cleaned"] = bool(cleanup_result.get("cleaned", False))
            session["exports_cleaned_at"] = finished_at if session["exports_cleaned"] else ""
            session["exports_cleanup_error"] = str(cleanup_result.get("error", "")).strip()
            for item in session.get("packages", []):
                if isinstance(item, dict):
                    item["available"] = False

            state["sessions"][session_id] = session
            self._save_store(state)
            return {
                "session_id": session_id,
                "status": status,
                "finished_at": finished_at,
                "failed_packages": failed_packages,
                "exports_cleaned": session["exports_cleaned"],
                "exports_cleanup_error": session["exports_cleanup_error"],
            }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._STORE_LOCK:
            state = self._load_store()
            session = self._get_open_or_finished_session(state, session_id)
            if not session:
                return None
            return session

    def _load_store(self) -> Dict[str, Any]:
        if not os.path.exists(self.SESSION_STORE_FILE):
            return {"schema_version": self.SCHEMA_VERSION, "sessions": {}}

        try:
            with open(self.SESSION_STORE_FILE, "r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            sessions = loaded.get("sessions", {})
            if not isinstance(sessions, dict):
                sessions = {}
            return {
                "schema_version": int(loaded.get("schema_version", self.SCHEMA_VERSION)),
                "sessions": sessions,
            }
        except Exception:
            return {"schema_version": self.SCHEMA_VERSION, "sessions": {}}

    def _save_store(self, state: Dict[str, Any]) -> None:
        with open(self.SESSION_STORE_FILE, "w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=2)

    def _cleanup_expired(self, state: Dict[str, Any]) -> None:
        now = _utc_now()
        sessions = state.get("sessions", {})
        to_delete: List[str] = []
        for session_id, session in sessions.items():
            expires_at = _parse_iso(str(session.get("expires_at", "")))
            if expires_at and expires_at < now:
                to_delete.append(session_id)

        for session_id in to_delete:
            sessions.pop(session_id, None)
            export_dir = self._session_export_dir(session_id)
            if os.path.isdir(export_dir):
                shutil.rmtree(export_dir, ignore_errors=True)

        state["sessions"] = sessions

    def _get_open_or_finished_session(self, state: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        self._cleanup_expired(state)
        session = state["sessions"].get(session_id)
        if not session:
            return None
        return session

    def _session_export_dir(self, session_id: str) -> str:
        return os.path.join(self.EXPORT_ROOT_DIR, session_id)

    def _session_export_file(self, session_id: str, filename: str) -> str:
        return os.path.join(self._session_export_dir(session_id), filename)

    def _resolve_package_options(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        default_layers = {"media", "cache", "cover", "meta"}
        layers_value = payload.get("layers", [])
        resolved_layers = set(default_layers)
        if isinstance(layers_value, list) and layers_value:
            candidate_layers = {str(item or "").strip().lower() for item in layers_value}
            resolved_layers = {item for item in candidate_layers if item in default_layers}
            if not resolved_layers:
                resolved_layers = set(default_layers)

        def _bool_value(key: str, default: bool = True) -> bool:
            value = payload.get(key, None)
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

        chunk_size = payload.get("media_chunk_size", self.MEDIA_DIRS_PER_CHUNK)
        try:
            chunk_size = int(chunk_size)
        except Exception:
            chunk_size = self.MEDIA_DIRS_PER_CHUNK
        chunk_size = max(1, min(chunk_size, 200))

        return {
            "include_media": "media" in resolved_layers and _bool_value("include_media", True),
            "include_cache": "cache" in resolved_layers and _bool_value("include_cache", True),
            "include_cover": "cover" in resolved_layers and _bool_value("include_cover", True),
            "include_meta": "meta" in resolved_layers and _bool_value("include_meta", True),
            "media_chunk_size": chunk_size,
        }

    def _extract_client_media_dirs(self, payload: Dict[str, Any]) -> Set[str]:
        candidates: List[Any] = []
        candidates.append(payload.get("client_media_dirs", []))
        candidates.append(payload.get("known_media_dirs", []))

        client_inventory = payload.get("client_inventory", {})
        if isinstance(client_inventory, dict):
            candidates.append(client_inventory.get("media_dirs", []))

        inventory = payload.get("inventory", {})
        if isinstance(inventory, dict):
            candidates.append(inventory.get("media_dirs", []))

        result: Set[str] = set()
        for item in candidates:
            if not isinstance(item, list):
                if isinstance(item, dict):
                    iterable = list(item.keys())
                else:
                    continue
            else:
                iterable = item

            for path_value in iterable:
                normalized = self._normalize_data_relative_path(path_value)
                if normalized:
                    result.add(normalized)
        return result

    def _build_packages(
        self,
        session_id: str,
        export_dir: str,
        client_media_dirs: Set[str],
        options: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        packages: List[Dict[str, Any]] = []

        include_meta = bool(options.get("include_meta", True))
        include_media = bool(options.get("include_media", True))
        include_cache = bool(options.get("include_cache", True))
        include_cover = bool(options.get("include_cover", True))
        media_chunk_size = int(options.get("media_chunk_size", self.MEDIA_DIRS_PER_CHUNK) or self.MEDIA_DIRS_PER_CHUNK)

        if include_media:
            server_media_dirs = self._collect_media_content_dirs()
            if client_media_dirs:
                missing_media_dirs = [item for item in server_media_dirs if item not in client_media_dirs]
            else:
                missing_media_dirs = list(server_media_dirs)

            for idx, chunk_dirs in enumerate(self._chunk_list(missing_media_dirs, media_chunk_size), start=1):
                media_files = self._collect_files_for_relative_dirs(chunk_dirs)
                if not media_files:
                    continue
                package_file = f"media_chunk_{idx:04d}.zip"
                package_id = f"media_chunk_{idx:04d}"
                packages.append(
                    self._build_package_descriptor(
                        session_id=session_id,
                        export_dir=export_dir,
                        package_id=package_id,
                        package_type="media",
                        package_file=package_file,
                        source_paths=media_files,
                        priority=10 + idx,
                        source_dirs=len(chunk_dirs),
                    )
                )

        if include_cache:
            cache_files = self._collect_files_from_roots(
                [RECOMMENDATION_CACHE_DIR, CACHE_ROOT_DIR],
                exclude_relative_prefixes=[
                    "cache/sync_exports",
                    "cache/sync_assets",
                ],
            )
            if cache_files:
                packages.append(
                    self._build_package_descriptor(
                        session_id=session_id,
                        export_dir=export_dir,
                        package_id="cache",
                        package_type="cache",
                        package_file="cache.zip",
                        source_paths=cache_files,
                        priority=60,
                    )
                )

        if include_cover:
            cover_files = self._collect_files_from_roots([COVER_DIR])
            if cover_files:
                packages.append(
                    self._build_package_descriptor(
                        session_id=session_id,
                        export_dir=export_dir,
                        package_id="cover",
                        package_type="cover",
                        package_file="cover.zip",
                        source_paths=cover_files,
                        priority=80,
                    )
                )

        if include_meta:
            meta_sources = [
                JSON_FILE,
                RECOMMENDATION_JSON_FILE,
                VIDEO_JSON_FILE,
                VIDEO_RECOMMENDATION_JSON_FILE,
                TAGS_JSON_FILE,
                LISTS_JSON_FILE,
                USER_CONFIG_JSON_FILE,
                ACTOR_JSON_FILE,
                AUTHOR_JSON_FILE,
            ]
            meta_files = [path for path in meta_sources if os.path.isfile(path)]
            packages.append(
                self._build_package_descriptor(
                    session_id=session_id,
                    export_dir=export_dir,
                    package_id="meta",
                    package_type="meta",
                    package_file="meta.zip",
                    source_paths=meta_files,
                    priority=100,
                    allow_empty=True,
                )
            )

        packages.sort(key=lambda item: (int(item.get("priority", 9999)), str(item.get("name", ""))))
        return packages

    def _build_package_descriptor(
        self,
        session_id: str,
        export_dir: str,
        package_id: str,
        package_type: str,
        package_file: str,
        source_paths: List[str],
        priority: int,
        source_dirs: int = 0,
        allow_empty: bool = False,
    ) -> Dict[str, Any]:
        package_path = os.path.join(export_dir, package_file)
        unique_paths = self._dedup_paths(source_paths)
        if unique_paths or allow_empty:
            self._create_zip(package_path, unique_paths)

        size_bytes = os.path.getsize(package_path) if os.path.isfile(package_path) else 0
        checksum = self._sha256_file(package_path) if os.path.isfile(package_path) else ""
        source_count = len(unique_paths)
        return {
            "id": package_id,
            "name": package_file,
            "file": package_file,
            "kind": package_type,
            "type": package_type,
            "size": size_bytes,
            "size_bytes": size_bytes,
            "sha256": checksum,
            "priority": int(priority),
            "download_path": f"/api/v1/sync/download/{session_id}/{package_file}",
            "source_count": source_count,
            "source_dirs": int(source_dirs),
            "available": True,
        }

    def _collect_media_content_dirs(self) -> List[str]:
        rel_dirs: Set[str] = set()
        for root_dir in (COMIC_DIR, VIDEO_DIR):
            for platform_dir in self._list_subdirs(root_dir):
                for content_dir in self._list_subdirs(platform_dir):
                    if not self._dir_has_any_file(content_dir):
                        continue
                    rel_path = self._relative_to_data_dir(content_dir)
                    if rel_path:
                        rel_dirs.add(rel_path)
        return sorted(rel_dirs)

    @staticmethod
    def _list_subdirs(root_dir: str) -> List[str]:
        if not os.path.isdir(root_dir):
            return []
        result: List[str] = []
        for name in sorted(os.listdir(root_dir)):
            abs_path = os.path.join(root_dir, name)
            if os.path.isdir(abs_path):
                result.append(abs_path)
        return result

    @staticmethod
    def _dir_has_any_file(root_dir: str) -> bool:
        if not os.path.isdir(root_dir):
            return False
        for _, _, files in os.walk(root_dir):
            if files:
                return True
        return False

    def _collect_files_for_relative_dirs(self, relative_dirs: List[str]) -> List[str]:
        collected: List[str] = []
        data_root = os.path.abspath(DATA_DIR)
        for rel_dir in relative_dirs:
            normalized = self._normalize_data_relative_path(rel_dir)
            if not normalized:
                continue
            target_dir = os.path.abspath(os.path.join(data_root, normalized.replace("/", os.sep)))
            try:
                if os.path.commonpath([data_root, target_dir]) != data_root:
                    continue
            except Exception:
                continue
            if not os.path.isdir(target_dir):
                continue

            for current, _, files in os.walk(target_dir):
                for name in sorted(files):
                    abs_path = os.path.join(current, name)
                    if os.path.isfile(abs_path):
                        collected.append(abs_path)
        return self._dedup_paths(collected)

    def _collect_files_from_roots(
        self,
        roots: List[str],
        exclude_relative_prefixes: Optional[List[str]] = None,
    ) -> List[str]:
        exclude = set()
        for item in exclude_relative_prefixes or []:
            normalized = self._normalize_data_relative_path(item)
            if normalized:
                exclude.add(normalized)

        collected: Dict[str, str] = {}
        for root_dir in roots:
            if not os.path.isdir(root_dir):
                continue
            for current, _, files in os.walk(root_dir):
                for name in sorted(files):
                    abs_path = os.path.join(current, name)
                    if not os.path.isfile(abs_path):
                        continue
                    rel_path = self._relative_to_data_dir(abs_path)
                    if not rel_path:
                        continue
                    if self._is_excluded_rel_path(rel_path, exclude):
                        continue
                    collected[rel_path] = abs_path
        return [collected[key] for key in sorted(collected.keys())]

    @staticmethod
    def _is_excluded_rel_path(rel_path: str, excludes: Set[str]) -> bool:
        if not rel_path:
            return True
        for prefix in excludes:
            if rel_path == prefix or rel_path.startswith(f"{prefix}/"):
                return True
        return False

    @staticmethod
    def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
        if chunk_size <= 0:
            chunk_size = 1
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def _cleanup_session_exports(self, session_id: str) -> Dict[str, Any]:
        export_dir = self._session_export_dir(session_id)
        if not os.path.isdir(export_dir):
            return {"cleaned": True, "removed_files": 0, "error": ""}

        removed_files = 0
        for _, _, files in os.walk(export_dir):
            removed_files += len(files)

        try:
            shutil.rmtree(export_dir, ignore_errors=False)
            return {
                "cleaned": not os.path.exists(export_dir),
                "removed_files": removed_files,
                "error": "",
            }
        except Exception as exc:
            return {"cleaned": False, "removed_files": removed_files, "error": str(exc)}

    def _server_data_root_fingerprint(self) -> str:
        sha = hashlib.sha256()
        roots = self._storage_roots()
        for key in sorted(roots.keys()):
            value = str(roots.get(key, "")).strip()
            sha.update(f"{key}:{value}".encode("utf-8", errors="ignore"))
            try:
                mtime = int(os.path.getmtime(value)) if value and os.path.exists(value) else 0
            except Exception:
                mtime = 0
            sha.update(f"@{mtime}".encode("utf-8", errors="ignore"))
        return f"sha256:{sha.hexdigest()}"

    @staticmethod
    def _storage_roots() -> Dict[str, str]:
        return {
            "data_root": os.path.abspath(DATA_DIR),
            "meta_root": os.path.abspath(META_DIR),
            "pictures_root": os.path.abspath(COMIC_DIR),
            "video_root": os.path.abspath(VIDEO_DIR),
            "cover_root": os.path.abspath(COVER_DIR),
            "cache_root": os.path.abspath(CACHE_ROOT_DIR),
            "recommendation_cache_root": os.path.abspath(RECOMMENDATION_CACHE_DIR),
        }

    @staticmethod
    def _dedup_paths(file_paths: List[str]) -> List[str]:
        unique: Dict[str, str] = {}
        for path in file_paths:
            abs_path = os.path.abspath(path)
            unique[abs_path] = abs_path
        return [unique[key] for key in sorted(unique.keys())]

    @staticmethod
    def _normalize_data_relative_path(path_value: Any) -> str:
        raw = str(path_value or "").strip()
        if not raw:
            return ""

        normalized = raw.replace("\\", "/").strip()
        if os.path.isabs(normalized):
            abs_path = os.path.abspath(normalized)
            data_root = os.path.abspath(DATA_DIR)
            try:
                if os.path.commonpath([data_root, abs_path]) != data_root:
                    return ""
            except Exception:
                return ""
            relative = os.path.relpath(abs_path, data_root).replace("\\", "/")
            return relative.strip("/").strip()

        normalized = normalized.lstrip("/").lstrip("./")
        parts = [item for item in normalized.split("/") if item and item not in {".", ".."}]
        if not parts:
            return ""
        lowered = [item.lower() for item in parts]
        if "data" in lowered:
            idx = lowered.index("data")
            parts = parts[idx + 1:]
        return "/".join(parts).strip("/")

    @staticmethod
    def _relative_to_data_dir(path_value: str) -> str:
        abs_path = os.path.abspath(str(path_value or ""))
        data_root = os.path.abspath(DATA_DIR)
        try:
            if os.path.commonpath([data_root, abs_path]) != data_root:
                return ""
        except Exception:
            return ""
        rel = os.path.relpath(abs_path, data_root).replace("\\", "/").strip("/")
        return rel

    @staticmethod
    def _create_zip(target_zip: str, file_paths: List[str]) -> None:
        os.makedirs(os.path.dirname(target_zip), exist_ok=True)
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path in file_paths:
                if not os.path.isfile(abs_path):
                    continue
                arcname = SyncAppService._relative_to_data_dir(abs_path)
                if not arcname:
                    arcname = os.path.basename(abs_path)
                zf.write(abs_path, arcname=arcname)

    @staticmethod
    def _sha256_file(path: str) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as fp:
            while True:
                chunk = fp.read(1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()
