from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from core.constants import SERVER_CONFIG_PATH

try:
    import rarfile  # type: ignore
except Exception:  # pragma: no cover
    rarfile = None


SUPPORTED_RAR_BACKEND_MODES = {"auto", "unrar", "7z", "bsdtar"}
DEFAULT_RAR_BACKEND_MODE = "auto"

_LAST_STATUS: Dict[str, Any] = {
    "enabled": False,
    "requested_mode": DEFAULT_RAR_BACKEND_MODE,
    "selected_mode": DEFAULT_RAR_BACKEND_MODE,
    "active_backend": "",
    "tools": {},
    "error": "",
}


def _load_server_config() -> Dict[str, Any]:
    try:
        path = Path(str(SERVER_CONFIG_PATH or "")).expanduser()
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_requested_mode() -> str:
    env_mode = str(os.environ.get("RAR_BACKEND_MODE", "")).strip().lower()
    if env_mode:
        return env_mode
    server_config = _load_server_config()
    storage = server_config.get("storage", {}) if isinstance(server_config, dict) else {}
    mode = str((storage or {}).get("rar_backend", "")).strip().lower()
    return mode or DEFAULT_RAR_BACKEND_MODE


def _resolve_tool_path(tool_name: str, env_var_name: str, windows_candidates: list[str]) -> Optional[str]:
    override = str(os.environ.get(env_var_name, "")).strip()
    if override:
        expanded = str(Path(override).expanduser())
        if Path(expanded).exists():
            return expanded

    resolved = shutil.which(tool_name)
    if resolved:
        return str(Path(resolved).resolve())

    if os.name == "nt":
        for raw in windows_candidates:
            candidate = Path(raw)
            if candidate.exists():
                return str(candidate.resolve())
    return None


def _discover_tools() -> Dict[str, str]:
    tools: Dict[str, str] = {}

    unrar_path = _resolve_tool_path(
        "unrar",
        "RAR_UNRAR_PATH",
        [
            r"C:\Program Files\WinRAR\UnRAR.exe",
            r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
        ],
    )
    if unrar_path:
        tools["unrar"] = unrar_path

    sevenzip_path = _resolve_tool_path(
        "7z",
        "RAR_7Z_PATH",
        [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ],
    )
    if sevenzip_path:
        tools["7z"] = sevenzip_path

    sevenzip2_path = _resolve_tool_path(
        "7zz",
        "RAR_7ZZ_PATH",
        [],
    )
    if sevenzip2_path:
        tools["7zz"] = sevenzip2_path

    bsdtar_path = _resolve_tool_path(
        "bsdtar",
        "RAR_BSDTAR_PATH",
        [
            r"C:\Windows\System32\tar.exe",
        ],
    )
    if bsdtar_path:
        tools["bsdtar"] = bsdtar_path

    return tools


def _apply_tool_paths(tools: Dict[str, str]) -> None:
    if rarfile is None:
        return
    if "unrar" in tools:
        rarfile.UNRAR_TOOL = tools["unrar"]
    if "7z" in tools:
        rarfile.SEVENZIP_TOOL = tools["7z"]
    if "7zz" in tools:
        rarfile.SEVENZIP2_TOOL = tools["7zz"]
    if "bsdtar" in tools:
        rarfile.BSDTAR_TOOL = tools["bsdtar"]


