from flask import Blueprint, jsonify, request

from application.reading_history_app_service import ReadingHistoryAppService
from infrastructure.logger import error_logger

history_bp = Blueprint("history", __name__)
history_service = ReadingHistoryAppService()


def success_response(data=None):
    return jsonify({"code": 200, "msg": "成功", "data": data})


def error_response(code, msg):
    return jsonify({"code": code, "msg": msg, "data": None})


@history_bp.route("/list", methods=["GET"])
def list_history():
    try:
        content_type = request.args.get("content_type", "comic")
        result = history_service.list_history(content_type)
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"读取阅读记录接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@history_bp.route("/visit", methods=["POST"])
def record_visit():
    try:
        data = request.json or {}
        content_type = data.get("content_type")
        content_id = data.get("content_id") or data.get("id")
        source = data.get("source", "local")
        result = history_service.record_visit(content_type, content_id, source)
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"写入阅读记录接口失败: {exc}")
        return error_response(500, "服务器内部错误")
