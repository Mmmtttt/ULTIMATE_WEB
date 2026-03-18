from functools import wraps

from core.runtime_profile import get_runtime_profile, is_third_party_enabled


THIRD_PARTY_DISABLED_MESSAGE = "third-party integration is disabled in current runtime profile"


def third_party_disabled_message() -> str:
    return f"{THIRD_PARTY_DISABLED_MESSAGE}: {get_runtime_profile()}"


def third_party_unavailable_response(error_response, status_code: int = 503):
    return error_response(status_code, third_party_disabled_message())


def require_third_party(error_response, status_code: int = 503):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not is_third_party_enabled():
                return third_party_unavailable_response(error_response, status_code=status_code)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
