"""Aria2 磁力/种子下载插件（JSON-RPC 协议化适配器）原型。

通过 Aria2 的 JSON-RPC 接口把磁力链接投递给本机或远程 Aria2 实例，
实现磁力链接下载、任务状态查询、任务列表与任务删除。

能力说明：
- health.query.status    配置就绪状态（不发网络请求）
- download.magnet.add    投递磁力/直链到 aria2.addUri
- download.task.status   按 gid 查询任务状态（aria2.tellStatus）
- download.task.list     查询任务列表（tellActive/tellWaiting/tellStopped）
- download.task.remove   删除任务（aria2.remove / aria2.forceRemove）
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from protocol.base import ProtocolProvider


ARIA2_CONFIG_KEY = "aria2"
ARIA2_PLUGIN_ID = "download.aria2"
ARIA2_PLATFORM = "Aria2"

DEFAULT_RPC_URL = "http://127.0.0.1:6800/jsonrpc"
DEFAULT_TIMEOUT_SECONDS = 30

# Aria2 原生状态 -> 宿主统一状态
_STATUS_MAP = {
    "active": "active",
    "waiting": "waiting",
    "paused": "paused",
    "error": "error",
    "complete": "complete",
    "removed": "removed",
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


def _normalize_rpc_url(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    return text or DEFAULT_RPC_URL


def _extract_name(raw: Dict[str, Any]) -> str:
    """从 Aria2 任务原始信息里提取可读文件名。

    磁力任务在元数据下载完成后，bittorrent.info.name 才可用；
    在此之前回退到文件路径的文件名。
    """
    bt = raw.get("bittorrent") if isinstance(raw.get("bittorrent"), dict) else {}
    info = bt.get("info") if isinstance(bt.get("info"), dict) else {}
    name = str(info.get("name") or "").strip()
    if name:
        return name
    files = raw.get("files") or []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if path:
            return path.replace("\\", "/").rsplit("/", 1)[-1]
    return ""


class Aria2Provider(ProtocolProvider):
    """Aria2 磁力下载能力实现。"""

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(payload or {})
        normalized: Dict[str, Any] = {}
        normalized["enabled"] = _as_bool(raw.get("enabled"), True)
        normalized["rpc_url"] = _normalize_rpc_url(raw.get("rpc_url"))
        normalized["secret"] = str(raw.get("secret") or "").strip()
        normalized["dir"] = str(raw.get("dir") or "").strip()
        normalized["timeout_seconds"] = _as_int(
            raw.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600
        )
        return normalized

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        public = dict(normalized)
        public["secret_configured"] = bool(normalized.get("secret"))
        public["secret"] = ""
        return public

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        enabled = _as_bool(normalized.get("enabled"), True)
        rpc_url = str(normalized.get("rpc_url") or "").strip()
        configured = bool(enabled and rpc_url)
        return {
            "configured": configured,
            "message": "" if configured else "Aria2 插件未启用或 RPC 地址未配置。",
            "missing_fields": [] if rpc_url else ["rpc_url"],
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
            raise RuntimeError("Aria2 插件未启用。")

        if capability == "health.query.status":
            return self.get_query_status(config)
        if capability == "download.magnet.add":
            return self._handle_add_magnet(normalized, params)
        if capability == "download.task.status":
            return self._handle_task_status(normalized, params)
        if capability == "download.task.list":
            return self._handle_task_list(normalized, params)
        if capability == "download.task.remove":
            return self._handle_task_remove(normalized, params)

        raise ValueError(f"不支持的能力: {capability}")

    # ---------- JSON-RPC 传输 ----------

    def _rpc_call(
        self,
        config: Dict[str, Any],
        method: str,
        params: Optional[List[Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """调用 Aria2 JSON-RPC，返回 result；失败抛 RuntimeError。

        token 通过第一个参数 `token:<secret>` 传入（Aria2 标准鉴权方式）。
        """
        url = str(config.get("rpc_url") or DEFAULT_RPC_URL).rstrip("/")
        secret = str(config.get("secret") or "").strip()
        rpc_params: List[Any] = list(params or [])
        if secret:
            rpc_params.insert(0, f"token:{secret}")
        payload = {
            "jsonrpc": "2.0",
            "id": f"aria2-{int(time.time() * 1000)}",
            "method": method,
            "params": rpc_params,
        }
        effective_timeout = _as_int(
            timeout or config.get("timeout_seconds"),
            DEFAULT_TIMEOUT_SECONDS, 1, 600,
        )
        try:
            response = requests.post(url, json=payload, timeout=effective_timeout)
        except Exception as exc:
            raise RuntimeError(f"Aria2 RPC 请求失败（{url}）: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(
                f"Aria2 RPC HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"Aria2 RPC 响应解析失败: {exc}") from exc

        error = body.get("error") if isinstance(body, dict) else None
        if error:
            code = error.get("code")
            message = str(error.get("message") or "").strip()
            raise RuntimeError(f"Aria2 RPC 错误 [{code}]: {message}")
        return body.get("result")

    # ---------- 能力实现 ----------

    def _handle_add_magnet(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.magnet.add — 投递磁力链接到 aria2.addUri。

        参数：magnet 单个磁力链接；uris 额外的链接列表；dir/out 可选覆盖默认目录与文件名。
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

        options: Dict[str, str] = {}
        target_dir = str(params.get("dir") or "").strip() or config.get("dir") or ""
        if target_dir:
            options["dir"] = target_dir
        out = str(params.get("out") or "").strip()
        if out:
            options["out"] = out

        rpc_params: List[Any] = [uris]
        if options:
            rpc_params.append(options)
        gid = self._rpc_call(config, "aria2.addUri", rpc_params)
        return {
            "gid": gid,
            "added": True,
            "magnet": uris[0],
            "options": options,
        }

    def _handle_task_status(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """处理 download.task.status — 按 gid 查询任务状态。"""
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.status 缺少 gid 参数。")
        raw = self._rpc_call(config, "aria2.tellStatus", [gid])
        if not isinstance(raw, dict):
            return None
        return self._normalize_task(raw)

    def _handle_task_list(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.list — 查询任务列表。

        status 参数可选：active / waiting / paused / stopped / complete / error。
        不传时合并 active + waiting（含 paused）+ stopped 三组。
        """
        status = str(params.get("status") or "").strip().lower()
        raw_items: List[Dict[str, Any]] = []

        if status in ("", "active"):
            active = self._rpc_call(config, "aria2.tellActive")
            raw_items.extend(active if isinstance(active, list) else [])
        if status in ("", "waiting", "paused"):
            waiting = self._rpc_call(config, "aria2.tellWaiting", [0, 1000])
            raw_items.extend(waiting if isinstance(waiting, list) else [])
        if status in ("", "stopped", "complete", "error", "removed"):
            stopped = self._rpc_call(config, "aria2.tellStopped", [0, 1000])
            raw_items.extend(stopped if isinstance(stopped, list) else [])

        tasks = [self._normalize_task(item) for item in raw_items if isinstance(item, dict)]
        return {"tasks": tasks, "count": len(tasks)}

    def _handle_task_remove(
        self,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 download.task.remove — 删除任务。

        force 默认 true（forceRemove，可删除 paused 任务）。
        Aria2 的 remove/forceRemove 只对活动任务（active/waiting/paused）有效；
        已停止的任务（complete/error/removed）必须用 removeDownloadResult 清理记录。
        """
        gid = str(params.get("gid") or "").strip()
        if not gid:
            raise ValueError("download.task.remove 缺少 gid 参数。")
        force = _as_bool(params.get("force"), True)

        # 先查询状态，决定调用哪个 Aria2 方法
        status = ""
        try:
            raw = self._rpc_call(config, "aria2.tellStatus", [gid])
            if isinstance(raw, dict):
                status = str(raw.get("status") or "").strip()
        except Exception:
            status = ""

        if status in {"complete", "error", "removed"}:
            result = self._rpc_call(config, "aria2.removeDownloadResult", [gid])
        else:
            method = "aria2.forceRemove" if force else "aria2.remove"
            result = self._rpc_call(config, method, [gid])
        return {"gid": gid, "removed": result == "OK"}

    # ---------- 数据转换 ----------

    def _normalize_task(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """把 Aria2 原始任务对象转为宿主统一结构。"""
        total = _as_int(raw.get("totalLength"), 0, 0, 10**18)
        completed = _as_int(raw.get("completedLength"), 0, 0, 10**18)
        raw_status = str(raw.get("status") or "").strip()
        status = _STATUS_MAP.get(raw_status, raw_status or "unknown")

        files: List[Dict[str, Any]] = []
        for item in (raw.get("files") or []):
            if not isinstance(item, dict):
                continue
            files.append({
                "path": str(item.get("path") or ""),
                "length": _as_int(item.get("length"), 0, 0, 10**18),
                "completed_length": _as_int(item.get("completedLength"), 0, 0, 10**18),
            })

        return {
            "gid": str(raw.get("gid") or ""),
            "status": status,
            "name": _extract_name(raw),
            "total_length": total,
            "completed_length": completed,
            "progress": (completed / total) if total > 0 else 0.0,
            "download_speed": _as_int(raw.get("downloadSpeed"), 0, 0, 10**18),
            "upload_speed": _as_int(raw.get("uploadSpeed"), 0, 0, 10**18),
            "error_code": raw.get("errorCode"),
            "error_message": str(raw.get("errorMessage") or ""),
            "dir": str(raw.get("dir") or ""),
            "files": files,
        }
