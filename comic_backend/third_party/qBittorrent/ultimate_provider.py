"""qBittorrent 磁力/种子下载插件（WebUI API v2 协议化适配器）。

通过 qBittorrent WebUI API 把磁力链接/直链投递给本机或远程 qBittorrent 实例，
实现磁力链接下载、任务状态查询、任务列表、暂停/继续与删除。

能力说明：
- health.query.status    配置就绪状态（不发网络请求）
- download.magnet.add    投递磁力/直链到 /torrents/add
- download.task.status   按 hash 查询任务状态（/torrents/info）
- download.task.list     查询任务列表（/torrents/info）
- download.task.pause    暂停任务（/torrents/stop）
- download.task.resume   继续任务（/torrents/start）
- download.task.remove   删除任务（/torrents/delete）
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from protocol.base import ProtocolProvider


QBITTORRENT_CONFIG_KEY = "qbittorrent"
QBITTORRENT_PLUGIN_ID = "download.qbittorrent"
QBITTORRENT_PLATFORM = "qBittorrent"

DEFAULT_WEBUI_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 30

# qBittorrent 原生 state -> 宿主统一状态
_QBT_STATE_MAP = {
    # 下载中
    "downloading": "active",
    "forcedDL": "active",
    "metaDL": "active",
    "forcedMetaDL": "active",
    "checkingDL": "active",
    "checkingResumeData": "active",
    "moving": "active",
    "allocating": "active",
    "stalledDL": "active",
    # 排队等待
    "queuedDL": "waiting",
    # 暂停（兼容 4.3.2 前后命名）
    "pausedDL": "paused",
    "pausedUP": "paused",
    "stoppedDL": "paused",
    "stoppedUP": "paused",
    # 已完成下载（做种中）
    "uploading": "complete",
    "forcedUP": "complete",
    "queuedUP": "complete",
    "stalledUP": "complete",
    "checkingUP": "complete",
    # 出错
    "error": "error",
    "missingFiles": "error",
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


def _as_int(value: Any, default: int, minimum: int = 0, maximum: int = 10**18) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _normalize_webui_url(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    return text or DEFAULT_WEBUI_URL


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


class QbittorrentProvider(ProtocolProvider):
    """qBittorrent 磁力下载能力实现。"""

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(payload or {})
        normalized: Dict[str, Any] = {}
        normalized["enabled"] = _as_bool(raw.get("enabled"), True)
        normalized["webui_url"] = _normalize_webui_url(raw.get("webui_url"))
        normalized["username"] = str(raw.get("username") or "").strip()
        normalized["password"] = str(raw.get("password") or "").strip()
        normalized["dir"] = str(raw.get("dir") or "").strip()
        normalized["timeout_seconds"] = _as_int(
            raw.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600
        )
        normalized["auto_import_enabled"] = _as_bool(raw.get("auto_import_enabled"), False)
        normalized["auto_import_mode"] = str(raw.get("auto_import_mode") or "softlink_ref").strip() or "softlink_ref"
        normalized["auto_organize_enabled"] = _as_bool(raw.get("auto_organize_enabled"), False)
        return normalized

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        public = dict(normalized)
        public["password_configured"] = bool(normalized.get("password"))
        public["password"] = ""
        return public

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        enabled = _as_bool(normalized.get("enabled"), True)
        webui_url = str(normalized.get("webui_url") or "").strip()
        configured = bool(enabled and webui_url)
        return {
            "configured": configured,
            "message": "" if configured else "qBittorrent 插件未启用或 WebUI 地址未配置。",
            "missing_fields": [] if webui_url else ["webui_url"],
        }

    # ---------- 协议入口 ----------

    def execute(
        self,
        capability: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Any:
        normalized = self.normalize_config(config)
        if not _as_bool(normalized.get("enabled"), True):
            raise RuntimeError("qBittorrent 插件未启用。")

        if capability == "health.query.status":
            return self.get_query_status(config)
        if capability == "download.magnet.add":
            return self._handle_add_magnet(normalized, params)
        if capability == "download.task.status":
            return self._handle_task_status(normalized, params)
        if capability == "download.task.list":
            return self._handle_task_list(normalized, params)
        if capability == "download.task.pause":
            return self._handle_task_pause(normalized, params)
        if capability == "download.task.resume":
            return self._handle_task_resume(normalized, params)
        if capability == "download.task.remove":
            return self._handle_task_remove(normalized, params)
        if capability == "download.task.migrate":
            return self._handle_task_migrate(normalized, params)

        raise ValueError(f"不支持的能力: {capability}")

    # ---------- WebUI API 传输 ----------

    def _api_call(
        self,
        config: Dict[str, Any],
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> "requests.Response":
        """调用 qBittorrent WebUI API v2，返回响应；非 2xx 抛 RuntimeError。

        每次调用先登录（携带 cookie 与 CSRF 所需的 Referer 头）。
        """
        base = str(config.get("webui_url") or DEFAULT_WEBUI_URL).rstrip("/")
        session = self._login(config)
        url = f"{base}/api/v2/{endpoint}"
        effective_timeout = _as_int(
            timeout or config.get("timeout_seconds"),
            DEFAULT_TIMEOUT_SECONDS, 1, 600,
        )
        try:
            if method == "GET":
                response = session.get(url, params=params, timeout=effective_timeout)
            else:
                response = session.post(url, params=params, data=data, timeout=effective_timeout)
        except Exception as exc:
            raise RuntimeError(f"qBittorrent 请求失败（{url}）: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(
                f"qBittorrent HTTP {response.status_code}: {response.text[:300]}"
            )
        return response

    def _login(self, config: Dict[str, Any]) -> "requests.Session":
        """登录 WebUI 并返回携带 SID cookie 的会话。"""
        base = str(config.get("webui_url") or DEFAULT_WEBUI_URL).rstrip("/")
        username = str(config.get("username") or "").strip()
        password = str(config.get("password") or "").strip()
        effective_timeout = _as_int(
            config.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600,
        )
        session = requests.Session()
        # qBittorrent 5.x 默认开启 CSRF 保护，需要同源 Referer
        session.headers.update({
            "Referer": f"{base}/",
            "X-Requested-With": "XMLHttpRequest",
        })
        try:
            response = session.post(
                f"{base}/api/v2/auth/login",
                data={"username": username, "password": password},
                timeout=effective_timeout,
            )
        except Exception as exc:
            raise RuntimeError(f"qBittorrent 登录请求失败（{base}）: {exc}") from exc

        # 登录成功判定：
        # - qBittorrent 4.x: HTTP 200 + 文本 "Ok."
        # - qBittorrent 5.x: HTTP 204 + 空响应
        # - 失败: HTTP 200 + 文本 "Fails."（4.x）或非 2xx（5.x Host/CSRF 校验失败）
        text = str(response.text or "").strip()
        if response.status_code >= 400:
            raise RuntimeError(f"qBittorrent 登录失败: HTTP {response.status_code}: {text[:200]}")
        if text == "Fails.":
            raise RuntimeError("qBittorrent 登录失败: 用户名或密码错误。")
        return session

    # ---------- 能力实现 ----------

    def _handle_add_magnet(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.magnet.add — 投递磁力/直链到 /torrents/add。

        qBittorrent 以换行符分隔多个链接，它们会作为独立任务加入。
        """
        magnet = str(params.get("magnet") or params.get("uri") or "").strip()
        raw_uris = params.get("uris") or []
        if not isinstance(raw_uris, list):
            raw_uris = []
        uris: List[str] = []
        if magnet:
            uris.append(magnet)
        for item in raw_uris:
            text = str(item or "").strip()
            if text and text not in uris:
                uris.append(text)
        if not uris:
            raise ValueError("download.magnet.add 缺少 magnet 参数。")

        data: Dict[str, Any] = {"urls": "\n".join(uris)}
        target_dir = str(params.get("dir") or "").strip() or config.get("dir") or ""
        if target_dir:
            # qBittorrent 会自动创建 savepath，但本机场景提前创建让错误更明确（远程实例由远端负责）
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError:
                pass
            data["savepath"] = target_dir

        self._api_call(config, "torrents/add", method="POST", data=data)
        # qBittorrent 添加接口只返回 "Ok."，不返回任务标识（磁力需解析元数据后才有 hash）
        return {
            "gid": "",
            "added": True,
            "magnet": uris[0],
            "savepath": target_dir,
        }

    def _handle_task_status(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """处理 download.task.status — 按 hash 查询任务状态。"""
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.status 缺少 gid 参数。")
        response = self._api_call(
            config, "torrents/info", params={"hashes": gid}
        )
        items = self._parse_json_list(response)
        if not items:
            return None
        return self._normalize_task(items[0])

    def _handle_task_list(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.list — 查询任务列表。

        /torrents/info 返回全部任务（含暂停/出错/做种），按需在本地过滤。
        """
        response = self._api_call(config, "torrents/info")
        items = self._parse_json_list(response)
        tasks = [self._normalize_task(item) for item in items]

        status = str(params.get("status") or "").strip().lower()
        if status:
            tasks = [task for task in tasks if task["status"] == status]
        return {"tasks": tasks, "count": len(tasks)}

    def _handle_task_pause(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.pause — 暂停任务（/torrents/stop）。"""
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.pause 缺少 gid 参数。")

        status = self._query_task_status(config, gid)
        if status == "paused":
            return {"gid": gid, "paused": True, "already": True}
        if status in {"active", "waiting"}:
            self._api_call(
                config, "torrents/stop", method="POST", data={"hashes": gid}
            )
            return {"gid": gid, "paused": True, "already": False}
        raise RuntimeError(f"任务状态为 {status or 'unknown'}，无法暂停。")

    def _handle_task_resume(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.resume — 继续任务（/torrents/start）。"""
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.resume 缺少 gid 参数。")

        status = self._query_task_status(config, gid)
        if status in {"active", "waiting"}:
            return {"gid": gid, "resumed": True, "already": True}
        if status == "paused":
            self._api_call(
                config, "torrents/start", method="POST", data={"hashes": gid}
            )
            return {"gid": gid, "resumed": True, "already": False}
        raise RuntimeError(f"任务状态为 {status or 'unknown'}，无法继续。")

    def _handle_task_remove(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.remove — 删除任务（/torrents/delete）。

        qBittorrent 的 delete 对任意状态的任务都有效（含已完成的记录），
        因此无需先查状态。deleteFiles 默认 false（仅移除任务不删文件）。
        """
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.remove 缺少 gid 参数。")
        self._api_call(
            config,
            "torrents/delete",
            method="POST",
            data={"hashes": gid, "deleteFiles": "false"},
        )
        return {"gid": gid, "removed": True}

    def _handle_task_migrate(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.migrate — 迁移任务到新下载目录。

        qBittorrent 不支持修改任务保存路径，因此流程为：
        1. 用任务 hash 构造磁力链接
        2. 删除原任务（不删文件）
        3. 以新 savepath 重新添加相同磁力（文件已在目标目录时仅重新校验）
        """
        gid = str(params.get("gid") or "").strip()
        target_dir = str(params.get("dir") or "").strip()
        if not gid:
            raise ValueError("download.task.migrate 缺少 gid 参数。")
        if not target_dir:
            raise ValueError("download.task.migrate 缺少 dir 参数。")
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"创建目标目录失败（{target_dir}）: {exc}") from exc

        response = self._api_call(config, "torrents/info", params={"hashes": gid})
        items = self._parse_json_list(response)
        if not items:
            raise RuntimeError(f"任务不存在: {gid}")
        infohash = str(items[0].get("hash") or gid).strip().lower()

        # 1) 删除原任务（不删除已下载文件）
        self._api_call(
            config,
            "torrents/delete",
            method="POST",
            data={"hashes": infohash, "deleteFiles": "false"},
        )
        # 2) 用相同 infohash 重建任务到目标目录
        magnet = f"magnet:?xt=urn:btih:{infohash}"
        self._api_call(
            config,
            "torrents/add",
            method="POST",
            data={"urls": magnet, "savepath": target_dir},
        )
        return {"gid": infohash, "migrated": True, "dir": target_dir}

    def _query_task_status(self, config: Dict[str, Any], gid: str) -> str:
        """查询任务状态；查询失败返回空字符串（调用方自行处理）。"""
        try:
            response = self._api_call(
                config, "torrents/info", params={"hashes": gid}
            )
            items = self._parse_json_list(response)
        except Exception:
            return ""
        if not items:
            return ""
        raw_status = str(items[0].get("state") or "").strip()
        return _QBT_STATE_MAP.get(raw_status, raw_status or "")

    # ---------- 数据转换 ----------

    @staticmethod
    def _parse_json_list(response: "requests.Response") -> List[Dict[str, Any]]:
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"qBittorrent 响应解析失败: {exc}") from exc
        if isinstance(body, dict):
            return [body]
        if isinstance(body, list):
            return [item for item in body if isinstance(item, dict)]
        return []

    def _normalize_task(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """把 qBittorrent 原始任务对象转为宿主统一结构。"""
        total = _as_int(raw.get("size") or raw.get("total_size"), 0, 0, 10**18)
        progress = _as_float(raw.get("progress"))
        completed = int(round(total * progress))
        raw_state = str(raw.get("state") or "").strip()
        status = _QBT_STATE_MAP.get(raw_state, raw_state or "unknown")

        return {
            "gid": str(raw.get("hash") or ""),
            "status": status,
            "name": str(raw.get("name") or ""),
            "total_length": total,
            "completed_length": completed,
            "progress": progress,
            "download_speed": _as_int(raw.get("dlspeed"), 0, 0, 10**18),
            "upload_speed": _as_int(raw.get("upspeed"), 0, 0, 10**18),
            "error_code": None,
            "error_message": str(raw.get("error") or ""),
            "dir": str(raw.get("save_path") or ""),
            "files": [],
        }
