"""下载任务完成后自动归集 + 软链接导入本地视频库。

宿主侧后台服务：周期性轮询启用了自动处理的下载引擎，
对新增的已完成任务（status=complete）：

1. 自动归集（auto_organize_enabled）：检查下载目录中是否已有相同番号的
   内容。若该番号已有文件夹，将散文件移入；若无文件夹，写入待确认记录
   （pending），由前端弹窗询问是否创建，确认后创建文件夹并移入，
   忽略则不创建文件夹、文件保留在原位置。
2. 自动导入（auto_import_enabled）：以软链接模式（softlink_ref，保留
   源文件）调用本地视频导入服务，把下载目录链接进本地视频库。

归集产生待确认询问时，若任务同时开启了自动导入，用户在弹窗中选择
『确认』或『忽略』后都会补执行一次导入（确认导入新文件夹、忽略导入
原目录），避免文件被移动后漏导或任务被忽略后永远不再导入。

去重：以 (engine_id, gid) 记录已处理任务；用户忽略归集的任务记入
ignored；待确认记录记入 pending。三者均持久化到状态文件。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from core.constants import DATA_DIR
from core.storage_layout import set_current_space_mode
from infrastructure.logger import app_logger, error_logger

AUTO_IMPORT_STATE_FILENAME = "download_auto_import_state.json"
DEFAULT_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_IMPORT_MODE = "softlink_ref"

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".ts",
    ".m2ts", ".rmvb", ".webm", ".m4v",
}

_SERVICE = None
_SERVICE_MODE = None
_SERVICE_LOCK = threading.Lock()


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


def get_download_auto_import_service(space_mode: str = "normal"):
    """返回全局自动处理服务实例（按空间模式复用）。"""
    global _SERVICE, _SERVICE_MODE
    with _SERVICE_LOCK:
        if _SERVICE is None or _SERVICE_MODE != str(space_mode or "normal"):
            _SERVICE = DownloadAutoImportService(space_mode=str(space_mode or "normal"))
            _SERVICE_MODE = str(space_mode or "normal")
        return _SERVICE


class DownloadAutoImportService:
    """后台轮询下载引擎已完成任务，自动归集并导入本地视频库。"""

    def __init__(
        self,
        host=None,
        state_path: str = "",
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        space_mode: str = "normal",
    ):
        self._host = host
        self._state_path = os.path.abspath(
            str(state_path or os.path.join(DATA_DIR, AUTO_IMPORT_STATE_FILENAME))
        )
        self._poll_interval = max(float(poll_interval_seconds or 0), 5.0)
        self._space_mode = str(space_mode or "normal")
        self._lock = threading.Lock()
        self._processed: set = set()
        self._ignored: set = set()
        self._pending: List[Dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._load_state()

    # ---------- 状态持久化 ----------

    def _load_state(self) -> None:
        try:
            if os.path.exists(self._state_path):
                with open(self._state_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    payload = {}
                processed = payload.get("processed")
                if isinstance(processed, list):
                    self._processed = {str(item) for item in processed if str(item).strip()}
                ignored = payload.get("ignored")
                if isinstance(ignored, list):
                    self._ignored = {str(item) for item in ignored if str(item).strip()}
                pending = payload.get("pending")
                if isinstance(pending, list):
                    self._pending = [
                        item for item in pending
                        if isinstance(item, dict) and str(item.get("id") or "").strip()
                    ]
        except Exception as exc:
            error_logger.error(f"加载自动处理状态失败（{self._state_path}）: {exc}")

    def _save_state(self) -> None:
        try:
            directory = os.path.dirname(self._state_path) or "."
            os.makedirs(directory, exist_ok=True)
            with self._lock:
                processed = sorted(self._processed)
                ignored = sorted(self._ignored)
                pending = [dict(item) for item in self._pending]
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"processed": processed, "ignored": ignored, "pending": pending},
                    f, ensure_ascii=False, indent=2,
                )
        except Exception as exc:
            error_logger.error(f"保存自动处理状态失败: {exc}")

    # ---------- 生命周期 ----------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="download-auto-import",
            daemon=True,
        )
        self._thread.start()
        app_logger.info(
            f"下载完成自动处理服务已启动（间隔 {self._poll_interval:.0f}s，空间 {self._space_mode}）"
        )

    def stop(self) -> None:
        self._stop.set()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                error_logger.error(f"下载完成自动处理执行异常: {exc}")
            self._stop.wait(self._poll_interval)

    # ---------- 主流程 ----------

    def run_once(self) -> None:
        set_current_space_mode(self._space_mode)
        host = self._resolve_host()
        if host is None:
            return
        try:
            engines = host.list_download_engines() or []
        except Exception as exc:
            error_logger.error(f"获取下载引擎列表失败: {exc}")
            return
        for engine in engines:
            try:
                self._process_engine(host, engine)
            except Exception as exc:
                error_logger.error(
                    f"自动处理：处理引擎 {engine.get('name') or engine.get('plugin_id')} 失败: {exc}"
                )

    def _resolve_host(self):
        if self._host is not None:
            return self._host
        try:
            from protocol.host_service import get_protocol_host_service

            return get_protocol_host_service()
        except Exception as exc:
            error_logger.error(f"无法获取协议宿主服务: {exc}")
            return None

    def _process_engine(self, host, engine: Dict[str, Any]) -> None:
        config_key = str(engine.get("config_key") or "").strip()
        engine_id = str(engine.get("plugin_id") or "").strip()
        if not engine_id:
            return

        plugin_config = self._read_plugin_config(host, config_key)
        auto_import = _as_bool(plugin_config.get("auto_import_enabled"), False)
        auto_organize = _as_bool(plugin_config.get("auto_organize_enabled"), False)
        if not auto_import and not auto_organize:
            return

        import_mode = self._normalize_import_mode(
            str(plugin_config.get("auto_import_mode") or DEFAULT_IMPORT_MODE)
        )

        try:
            _, _, payload = host.execute_download_capability(
                engine_id, "download.task.list", {"status": "complete"}
            )
        except Exception as exc:
            error_logger.error(f"自动处理：查询 {engine_id} 已完成任务失败: {exc}")
            return

        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, list):
            return
        for task in tasks:
            try:
                self._process_task(
                    engine_id, task, import_mode, plugin_config,
                    auto_import=auto_import, auto_organize=auto_organize,
                )
            except Exception as exc:
                error_logger.error(
                    f"自动处理：任务 {engine_id}:{task.get('gid')} 处理失败: {exc}"
                )

    def _read_plugin_config(self, host, config_key: str) -> Dict[str, Any]:
        if not config_key:
            return {}
        try:
            store = getattr(host, "_config_store", None)
            if store is None:
                return {}
            config = store.get_plugin_config(config_key)
            return config if isinstance(config, dict) else {}
        except Exception as exc:
            error_logger.error(f"自动处理：读取插件配置失败（{config_key}）: {exc}")
            return {}

    def _process_task(
        self,
        engine_id: str,
        task: Dict[str, Any],
        import_mode: str,
        plugin_config: Dict[str, Any],
        *,
        auto_import: bool,
        auto_organize: bool,
    ) -> None:
        gid = str(task.get("gid") or "").strip()
        if not gid:
            return
        key = f"{engine_id}:{gid}"
        with self._lock:
            if key in self._processed or key in self._ignored:
                return
            if any(item["id"] == key for item in self._pending):
                return

        source_path = self._resolve_source_path(task, plugin_config)
        if not source_path or not os.path.isdir(source_path):
            # 目录未就绪（可能仍在校验或缓存路径），留待下轮重试
            app_logger.info(f"自动处理：任务 {key} 的目录尚未就绪，跳过本轮: {source_path}")
            return

        if auto_organize:
            task_name = str(task.get("name") or "")
            code = self._extract_code(task_name)
            organize_result = self._organize_task(
                key, source_path, code, task_name,
                auto_import=auto_import, import_mode=import_mode,
            )
            if organize_result == "pending":
                label = code or task_name or "未知"
                app_logger.info(
                    f"自动归集：{key} 无 {label} 文件夹，已记录待确认（{len(self._pending)} 项）"
                )
                return

        if auto_import:
            try:
                result = self._import_video(source_path, import_mode)
                app_logger.info(
                    f"自动导入完成：{key} 目录 {source_path}（模式 {import_mode}）-> {result.message}"
                )
            except Exception as exc:
                error_logger.error(f"自动导入：任务 {key}（{source_path}）导入失败: {exc}")

        self._mark_processed(key)

    @staticmethod
    def _resolve_source_path(
        task: Dict[str, Any],
        plugin_config: Dict[str, Any],
    ) -> str:
        raw_path = str(task.get("dir") or "").strip() or str(plugin_config.get("dir") or "").strip()
        if not raw_path:
            return ""
        try:
            return os.path.abspath(os.path.expandvars(os.path.expanduser(raw_path)))
        except Exception:
            return raw_path

    @staticmethod
    def _normalize_import_mode(raw_mode: str) -> str:
        try:
            from application.video_app_service import VideoAppService

            return VideoAppService.normalize_local_import_mode(raw_mode)
        except Exception:
            return DEFAULT_IMPORT_MODE

    @staticmethod
    def _import_video(source_path: str, import_mode: str):
        from application.video_app_service import VideoAppService

        return VideoAppService().import_local_videos_from_path(
            source_path,
            import_mode=import_mode,
        )

    # ---------- 番号提取与归集 ----------

    @staticmethod
    def _extract_code(raw_name: str) -> str:
        name = str(raw_name or "").strip()
        if not name:
            return ""
        try:
            from application.video_app_service import VideoAppService

            match = VideoAppService.CODE_PATTERN.search(name)
            if not match:
                return ""
            # 统一为 "ABC-123" 形式（便于匹配文件夹/文件名）
            return f"{match.group(1)}-{match.group(2)}".upper()
        except Exception:
            return ""

    def _organize_task(
        self,
        key: str,
        source_dir: str,
        code: str,
        task_name: str = "",
        *,
        auto_import: bool = False,
        import_mode: str = DEFAULT_IMPORT_MODE,
    ) -> str:
        """按番号/剧名检查下载目录并归集散文件。

        优先番号（ABC-123）；无番号时尝试按剧名（动漫剧集）分组。

        返回：
        - "moved": 已存在目标文件夹，散文件已移入
        - "pending": 无目标文件夹，已记录待确认
        - "none": 无散文件或无法提取番号/剧名
        """
        if code:
            code_lower = code.lower()
            # 兼容带连字符（ABC-123）与紧凑（ABC123）两种命名
            tokens = {code_lower, code_lower.replace("-", ""), code_lower.replace(" ", "")}
            folder_hint = code
        else:
            series = self._extract_series_name(task_name)
            if not series:
                return "none"
            normalized = self._normalize_for_match(series)
            if len(normalized) < 5:
                return "none"
            tokens = {normalized}
            folder_hint = self._sanitize_folder_name(series)

        # 任务已直接下载到剧名/番号文件夹时无需再归集
        source_basename = os.path.basename(os.path.normpath(source_dir))
        if self._entry_matches(source_basename, tokens):
            return "none"

        try:
            entries = os.listdir(source_dir)
        except OSError as exc:
            error_logger.error(f"自动归集：扫描目录失败（{source_dir}）: {exc}")
            return "none"

        target_folder = ""
        for entry in entries:
            full = os.path.join(source_dir, entry)
            if os.path.isdir(full) and self._entry_matches(entry, tokens):
                target_folder = full
                break

        loose_files: List[str] = []
        for entry in entries:
            full = os.path.join(source_dir, entry)
            if not os.path.isfile(full):
                continue
            if os.path.splitext(entry)[1].lower() not in VIDEO_EXTENSIONS:
                continue
            base = os.path.splitext(entry)[0]
            if self._entry_matches(base, tokens):
                loose_files.append(entry)

        if not loose_files:
            return "none"

        if target_folder:
            for filename in sorted(loose_files):
                self._move_file_into_folder(os.path.join(source_dir, filename), target_folder)
            app_logger.info(f"自动归集：{key} 将 {len(loose_files)} 个散文件移入 {target_folder}")
            return "moved"

        self._add_pending(
            key,
            folder_hint,
            source_dir,
            loose_files,
            auto_import=auto_import,
            import_mode=import_mode,
        )
        return "pending"

    @staticmethod
    def _entry_matches(entry: str, tokens) -> bool:
        """条目名是否命中任一匹配串（番号或归一化剧名）。"""
        entry_lower = str(entry or "").lower()
        if not entry_lower:
            return False
        normalized_entry = "".join(ch for ch in entry_lower if ch.isalnum())
        for token in tokens:
            if token in entry_lower:
                return True
            # 归一化剧名（纯字母数字）需在归一化条目中匹配
            if token.isalnum() and token in normalized_entry:
                return True
        return False

    @staticmethod
    def _extract_series_name(raw_name: str) -> str:
        """从文件名提取剧名。

        去掉 [发布组] [画质] 等标签和结尾的集数标记。
        例：[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip ...]
            -> Katainaka no Ossan, Kensei ni Naru II
        """
        name = str(raw_name or "").strip()
        if not name:
            return ""
        name = os.path.splitext(name)[0]
        # 去掉 [标签]
        name = re.sub(r"\[[^\]]*\]", " ", name)
        # 去掉结尾的集数标记：- 01 / EP01 / 第01话 / 01v2
        name = re.sub(
            r"[-–—\s_]*(\d{1,3}\s*[vV]?\s*$|EP?\s*\d{1,3}\s*$|第\s*\d{1,3}\s*话\s*$)",
            " ",
            name,
        )
        # 清理首尾空白与分隔符
        name = re.sub(r"^[\s\-–—_.]+|[\s\-–—_.]+$", "", name).strip()
        if len(name) < 2:
            return ""
        return name

    @staticmethod
    def _normalize_for_match(name: str) -> str:
        """归一化用于包含匹配：小写并去掉所有非字母数字字符。"""
        return "".join(ch for ch in str(name or "").lower() if ch.isalnum())

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """清理为可用的文件夹名（去除 Windows 非法字符）。"""
        cleaned = re.sub(r'[<>:"/\\|?*]', " ", str(name or ""))
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned or "Unknown"

    @staticmethod
    def _move_file_into_folder(src: str, folder: str) -> str:
        name = os.path.basename(src)
        target = os.path.join(folder, name)
        if os.path.exists(target):
            base, ext = os.path.splitext(name)
            index = 1
            while os.path.exists(os.path.join(folder, f"{base}-{index}{ext}")):
                index += 1
            target = os.path.join(folder, f"{base}-{index}{ext}")
        shutil.move(src, target)
        return target

    # ---------- 待确认队列 ----------

    def _add_pending(
        self,
        key: str,
        code: str,
        source_dir: str,
        files: List[str],
        *,
        auto_import: bool = False,
        import_mode: str = DEFAULT_IMPORT_MODE,
    ) -> None:
        with self._lock:
            if key in self._ignored:
                return
            if any(item["id"] == key for item in self._pending):
                return
            self._pending.append({
                "id": key,
                "key": key,
                "code": code,
                "source_dir": source_dir,
                "target_dir": os.path.join(source_dir, code),
                "files": files,
                "auto_import": bool(auto_import),
                "import_mode": str(import_mode or DEFAULT_IMPORT_MODE),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        self._save_state()

    def get_pending_organizations(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._pending]

    def _import_with_mode(
        self,
        action_label: str,
        path: str,
        *,
        auto_import: bool,
        import_mode: str,
    ) -> None:
        """归集决策（确认/忽略）后补执行一次自动导入。

        仅在任务开启自动导入时执行；导入异常只记录日志，不阻断归集结果。
        """
        if not auto_import or not path or not os.path.isdir(path):
            return
        try:
            result = self._import_video(path, import_mode)
            app_logger.info(
                f"自动导入（{action_label}后执行）：目录 {path}"
                f"（模式 {import_mode}）-> {result.message}"
            )
        except Exception as exc:
            error_logger.error(f"自动导入（{action_label}后执行）：目录 {path} 导入失败: {exc}")

    def confirm_organization(self, org_id: str) -> Tuple[bool, str]:
        """确认创建番号/剧名文件夹、移入散文件，并把相关下载任务迁移到新目录。

        迁移通过 download.task.migrate 实现（删除原任务并以新目录重建），
        保证下载器里的任务状态与文件实际位置一致。
        """
        org_id = str(org_id or "").strip()
        target_dir = ""
        code_label = ""
        related_keys: List[str] = []
        files: List[str] = []
        source_dir = ""
        with self._lock:
            record = next((item for item in self._pending if item["id"] == org_id), None)
            if record is None:
                return False, "待确认记录不存在或已处理"
            self._pending = [item for item in self._pending if item["id"] != org_id]
            target_dir = str(record.get("target_dir") or "")
            code_label = str(record.get("code") or "")
            source_dir = str(record.get("source_dir") or "")
            files = list(record.get("files") or [])
            related = [record]
            # 同目标目录的其他待确认由本记录的文件一并覆盖，清除以避免重复弹窗
            for other in list(self._pending):
                if str(other.get("target_dir") or "") == target_dir:
                    self._pending.remove(other)
                    related.append(other)
            related_keys = [str(item.get("key") or "") for item in related]
        try:
            os.makedirs(target_dir, exist_ok=True)
            moved = 0
            for filename in files:
                src = os.path.join(source_dir, filename)
                if not os.path.isfile(src):
                    continue
                self._move_file_into_folder(src, target_dir)
                moved += 1
            migrated = self._migrate_related_tasks(related_keys, target_dir)
            # 归集确认后立即补一次导入，避免依赖迁移任务重新下载完成才导入
            self._import_with_mode(
                "确认归集",
                target_dir,
                auto_import=_as_bool(record.get("auto_import"), False),
                import_mode=str(record.get("import_mode") or DEFAULT_IMPORT_MODE),
            )
            for key in related_keys:
                self._mark_processed(key)
            self._save_state()
            app_logger.info(
                f"自动归集确认：{code_label} 创建 {target_dir}，"
                f"移入 {moved} 个文件，迁移 {migrated} 个下载任务"
            )
            message = f"已创建 {code_label} 文件夹并移入 {moved} 个文件"
            if migrated:
                message += f"，已重建 {migrated} 个下载任务"
            return True, message
        except Exception as exc:
            error_logger.error(f"自动归集确认失败：{related_keys}: {exc}")
            with self._lock:
                if not any(item["id"] == org_id for item in self._pending):
                    self._pending.insert(0, record)
            return False, f"归集失败: {exc}"

    def _migrate_related_tasks(self, related_keys: List[str], target_dir: str) -> int:
        """把归集涉及的任务迁移到目标目录；返回成功迁移数量。"""
        host = self._host
        if host is None:
            try:
                from protocol.host_service import get_protocol_host_service
                host = get_protocol_host_service()
            except Exception as exc:
                error_logger.error(f"自动归集迁移：无法获取宿主服务: {exc}")
                return 0
        migrated = 0
        for key in related_keys:
            engine_id, _, gid = str(key or "").partition(":")
            if not engine_id or not gid:
                continue
            try:
                host.execute_download_capability(
                    engine_id,
                    "download.task.migrate",
                    {"gid": gid, "dir": target_dir},
                )
                migrated += 1
            except Exception as exc:
                error_logger.error(f"自动归集迁移任务失败（{key}）: {exc}")
        return migrated

    def dismiss_organization(self, org_id: str) -> Tuple[bool, str]:
        """忽略本次归集询问：文件保留在原位置，之后不再重复询问该任务。

        若任务同时开启了自动导入，忽略后仍会补一次导入（导入原目录），
        避免文件因任务被忽略而永远不进入本地库。
        """
        org_id = str(org_id or "").strip()
        with self._lock:
            record = next((item for item in self._pending if item["id"] == org_id), None)
            if record is None:
                return False, "待确认记录不存在或已处理"
            self._pending = [item for item in self._pending if item["id"] != org_id]
            self._ignored.add(record["key"])
            source_dir = str(record.get("source_dir") or "")
            decision_auto_import = _as_bool(record.get("auto_import"), False)
            decision_import_mode = str(record.get("import_mode") or DEFAULT_IMPORT_MODE)
        self._save_state()
        self._import_with_mode(
            "忽略归集",
            source_dir,
            auto_import=decision_auto_import,
            import_mode=decision_import_mode,
        )
        app_logger.info(f"自动归集忽略：{record['key']}")
        return True, "已忽略"

    def _mark_processed(self, key: str) -> None:
        with self._lock:
            if key in self._processed:
                return
            self._processed.add(key)
        self._save_state()
