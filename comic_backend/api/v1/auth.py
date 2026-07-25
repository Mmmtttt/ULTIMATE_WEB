from flask import Blueprint, request, session, jsonify

from infrastructure.logger import app_logger


auth_bp = Blueprint("auth", __name__)


def _get_auth_config():
    try:
        from core.config_paths import _load_server_config
        return (_load_server_config() or {}).get("auth", {}) or {}
    except Exception:
        return {}


def is_auth_enabled() -> bool:
    cfg = _get_auth_config()
    return bool(cfg.get("enabled", False))


def get_correct_password() -> str:
    cfg = _get_auth_config()
    return str(cfg.get("password", "") or "").strip()


def is_authenticated() -> bool:
    if not is_auth_enabled():
        return True
    return bool(session.get("authenticated", False))


@auth_bp.route("/login", methods=["POST"])
def login():
    """登录接口 - 校验密码，设置 session"""
    if not is_auth_enabled():
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {"authenticated": True, "mode": "normal"}
        })

    try:
        payload = request.get_json(silent=True) or {}
        password = str(payload.get("password", "") or "").strip()
    except Exception:
        password = ""

    correct = get_correct_password()
    authenticated = correct and password == correct

    if authenticated:
        session["authenticated"] = True
        app_logger.info("[auth] login success from %s", request.remote_addr)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {"authenticated": True, "mode": "normal"}
        })
    else:
        # 密码错误 - 静默失败，返回 "private" 模式
        session["authenticated"] = False
        app_logger.info("[auth] login failed from %s", request.remote_addr)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {"authenticated": False, "mode": "private"}
        })


@auth_bp.route("/status", methods=["GET"])
def status():
    """查询当前认证状态"""
    if not is_auth_enabled():
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {"enabled": False, "authenticated": True, "mode": "normal"}
        })

    authenticated = bool(session.get("authenticated", False))
    mode = "normal" if authenticated else "private"
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {
            "enabled": True,
            "authenticated": authenticated,
            "mode": mode
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """退出登录 - 回到隐私模式"""
    if is_auth_enabled():
        session["authenticated"] = False
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": {"authenticated": False, "mode": "private"}
    })
