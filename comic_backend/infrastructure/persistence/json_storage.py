from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from typing import Callable, Dict, Optional

from core.constants import (
    AUTHOR_JSON_FILE,
    ACTOR_JSON_FILE,
    BACKUP_SUFFIX,
    IMPORT_TASKS_JSON_FILE,
    JSON_FILE,
    LISTS_JSON_FILE,
    META_DIR,
    RECOMMENDATION_JSON_FILE,
    TAGS_JSON_FILE,
    UI_STATE_JSON_FILE,
    USER_CONFIG_JSON_FILE,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE,
)
from infrastructure.logger import app_logger, error_logger


class JsonStorage:
    _instances: Dict[str, "JsonStorage"] = {}
    _locks: Dict[str, threading.RLock] = {}

    def __new__(cls, json_file: str = None):
        normalized_path = os.path.abspath(json_file or JSON_FILE)
        instance = cls._instances.get(normalized_path)
        if instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[normalized_path] = instance
        return instance

    def __init__(self, json_file: str = None):
        if self._initialized:
            return

        self.json_file = os.path.abspath(json_file or JSON_FILE)
        self._tmp_prefix = "comic_db_"
        self._tmp_suffix = ".tmp"
        self._tmp_cleanup_max_age_seconds = 600
        self._last_tmp_cleanup_ts = 0.0
        self._tmp_cleanup_cooldown_seconds = 60
        self._lock = self._locks.setdefault(self.json_file, threading.RLock())
        self._cleanup_stale_temp_files(force=True)
        self._initialized = True

    def _cleanup_stale_temp_files(self, force: bool = False) -> int:
        try:
            now = time.time()
            if not force and (now - self._last_tmp_cleanup_ts) < self._tmp_cleanup_cooldown_seconds:
                return 0
            self._last_tmp_cleanup_ts = now

            dir_path = os.path.dirname(self.json_file) or "."
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
            error_logger.warning(f"扫描残留临时文件失败: {self.json_file}, {e}")
            return 0

    def _read_unlocked(self) -> dict:
        if not os.path.exists(self.json_file):
            return self._create_empty_data()
        with open(self.json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_unlocked(self, data: dict) -> bool:
        self._cleanup_stale_temp_files()
        dir_path = os.path.dirname(self.json_file) or "."
        os.makedirs(dir_path, exist_ok=True)

        backup_file = self.json_file + BACKUP_SUFFIX
        if os.path.exists(self.json_file):
            try:
                shutil.copy2(self.json_file, backup_file)
            except Exception as e:
                error_logger.warning(f"创建备份失败: {e}")

        temp_path = os.path.join(dir_path, f"{self._tmp_prefix}{uuid.uuid4().hex}{self._tmp_suffix}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            last_error = None
            for attempt in range(3):
                try:
                    os.replace(temp_path, self.json_file)
                    last_error = None
                    break
                except PermissionError as e:
                    last_error = e
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error
            app_logger.info(f"JSON 文件写入成功: {self.json_file}")
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
        with self._lock:
            try:
                data = self._read_unlocked()
                app_logger.info(f"JSON 文件读取成功: {self.json_file}")
                return data
            except json.JSONDecodeError as e:
                error_logger.error(f"JSON 文件损坏: path={self.json_file}, error={e}")
                return self.restore_backup()
            except Exception as e:
                error_logger.error(f"读取 JSON 文件失败: {e}")
                return self._create_empty_data()

    def write(self, data: dict, max_retries: int = 3) -> bool:
        del max_retries
        with self._lock:
            try:
                return self._write_unlocked(dict(data or {}))
            except Exception as e:
                error_logger.error(f"写入 JSON 文件失败: {e}")
                return False

    def cleanup_stale_meta_temp_files(self, max_age_seconds: int = 600) -> int:
        try:
            meta_dir_abs = os.path.abspath(META_DIR)
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
        file_name = os.path.basename(self.json_file).lower()
        now = time.strftime("%Y-%m-%d")

        if self.json_file == os.path.abspath(USER_CONFIG_JSON_FILE) or file_name == "user_config.json":
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

        if self.json_file == os.path.abspath(TAGS_JSON_FILE):
            return {
                "collection_name": "标签库",
                "user": "用户名",
                "last_updated": now,
                "tags": [],
            }

        if file_name == os.path.basename(TAGS_JSON_FILE).lower():
            return {
                "collection_name": "标签库",
                "user": "用户名",
                "last_updated": now,
                "tags": [],
            }

        if self.json_file == os.path.abspath(LISTS_JSON_FILE):
            return {
                "collection_name": "清单库",
                "user": "用户名",
                "last_updated": now,
                "lists": [],
            }

        if file_name == os.path.basename(LISTS_JSON_FILE).lower():
            return {
                "collection_name": "清单库",
                "user": "用户名",
                "last_updated": now,
                "lists": [],
            }

        if self.json_file == os.path.abspath(JSON_FILE):
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

        if file_name == os.path.basename(JSON_FILE).lower():
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

        if self.json_file == os.path.abspath(RECOMMENDATION_JSON_FILE):
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

        if file_name == os.path.basename(RECOMMENDATION_JSON_FILE).lower():
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

        if self.json_file == os.path.abspath(VIDEO_JSON_FILE):
            return {
                "collection_name": "视频库",
                "user": "用户名",
                "total_videos": 0,
                "last_updated": now,
                "videos": [],
            }

        if file_name == os.path.basename(VIDEO_JSON_FILE).lower():
            return {
                "collection_name": "视频库",
                "user": "用户名",
                "total_videos": 0,
                "last_updated": now,
                "videos": [],
            }

        if self.json_file == os.path.abspath(VIDEO_RECOMMENDATION_JSON_FILE):
            return {
                "collection_name": "推荐视频",
                "user": "用户名",
                "total_video_recommendations": 0,
                "last_updated": now,
                "video_recommendations": [],
            }

        if file_name == os.path.basename(VIDEO_RECOMMENDATION_JSON_FILE).lower():
            return {
                "collection_name": "推荐视频",
                "user": "用户名",
                "total_video_recommendations": 0,
                "last_updated": now,
                "video_recommendations": [],
            }

        if self.json_file == os.path.abspath(ACTOR_JSON_FILE):
            return {"last_updated": now, "actors": []}

        if file_name == os.path.basename(ACTOR_JSON_FILE).lower():
            return {"last_updated": now, "actors": []}

        if self.json_file == os.path.abspath(AUTHOR_JSON_FILE):
            return {"last_updated": now, "authors": []}

        if file_name == os.path.basename(AUTHOR_JSON_FILE).lower():
            return {"last_updated": now, "authors": []}

        if self.json_file == os.path.abspath(IMPORT_TASKS_JSON_FILE):
            return {"last_updated": now, "tasks": []}

        if file_name == os.path.basename(IMPORT_TASKS_JSON_FILE).lower():
            return {"last_updated": now, "tasks": []}

        if self.json_file == os.path.abspath(UI_STATE_JSON_FILE):
            return {"last_updated": now, "ui_state": {}}

        if file_name == os.path.basename(UI_STATE_JSON_FILE).lower():
            return {"last_updated": now, "ui_state": {}}

        return {"last_updated": now}

    def restore_backup(self) -> dict:
        backup_file = self.json_file + BACKUP_SUFFIX
        with self._lock:
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

    def atomic_update(self, update_func: Callable[[dict], Optional[dict]], max_retries: int = 3) -> bool:
        del max_retries
        with self._lock:
            try:
                data = self._read_unlocked()
                updated = update_func(data)
                if updated is None:
                    return False
                return self._write_unlocked(updated)
            except json.JSONDecodeError as e:
                error_logger.error(f"原子更新时 JSON 文件损坏: path={self.json_file}, error={e}")
                data = self.restore_backup()
                updated = update_func(data)
                if updated is None:
                    return False
                return self._write_unlocked(updated)
            except Exception as e:
                error_logger.error(f"原子更新失败: {e}")
                return False
