import os
from typing import Optional


RUNTIME_PROFILE_FULL = "full"
RUNTIME_PROFILE_MOBILE_CORE = "mobile_core"

_RUNTIME_PROFILE_ENV_KEYS = (
    "BACKEND_RUNTIME_PROFILE",
    "ULTIMATE_RUNTIME_PROFILE",
    "DEPLOYMENT_RUNTIME_PROFILE",
)

_THIRD_PARTY_ENABLE_ENV_KEYS = (
    "BACKEND_ENABLE_THIRD_PARTY",
    "ULTIMATE_ENABLE_THIRD_PARTY",
)

_TRUTHY = {"1", "true", "yes", "on", "enable", "enabled"}
_FALSY = {"0", "false", "no", "off", "disable", "disabled"}


def _read_env_value(keys) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _normalize_runtime_profile(raw_profile: Optional[str]) -> str:
    normalized = str(raw_profile or "").strip().lower()
    if normalized in {"mobile_core", "mobile", "android", "apk"}:
        return RUNTIME_PROFILE_MOBILE_CORE
    return RUNTIME_PROFILE_FULL


def get_runtime_profile() -> str:
    return _normalize_runtime_profile(_read_env_value(_RUNTIME_PROFILE_ENV_KEYS))


def is_mobile_core_profile() -> bool:
    return get_runtime_profile() == RUNTIME_PROFILE_MOBILE_CORE


def _parse_bool_flag(raw_value: Optional[str]) -> Optional[bool]:
    if raw_value is None:
        return None
    lowered = str(raw_value).strip().lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    return None


def is_third_party_enabled() -> bool:
    explicit_flag = _parse_bool_flag(_read_env_value(_THIRD_PARTY_ENABLE_ENV_KEYS))
    if explicit_flag is not None:
        return explicit_flag
    return get_runtime_profile() == RUNTIME_PROFILE_FULL


def runtime_capabilities() -> dict:
    runtime_profile = get_runtime_profile()
    third_party_enabled = is_third_party_enabled()
    return {
        "runtime_profile": runtime_profile,
        "third_party_enabled": third_party_enabled,
        "mobile_core": runtime_profile == RUNTIME_PROFILE_MOBILE_CORE,
    }