def _setup_backend(mode: str) -> str:
    if rarfile is None:
        return ""
    requested = str(mode or DEFAULT_RAR_BACKEND_MODE).strip().lower()
    if requested not in SUPPORTED_RAR_BACKEND_MODES:
        requested = DEFAULT_RAR_BACKEND_MODE

    if requested == "unrar":
        rarfile.tool_setup(unrar=True, unar=False, bsdtar=False, sevenzip=False, sevenzip2=False, force=True)
        return "unrar"
    if requested == "7z":
        rarfile.tool_setup(unrar=False, unar=False, bsdtar=False, sevenzip=True, sevenzip2=True, force=True)
        return "7z"
    if requested == "bsdtar":
        rarfile.tool_setup(unrar=False, unar=False, bsdtar=True, sevenzip=False, sevenzip2=False, force=True)
        return "bsdtar"

    # auto: 优先可读取 RAR 兼容性更好的 unrar/7z，再回退 bsdtar/unar。
    attempts = [
        ("unrar", dict(unrar=True, unar=False, bsdtar=False, sevenzip=False, sevenzip2=False)),
        ("7z", dict(unrar=False, unar=False, bsdtar=False, sevenzip=True, sevenzip2=True)),
        ("bsdtar", dict(unrar=False, unar=False, bsdtar=True, sevenzip=False, sevenzip2=False)),
        ("auto", dict(unrar=True, unar=True, bsdtar=True, sevenzip=True, sevenzip2=True)),
    ]
    for selected, kwargs in attempts:
        try:
            rarfile.tool_setup(force=True, **kwargs)
            return selected
        except Exception:
            continue
    return "failed"


def _resolve_active_backend_name() -> str:
    if rarfile is None:
        return ""
    setup = getattr(rarfile, "CURRENT_SETUP", None)
    setup_dict = getattr(setup, "setup", {}) if setup is not None else {}
    open_cmd = setup_dict.get("open_cmd") if isinstance(setup_dict, dict) else None
    token = str(open_cmd[0] or "").strip().upper() if isinstance(open_cmd, tuple) and open_cmd else ""
    mapping = {
        "UNRAR_TOOL": "unrar",
        "SEVENZIP_TOOL": "7z",
        "SEVENZIP2_TOOL": "7z",
        "BSDTAR_TOOL": "bsdtar",
        "UNAR_TOOL": "unar",
    }
    return mapping.get(token, token.lower())


def ensure_rar_backend_configured(logger=None, force: bool = False) -> Dict[str, Any]:
    global _LAST_STATUS

    if rarfile is None:
        _LAST_STATUS = {
            "enabled": False,
            "requested_mode": DEFAULT_RAR_BACKEND_MODE,
            "selected_mode": "disabled",
            "active_backend": "",
            "tools": {},
            "error": "rarfile not installed",
        }
        return dict(_LAST_STATUS)

    requested_mode = _resolve_requested_mode()
    if requested_mode not in SUPPORTED_RAR_BACKEND_MODES:
        requested_mode = DEFAULT_RAR_BACKEND_MODE

    tools = _discover_tools()
    _apply_tool_paths(tools)

    selected_mode = requested_mode
    error = ""

    current_setup = str(getattr(rarfile, "CURRENT_SETUP", "") or "").strip()
    if force or not current_setup:
        try:
            selected_mode = _setup_backend(requested_mode)
        except Exception as exc:
            error = str(exc)
            if requested_mode != DEFAULT_RAR_BACKEND_MODE:
                try:
                    selected_mode = _setup_backend(DEFAULT_RAR_BACKEND_MODE)
                    if error:
                        error = f"{error} | fallback=auto"
                except Exception as fallback_exc:
                    error = f"{error} | fallback_failed={fallback_exc}"
                    selected_mode = "failed"
            else:
                selected_mode = "failed"

    active_backend = _resolve_active_backend_name()
    enabled = bool(active_backend)

    _LAST_STATUS = {
        "enabled": enabled,
        "requested_mode": requested_mode,
        "selected_mode": selected_mode,
        "active_backend": active_backend,
        "tools": tools,
        "error": error,
    }

    if logger is not None:
        logger.info(
            f"RAR backend configured: requested={requested_mode} selected={selected_mode} active={active_backend or '<none>'}"
        )
        if error:
            logger.warning(f"RAR backend setup warning: {error}")

    return dict(_LAST_STATUS)


def get_rar_backend_status() -> Dict[str, Any]:
    return dict(_LAST_STATUS)
