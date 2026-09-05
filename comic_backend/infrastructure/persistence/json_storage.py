from __future__ import annotations

import copy
from contextlib import contextmanager
import json
import os
import shutil
import threading
import time
import uuid
from typing import Any, Callable, Dict, Iterable, Optional

from core.constants import BACKUP_SUFFIX
from core.storage_layout import get_meta_dir, get_current_space_mode
from infrastructure.logger import app_logger, error_logger


def _get_file_name_from_path(path: str) -> str:
    """从路径中提取文件名（用于标识同一份逻辑数据在不同空间的对应文件）"""
    return os.path.basename(path)


class JsonStorage:
    _instances: Dict[str, "JsonStorage"] = {}
    _locks: Dict[str, threading.RLock] = {}
    _deferred_index_sync = threading.local()

    def __new__(cls, json_file: str = None, space_mode: str = None):
        if json_file is None:
            file_name = "comics_database.json"
        else:
            file_name = _get_file_name_from_path(json_file)

        instance = cls._instances.get(file_name)
        if instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[file_name] = instance
        return instance

    def __init__(self, json_file: str = None, space_mode: str = None):
        if self._initialized:
            return

        if json_file is None:
            file_name = "comics_database.json"
        else:
            file_name = _get_file_name_from_path(json_file)

        self._file_name = file_name
        self._tmp_prefix = "comic_db_"
        self._tmp_suffix = ".tmp"
        self._tmp_cleanup_max_age_seconds = 600
        self._last_tmp_cleanup_ts_per_space: Dict[str, float] = {}
        self._tmp_cleanup_cooldown_seconds = 60
        self._initialized = True

    def _get_json_file(self) -> str:
        """获取当前空间模式下的实际 JSON 文件路径"""
        return os.path.join(get_meta_dir(), self._file_name)

    def _get_lock(self) -> threading.RLock:
        """获取当前空间对应文件的锁"""
        actual_path = self._get_json_file()
        lock = self._locks.get(actual_path)
        if lock is None:
            lock = threading.RLock()
            self._locks[actual_path] = lock
        return lock

    @property
    def json_file(self) -> str:
        return self._get_json_file()

    @classmethod
    @contextmanager
    def defer_catalog_index_sync(cls):
        stack = getattr(cls._deferred_index_sync, "stack", None)
        if stack is None:
            stack = []
            cls._deferred_index_sync.stack = stack

        pending: Dict[str, Dict[str, object]] = {}
        stack.append(pending)
        try:
            yield
        finally:
            stack.pop()
            if stack:
                parent = stack[-1]
                for file_name, payload in pending.items():
                    current = parent.setdefault(
                        file_name,
                        {
                            "old": payload.get("old"),
                            "old_set": payload.get("old_set", False),
                            "new": payload.get("new"),
                        },
                    )
                    if not current.get("old_set"):
                        current["old"] = payload.get("old")
                        current["old_set"] = payload.get("old_set", False)
                    current["new"] = payload.get("new")
                return

            tag_payload = pending.get("tags_database.json")
            if tag_payload is not None:
                cls._sync_catalog_index_payload("tags_database.json", tag_payload.get("old"), tag_payload.get("new"))
                return

            for file_name, payload in pending.items():
                cls._sync_catalog_index_payload(file_name, payload.get("old"), payload.get("new"))

    def _cleanup_stale_temp_files(self, force: bool = False) -> int:
        try:
            now = time.time()
            json_file = self._get_json_file()
            space_key = get_current_space_mode()

            last_ts = self._last_tmp_cleanup_ts_per_space.get(space_key, 0.0)
            if not force and (now - last_ts) < self._tmp_cleanup_cooldown_seconds:
                return 0
            self._last_tmp_cleanup_ts_per_space[space_key] = now

            dir_path = os.path.dirname(json_file) or "."
            if not os.path.isdir(dir_path):
                return 0

            cleaned = 0
            for entry in os.scandir(dir_path):
                if not entry.is_file():
                    continue
                if not (entry.name.startswith(self._tmp_prefix) and entry.name.endswith(self._tmp_suffix)):
                    continue
                age_seconds = now - entry.stat().st_mtime
                if age_seconds < self._tmp_cleanup_max_age_seconds:
                    continue
                try:
                    os.remove(entry.path)
                    cleaned += 1
                except Exception as e:
                    error_logger.warning(f"清理临时文件失败: {entry.path}, {e}")

            if cleaned:
                app_logger.info(f"已清理残留临时文件: {cleaned} 个, 目录: {dir_path}")
            return cleaned
        except Exception as e:
            error_logger.warning(f"扫描残留临时文件失败: {self._file_name}, {e}")
            return 0

    def _read_unlocked(self) -> dict:
        json_file = self._get_json_file()
        if not os.path.exists(json_file):
            return self._create_empty_data()
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_unlocked(self, data: dict) -> bool:
        self._cleanup_stale_temp_files()
        json_file = self._get_json_file()
        dir_path = os.path.dirname(json_file) or "."
        os.makedirs(dir_path, exist_ok=True)

        backup_file = json_file + BACKUP_SUFFIX
        if os.path.exists(json_file):
            try:
                shutil.copy2(json_file, backup_file)
            except Exception as e:
                error_logger.warning(f"创建备份失败: {e}")

        temp_path = os.path.join(dir_path, f"{self._tmp_prefix}{uuid.uuid4().hex}{self._tmp_suffix}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            last_error = None
            for attempt in range(3):
                try:
                    os.replace(temp_path, json_file)
                    last_error = None
                    break
                except PermissionError as e:
                    last_error = e
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error
            app_logger.info(f"JSON 文件写入成功: {json_file}")
            return True
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as cleanup_err:
                    error_logger.warning(f"清理临时文件失败: {temp_path}, {cleanup_err}")
            raise
        finally:
            self._cleanup_stale_temp_files()

    def read(self) -> dict:
        lock = self._get_lock()
        with lock:
            try:
                data = self._read_unlocked()
                app_logger.info(f"JSON 文件读取成功: {self._get_json_file()}")
                return data
            except json.JSONDecodeError as e:
                error_logger.error(f"JSON 文件损坏: path={self._get_json_file()}, error={e}")
                return self.restore_backup()
            except Exception as e:
                error_logger.error(f"读取 JSON 文件失败: {e}")
                return self._create_empty_data()

    def write(self, data: dict, max_retries: int = 3) -> bool:
        del max_retries
        lock = self._get_lock()
        with lock:
            try:
                payload = dict(data or {})
                written = self._write_unlocked(payload)
                if written:
                    self._sync_catalog_index_after_write(None, payload)
                return written
            except Exception as e:
                error_logger.error(f"写入 JSON 文件失败: {e}")
                return False

    def cleanup_stale_meta_temp_files(self, max_age_seconds: int = 600) -> int:
        try:
            meta_dir_abs = os.path.abspath(get_meta_dir())
            if not os.path.isdir(meta_dir_abs):
                return 0

            now = time.time()
            cleaned = 0
            for entry in os.scandir(meta_dir_abs):
                if not entry.is_file():
                    continue
                if not (entry.name.startswith(self._tmp_prefix) and entry.name.endswith(self._tmp_suffix)):
                    continue
                age_seconds = now - entry.stat().st_mtime
                if age_seconds < max_age_seconds:
                    continue
                try:
                    os.remove(entry.path)
                    cleaned += 1
                except Exception as e:
                    error_logger.warning(f"启动清理临时文件失败: {entry.path}, {e}")

            if cleaned:
                app_logger.info(f"启动清理残留临时文件完成: {cleaned} 个, 目录: {meta_dir_abs}")
            return cleaned
        except Exception as e:
            error_logger.warning(f"启动扫描残留临时文件失败: {e}")
            return 0

    def _create_empty_data(self) -> dict:
        file_name = self._file_name.lower()
        now = time.strftime("%Y-%m-%d")

        if file_name == "user_config.json":
            return {
                "user_config": {
                    "default_page_mode": "up_down",
                    "default_background": "white",
                    "auto_hide_toolbar": True,
                    "show_page_number": True,
                    "single_page_browsing": False,
                    "cache_config": {
                        "recommendation_cache_max_size_mb": 5120,
                        "cache_ttl_seconds": 3600,
                    },
                },
                "last_updated": now,
            }

        if file_name == "tags_database.json":
            return {
                "collection_name": "标签库",
                "user": "用户名",
                "last_updated": now,
                "tags": [],
            }

        if file_name == "lists_database.json":
            return {
                "collection_name": "清单库",
                "user": "用户名",
                "last_updated": now,
                "lists": [],
            }

        if file_name == "reading_history_database.json":
            return {
                "collection_name": "阅读记录",
                "user": "用户名",
                "last_updated": now,
                "history": {
                    "comic": [],
                    "video": [],
                },
            }

        if file_name == "comics_database.json":
            return {
                "collection_name": "我的收藏集",
                "user": "用户名",
                "total_comics": 0,
                "last_updated": now,
                "comics": [],
                "user_config": {
                    "default_page_mode": "up_down",
                    "default_background": "white",
                    "single_page_browsing": False,
                },
            }

        if file_name == "recommendations_database.json":
            return {
                "collection_name": "推荐漫画",
                "user": "用户名",
                "total_recommendations": 0,
                "last_updated": now,
                "recommendations": [],
                "user_config": {
                    "default_page_mode": "up_down",
                    "default_background": "dark",
                    "single_page_browsing": False,
                },
            }

        if file_name == "videos_database.json":
            return {
                "collection_name": "视频库",
                "user": "用户名",
                "total_videos": 0,
                "last_updated": now,
                "videos": [],
            }

        if file_name == "video_recommendations_database.json":
            return {
                "collection_name": "推荐视频",
                "user": "用户名",
                "total_video_recommendations": 0,
                "last_updated": now,
                "video_recommendations": [],
            }

        if file_name == "actors_database.json":
            return {"last_updated": now, "actors": []}

        if file_name == "authors_database.json":
            return {"last_updated": now, "authors": []}

        if file_name == "import_tasks.json":
            return {"last_updated": now, "tasks": []}

        if file_name == "ui_state_database.json":
            return {"last_updated": now, "ui_state": {}}

        return {"last_updated": now}

    def restore_backup(self) -> dict:
        lock = self._get_lock()
        json_file = self._get_json_file()
        backup_file = json_file + BACKUP_SUFFIX
        with lock:
            try:
                if not os.path.exists(backup_file):
                    app_logger.warning("备份文件不存在")
                    return self._create_empty_data()
                with open(backup_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                app_logger.info(f"从备份恢复数据: {backup_file}")
                self._write_unlocked(data)
                return data
            except Exception as e:
                error_logger.error(f"从备份恢复失败: {e}")
                return self._create_empty_data()

    @staticmethod
    def _normalize_catalog_index_changed_ids(changed_ids: Iterable[Any] | None) -> Optional[set[str]]:
        if changed_ids is None:
            return None
        normalized = {
            str(item or "").strip()
            for item in changed_ids
            if str(item or "").strip()
        }
        return normalized

    def atomic_update(
        self,
        update_func: Callable[[dict], Optional[dict]],
        max_retries: int = 3,
        catalog_index_changed_ids: Iterable[Any] | None = None,
    ) -> bool:
        del max_retries
        normalized_changed_ids = self._normalize_catalog_index_changed_ids(catalog_index_changed_ids)
        lock = self._get_lock()
        with lock:
            try:
                data = self._read_unlocked()
                old_data_for_index = self._snapshot_for_catalog_index(data, normalized_changed_ids)
                updated = update_func(data)
                if updated is None:
                    return False
                written = self._write_unlocked(updated)
                if written:
                    self._sync_catalog_index_after_write(old_data_for_index, updated, normalized_changed_ids)
                return written
            except json.JSONDecodeError as e:
                error_logger.error(f"原子更新时 JSON 文件损坏: path={self._get_json_file()}, error={e}")
                data = self.restore_backup()
                old_data_for_index = self._snapshot_for_catalog_index(data, normalized_changed_ids)
                updated = update_func(data)
                if updated is None:
                    return False
                written = self._write_unlocked(updated)
                if written:
                    self._sync_catalog_index_after_write(old_data_for_index, updated, normalized_changed_ids)
                return written
            except Exception as e:
                error_logger.error(f"原子更新失败: {e}")
                return False

    def _snapshot_for_catalog_index(self, data: dict, changed_ids: Optional[set[str]] = None) -> Optional[dict]:
        data_key_by_file = {
            "comics_database.json": "comics",
            "recommendations_database.json": "recommendations",
            "videos_database.json": "videos",
            "video_recommendations_database.json": "video_recommendations",
        }
        data_key = data_key_by_file.get(self._file_name.lower())
        if not data_key:
            return None
        if changed_ids is None:
            try:
                from infrastructure.persistence.catalog_index.connection import get_catalog_index_path

                if not os.path.exists(get_catalog_index_path()):
                    return None
            except Exception:
                return None

        items = data.get(data_key)
        if not isinstance(items, list):
            return {data_key: []}

        snapshot_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if changed_ids is not None and str(item.get("id") or "").strip() not in changed_ids:
                continue
            copied = dict(item)
            for key in (
                "tag_ids",
                "list_ids",
                "actors",
                "authors",
                "thumbnail_images",
                "thumbnail_images_local",
                "preview_image_urls",
                "preview_pages",
                "actor_refs",
            ):
                if key in copied and isinstance(copied[key], list):
                    copied[key] = list(copied[key])
            snapshot_items.append(copied)
        return {data_key: snapshot_items}

    def _sync_catalog_index_after_write(
        self,
        old_data: Optional[dict],
        new_data: dict,
        changed_ids: Optional[set[str]] = None,
    ) -> None:
        if self._queue_deferred_catalog_index_sync(old_data, new_data):
            return
        self._sync_catalog_index_payload(self._file_name, old_data, new_data, changed_ids)

    def _queue_deferred_catalog_index_sync(self, old_data: Optional[dict], new_data: dict) -> bool:
        stack = getattr(self._deferred_index_sync, "stack", None)
        if not stack:
            return False

        pending = stack[-1]
        file_name = self._file_name
        payload = pending.setdefault(
            file_name,
            {
                "old": copy.deepcopy(old_data),
                "old_set": True,
                "new": None,
            },
        )
        payload["new"] = copy.deepcopy(new_data)
        return True

    @staticmethod
    def _sync_catalog_index_payload(
        file_name: str,
        old_data: Optional[dict],
        new_data: Optional[dict],
        changed_ids: Optional[set[str]] = None,
    ) -> None:
        if new_data is None:
            return
        try:
            from infrastructure.persistence.catalog_index.writer import sync_after_json_write

            sync_after_json_write(file_name, old_data, new_data, changed_ids=changed_ids)
        except Exception as e:
            error_logger.warning(f"同步 catalog index 失败，不影响 JSON 写入: {file_name}, {e}")
