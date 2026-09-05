import json
import os

from flask import Blueprint, current_app, request, session, jsonify

from core.config_paths import DEFAULT_SERVER_CONFIG, SERVER_CONFIG_PATH, _load_server_config
from core.storage_layout import SPACE_MODE_NORMAL
from infrastructure.logger import app_logger


auth_bp = Blueprint("auth", __name__)


def _get_auth_config():
    try:
        return (_load_server_config() or {}).get("auth", {}) or {}
    except Exception:
        return {}


def _save_server_config(config: dict) -> None:
    os.makedirs(os.path.dirname(SERVER_CONFIG_PATH) or ".", exist_ok=True)
    with open(SERVER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


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


def _is_normal_space() -> bool:
    return str(current_app.config.get("SPACE_MODE") or SPACE_MODE_NORMAL).strip() == SPACE_MODE_NORMAL


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


@auth_bp.route("/password", methods=["PUT"])
def update_password():
    """在 normal 空间更新项目密码；密码按项目当前约定明文保存。"""
    if not _is_normal_space():
        return jsonify({"code": 403, "msg": "当前空间不能修改项目密码", "data": None}), 403
    if is_auth_enabled() and not bool(session.get("authenticated", False)):
        return jsonify({"code": 401, "msg": "请先登录正常空间", "data": None}), 401

    payload = request.get_json(silent=True) or {}
    if "password" not in payload:
        return jsonify({"code": 400, "msg": "缺少新密码", "data": None}), 400

    password = str(payload.get("password") or "").strip()
    if not password:
        return jsonify({"code": 400, "msg": "新密码不能为空", "data": None}), 400

    server_config = _load_server_config() or {}
    if not isinstance(server_config, dict):
        server_config = dict(DEFAULT_SERVER_CONFIG)
    auth_config = server_config.setdefault("auth", {})
    if not isinstance(auth_config, dict):
        auth_config = {}
        server_config["auth"] = auth_config
    auth_config["enabled"] = True
    auth_config["password"] = password
    _save_server_config(server_config)
    session["authenticated"] = True
    app_logger.info("[auth] project password updated from %s", request.remote_addr)
    return jsonify({
        "code": 200,
        "msg": "密码已更新",
        "data": {"enabled": True, "authenticated": True, "mode": "normal"}
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
