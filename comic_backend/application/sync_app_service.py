import hashlib
import json
import os
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.constants import (
    ACTOR_JSON_FILE,
    AUTHOR_JSON_FILE,
    CACHE_ROOT_DIR,
    JSON_FILE,
    LISTS_JSON_FILE,
    META_DIR,
    RECOMMENDATION_JSON_FILE,
    TAGS_JSON_FILE,
    USER_CONFIG_JSON_FILE,
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

            export_dir = self._session_export_dir(session_id)
            os.makedirs(export_dir, exist_ok=True)
            packages = self._build_packages(session_id, export_dir)

            session = {
                "session_id": session_id,
                "schema_version": self.SCHEMA_VERSION,
                "status": "open",
                "created_at": _to_iso(created_at),
                "expires_at": _to_iso(expires_at),
                "client": {
                    "device_id": str(payload.get("device_id", "")).strip(),
                    "client_version": str(payload.get("client_version", "")).strip(),
                    "platform": str(payload.get("platform", "")).strip(),
                },
                "packages": packages,
                "result": None,
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
                "packages": session.get("packages", []),
            }

    def resolve_package(self, session_id: str, package_name: str) -> Optional[Dict[str, Any]]:
        with self._STORE_LOCK:
            state = self._load_store()
            session = self._get_open_or_finished_session(state, session_id)
            if not session:
                return None

            packages = session.get("packages", [])
            for item in packages:
                if item.get("name") == package_name:
                    package_path = self._session_export_file(session_id, package_name)
                    if not os.path.isfile(package_path):
                        return None
                    return {
                        "session_id": session_id,
                        "name": package_name,
                        "path": package_path,
                        "size_bytes": item.get("size_bytes", 0),
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
            state["sessions"][session_id] = session
            self._save_store(state)
            return {
                "session_id": session_id,
                "status": status,
                "finished_at": finished_at,
                "failed_packages": failed_packages,
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

    def _build_packages(self, session_id: str, export_dir: str) -> List[Dict[str, Any]]:
        package_name = "meta_data.zip"
        package_path = os.path.join(export_dir, package_name)
        sources = [
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
        existing_files = [path for path in sources if os.path.isfile(path)]
        self._create_zip(package_path, existing_files)
        size_bytes = os.path.getsize(package_path) if os.path.isfile(package_path) else 0
        checksum = self._sha256_file(package_path) if os.path.isfile(package_path) else ""

        return [
            {
                "name": package_name,
                "kind": "meta_data",
                "size_bytes": size_bytes,
                "sha256": checksum,
                "download_path": f"/api/v1/sync/download/{session_id}/{package_name}",
                "source_count": len(existing_files),
            }
        ]

    @staticmethod
    def _create_zip(target_zip: str, file_paths: List[str]) -> None:
        os.makedirs(os.path.dirname(target_zip), exist_ok=True)
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path in file_paths:
                if not os.path.isfile(abs_path):
                    continue
                arcname = os.path.relpath(abs_path, META_DIR).replace("\\", "/")
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
