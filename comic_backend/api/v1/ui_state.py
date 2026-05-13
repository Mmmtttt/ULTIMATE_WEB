from flask import Blueprint, jsonify, request

from application.ui_state_app_service import UiStateAppService
from infrastructure.logger import error_logger

ui_state_bp = Blueprint("ui_state", __name__)
ui_state_service = UiStateAppService()


def success_response(data=None, msg="成功"):
    return jsonify({
        "code": 200,
        "msg": msg,
        "data": data,
    })


def error_response(code, msg):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None,
    })


@ui_state_bp.route("", methods=["GET"])
def get_ui_state():
    try:
        client_id = request.args.get("client_id")
        scope = request.args.get("scope")
        result = ui_state_service.get_state(client_id, scope)
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"获取 UI 状态失败: {exc}")
        return error_response(500, "服务器内部错误")


@ui_state_bp.route("", methods=["PUT"])
def save_ui_state():
    try:
        payload = request.get_json(silent=True) or {}
        result = ui_state_service.save_state(
            payload.get("client_id"),
            payload.get("scope"),
            payload.get("state"),
        )
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"保存 UI 状态失败: {exc}")
        return error_response(500, "服务器内部错误")


@ui_state_bp.route("", methods=["DELETE"])
def delete_ui_state():
    try:
        payload = request.get_json(silent=True) or {}
        client_id = payload.get("client_id") or request.args.get("client_id")
        scope = payload.get("scope") or request.args.get("scope")
        result = ui_state_service.delete_state(client_id, scope)
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"删除 UI 状态失败: {exc}")
        return error_response(500, "服务器内部错误")
