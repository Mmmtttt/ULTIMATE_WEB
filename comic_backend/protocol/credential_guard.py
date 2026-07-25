"""
Protocol-level credential validation helpers for plugin configuration.

Validation rules are read from each plugin's ultimate-plugin.json under
configuration.credential. No plugin-specific hardcoding in this file.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .registry import get_plugin_registry


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


def _get_nested_value(config: Dict, field_path: str):
    current = config
    for part in field_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _find_plugin_manifest(adapter_name: str):
    adapter_key = _normalize_text(adapter_name).lower()
    if not adapter_key:
        return None
    try:
        registry = get_plugin_registry()
    except Exception:
        return None
    return registry.find_by_config_key(adapter_key)


def _get_credential_config(manifest) -> Dict:
    if manifest is None:
        return {}
    configuration = getattr(manifest, "configuration", None) or {}
    if not isinstance(configuration, dict):
        return {}
    cred = configuration.get("credential") or {}
    return cred if isinstance(cred, dict) else {}


def get_adapter_credential_status(adapter_name: str, adapter_config: Dict) -> Dict[str, object]:
    adapter_key = _normalize_text(adapter_name).lower()
    config = dict(adapter_config or {})
    manifest = _find_plugin_manifest(adapter_key)
    cred_cfg = _get_credential_config(manifest)

    enabled_field = str(cred_cfg.get("enabled_field") or "enabled").strip() or "enabled"
    enabled = _as_enabled(config.get(enabled_field, True))

    plugin_label = ""
    if manifest is not None:
        plugin_label = _normalize_text(getattr(manifest, "name", "") or "") or adapter_key
    if not plugin_label:
        plugin_label = adapter_key

    if not enabled:
        disabled_message = str(cred_cfg.get("disabled_message") or "").strip()
        if not disabled_message:
            disabled_message = f"{plugin_label} 未启用，不能使用该平台查询。"
        return {
            "configured": False,
            "message": disabled_message,
            "missing_fields": [enabled_field],
        }

    required_fields = cred_cfg.get("required_fields") or []
    if not isinstance(required_fields, list):
        required_fields = []

    missing = []
    for field in required_fields:
        field_name = str(field or "").strip()
        if not field_name:
            continue
        value = _get_nested_value(config, field_name)
        if _looks_unconfigured(value):
            missing.append(field_name)

    configured = len(missing) == 0
    unconfigured_message = str(cred_cfg.get("unconfigured_message") or "").strip()
    if not unconfigured_message and not configured:
        unconfigured_message = f"{plugin_label} 配置不完整，不能使用该平台查询。"

    return {
        "configured": configured,
        "message": "" if configured else unconfigured_message,
        "missing_fields": missing,
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
