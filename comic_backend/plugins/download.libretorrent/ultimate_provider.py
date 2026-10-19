"""LibreTorrent 下载引擎插件（Android 专用 · 链式启动投递）。

只声明 ``download.magnet.add`` 一个能力：把磁力/种子链接通过 Android Intent 交给
已安装的 **LibreTorrent** 应用去下载。任务列表、暂停/继续/删除、目录迁移、自动归集
都不实现——LibreTorrent 自己管理自己的任务，宿主也拿不到它的任务状态。

宿主据此自动裁剪界面
--------------------
宿主的「功能 ↔ 能力」映射（``protocol/download_features.py``）会算出本引擎只支持
``submit_magnet``，于是：

- 下载任务页不会轮询本引擎（未声明 ``download.task.list``）；
- 自动归集/自动导入会跳过它（未声明 ``download.task.*``）；
- 界面上只剩「投递」入口，不会出现点不通的暂停/删除按钮。

这是能力驱动裁剪的设计用例：插件只声明真实能力，界面自适应，宿主零特判。
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import threading
from typing import Any, Dict, List, Optional

from protocol.base import ProtocolProvider

LIBRETORRENT_CONFIG_KEY = "libretorrent"
LIBRETORRENT_PLUGIN_ID = "download.libretorrent"
LIBRETORRENT_PLATFORM = "LibreTorrent"

MAGNET_CAPABILITY = "download.magnet.add"

DEFAULT_PACKAGE_NAME = "org.proninyaroslav.libretorrent"

# 本插件真实声明并实现的能力（只有投递一种）
SUPPORTED_CAPABILITIES = frozenset({MAGNET_CAPABILITY})

# Android 适配模块名带插件专属前缀，避免多插件共用 sys.path 时发生导入冲突
# （API_INTEGRATION_STANDARD.md §8.2）。
_ANDROID_RUNTIME_MODULE = "libretorrent_android_runtime"

_runtime_lock = threading.Lock()
_runtime_module: Any = None
_runtime_loaded = False


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


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def load_android_runtime() -> Optional[Any]:
    """加载 Android 适配模块；不可用时返回 None。

    优先走普通导入（宿主会把插件目录加入 sys.path）；失败则按本文件所在目录
    直接加载，保证在测试等未注入 sys.path 的场景下也能工作。整个模块的导入是
    安全的——它内部不会在导入期触碰 `java`。
    """
    global _runtime_module, _runtime_loaded
    if _runtime_loaded:
        return _runtime_module
    with _runtime_lock:
        if _runtime_loaded:
            return _runtime_module
        module: Any = None
        try:
            module = importlib.import_module(_ANDROID_RUNTIME_MODULE)
        except Exception:
            module = None
        if module is None:
            try:
                path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    f"{_ANDROID_RUNTIME_MODULE}.py",
                )
                spec = importlib.util.spec_from_file_location(_ANDROID_RUNTIME_MODULE, path)
                if spec is not None and spec.loader is not None:
                    candidate = importlib.util.module_from_spec(spec)
                    sys.modules.setdefault(_ANDROID_RUNTIME_MODULE, candidate)
                    spec.loader.exec_module(candidate)
                    module = candidate
            except Exception:
                module = None
        _runtime_module = module
        _runtime_loaded = True
        return _runtime_module


class LibreTorrentProvider(ProtocolProvider):
    """把磁力链接链式交给 LibreTorrent 的 Provider。"""

    # ---------- 配置 ----------

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = dict(payload or {})
        config["enabled"] = _as_bool(config.get("enabled"), True)
        config["package_name"] = _as_text(config.get("package_name")) or DEFAULT_PACKAGE_NAME
        return config

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # 本插件没有密文字段，直接回显归一化后的配置
        return self.normalize_config(config)

    # ---------- 状态 ----------

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """就绪状态。

        ``configured=False`` 只在**明确不具备 Android 运行环境**时返回（没有 Java 桥，
        例如桌面端）。一旦处于 Android 端，任何探测失败都保持 ``configured=True``：

        宿主前端会按 ``status.configured !== false`` 过滤可投递引擎，所以把「探测失败」
        报成「未配置」会让引擎从界面上静默消失，用户看到的是「没有配置下载引擎」——
        而配置其实是好的。探测问题应当作为 message 暴露，并在真正投递时给出精确错误。

        同理，探测不到 LibreTorrent 也不判为不可用：Android 11+ 的软件包可见性过滤会
        让已安装的应用同样查不到（``is_package_installed`` 因此设计成三态）。
        """
        normalized = self.normalize_config(config)
        runtime = load_android_runtime()
        if runtime is None:
            return {
                "configured": False,
                "message": "未找到 Android 适配模块，LibreTorrent 引擎只能在 Android 端使用",
                "missing_fields": [],
            }
        if not runtime.has_java_bridge():
            return {
                "configured": False,
                "message": runtime.unavailable_reason(),
                "missing_fields": [],
            }

        if runtime.android_context() is None:
            detail = ""
            try:
                detail = str(runtime.unavailable_reason() or "").strip()
            except Exception:
                detail = ""
            return {
                "configured": True,
                "message": (
                    "已启用，但未能获取 Android 上下文；仅影响状态探测，"
                    "投递时会给出具体错误。"
                    + (f"（{detail}）" if detail else "")
                ),
                "missing_fields": [],
            }

        installed = runtime.is_package_installed(normalized["package_name"])
        if installed is False:
            return {
                "configured": True,
                "message": (
                    f"未检测到 {normalized['package_name']}。"
                    "若已安装，可能是 Android 11+ 软件包可见性所致，"
                    "需在打包时声明 <queries>（见插件 README）。"
                ),
                "missing_fields": [],
            }
        return {"configured": True, "message": "", "missing_fields": []}

    # ---------- 执行 ----------

    def execute(
        self,
        capability: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_capability = _as_text(capability)
        if normalized_capability not in SUPPORTED_CAPABILITIES:
            raise ValueError(f"LibreTorrent 引擎不支持能力：{normalized_capability}")

        normalized = self.normalize_config(config)
        if not normalized["enabled"]:
            # download.* 不在宿主的 enabled 前置拦截名单里，插件必须自己把关
            raise RuntimeError("LibreTorrent 引擎未启用。")

        payload = dict(params or {})
        uri = self._resolve_uri(payload)

        runtime = load_android_runtime()
        if runtime is None:
            raise RuntimeError("LibreTorrent 引擎缺少 Android 适配模块，仅支持 Android 端。")

        result = runtime.start_download(uri, normalized["package_name"])

        # 宿主的投递接口会带 dir/out（子文件夹 / 重命名）。LibreTorrent 的投递入口
        # 只接收链接本身，落盘位置由它自己的设置决定——如实回报，不假装已生效。
        ignored: Dict[str, Any] = {}
        for key in ("dir", "out"):
            value = _as_text(payload.get(key))
            if value:
                ignored[key] = value
        if ignored:
            result["ignored_params"] = ignored
            result["warning"] = (
                "LibreTorrent 由它自己决定下载位置，本次请求中的 "
                + "、".join(sorted(ignored))
                + " 未生效；如需固定目录/番号文件夹，请在 LibreTorrent 应用内设置。"
            )
        return result

    # ---------- 内部 ----------

    @staticmethod
    def _resolve_uri(params: Dict[str, Any]) -> str:
        magnet = _as_text(params.get("magnet"))
        if magnet:
            return magnet
        raw_uris = params.get("uris")
        if isinstance(raw_uris, (list, tuple)):
            for item in raw_uris:
                text = _as_text(item)
                if text:
                    return text
        raise ValueError("缺少 magnet 或 uris 参数")
