from flask import Blueprint, jsonify, request

from application.database_organize_service import DatabaseOrganizeService
from infrastructure.logger import error_logger

organize_bp = Blueprint("organize", __name__)
organize_service = DatabaseOrganizeService()


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


@organize_bp.route("/options", methods=["GET"])
def get_organize_options():
    try:
        mode = request.args.get("mode", "comic")
        result = organize_service.get_options(mode)
        if result.success:
            return success_response(result.data, result.message)
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"Get organize options failed: {e}")
        return error_response(500, "internal server error")


@organize_bp.route("/run", methods=["POST"])
def run_organize_action():
    try:
        payload = request.json or {}
        mode = payload.get("mode", "comic")
        action = payload.get("action", "")
        if not action:
            return error_response(400, "missing parameter: action")

        result = organize_service.run(mode, action)
        if result.success:
            return success_response(result.data, result.message)
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"Run organize action failed: {e}")
        return error_response(500, "internal server error")
