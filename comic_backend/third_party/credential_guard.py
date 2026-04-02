"""
第三方平台凭据校验工具
"""

from __future__ import annotations

from typing import Dict, List, Tuple


_PLACEHOLDER_TEXTS = (
    "请输入",
    "请填写",
    "your_",
    "your ",
    "example",
    "示例",
    "changeme",
)


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _looks_unconfigured(value) -> bool:
    text = _normalize_text(value)
    if not text:
        return True

    lower_text = text.lower()
    if lower_text in {"none", "null", "undefined"}:
        return True

    for token in _PLACEHOLDER_TEXTS:
        if token in lower_text or token in text:
            return True
    return False


def _as_enabled(raw_value) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    text = _normalize_text(raw_value).lower()
    if text in {"0", "false", "off", "no"}:
        return False
    if text in {"1", "true", "on", "yes"}:
        return True
    return True


def get_adapter_credential_status(adapter_name: str, adapter_config: Dict) -> Dict[str, object]:
    adapter_key = _normalize_text(adapter_name).lower()
    config = dict(adapter_config or {})
    enabled = _as_enabled(config.get("enabled", True))

    if adapter_key == "jmcomic":
        if not enabled:
            return {
                "configured": False,
                "message": "JM 平台未启用，不能使用该平台查询。",
                "missing_fields": ["enabled"],
            }
        missing = []
        if _looks_unconfigured(config.get("username")):
            missing.append("username")
        if _looks_unconfigured(config.get("password")):
            missing.append("password")
        configured = len(missing) == 0
        return {
            "configured": configured,
            "message": "" if configured else "JM 平台未配置账号或密码，不能使用该平台查询。",
            "missing_fields": missing,
        }

    if adapter_key == "picacomic":
        if not enabled:
            return {
                "configured": False,
                "message": "PK 平台未启用，不能使用该平台查询。",
                "missing_fields": ["enabled"],
            }
        missing = []
        if _looks_unconfigured(config.get("account")):
            missing.append("account")
        if _looks_unconfigured(config.get("password")):
            missing.append("password")
        configured = len(missing) == 0
        return {
            "configured": configured,
            "message": "" if configured else "PK 平台未配置账号或密码，不能使用该平台查询。",
            "missing_fields": missing,
        }

    if adapter_key == "javdb":
        if not enabled:
            return {
                "configured": False,
                "message": "JAVDB 平台未启用，不能使用该平台查询。",
                "missing_fields": ["enabled"],
            }
        cookies = config.get("cookies") or {}
        if not isinstance(cookies, dict):
            cookies = {}
        session_cookie = _normalize_text(cookies.get("_jdb_session"))
        configured = not _looks_unconfigured(session_cookie)
        return {
            "configured": configured,
            "message": "" if configured else "JAVDB 平台未配置 cookie（_jdb_session），不能使用该平台查询。",
            "missing_fields": [] if configured else ["cookies._jdb_session"],
        }

    return {
        "configured": True,
        "message": "",
        "missing_fields": [],
    }


def ensure_adapter_query_ready(adapter_name: str, adapter_config: Dict) -> None:
    status = get_adapter_credential_status(adapter_name, adapter_config)
    if not bool(status.get("configured", False)):
        raise RuntimeError(str(status.get("message") or "平台配置不完整，不能执行查询"))


def filter_configured_adapters(adapter_configs: Dict[str, Dict]) -> Tuple[List[str], Dict[str, str]]:
    configured: List[str] = []
    errors: Dict[str, str] = {}
    for adapter_name, adapter_config in (adapter_configs or {}).items():
        status = get_adapter_credential_status(adapter_name, adapter_config or {})
        if bool(status.get("configured", False)):
            configured.append(adapter_name)
        else:
            errors[adapter_name] = str(status.get("message") or "平台配置不完整")
    return configured, errors
