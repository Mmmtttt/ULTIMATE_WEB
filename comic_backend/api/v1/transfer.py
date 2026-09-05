from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from application.lan_transfer_app_service import LanTransferAppService
from infrastructure.logger import error_logger

transfer_bp = Blueprint("transfer", __name__)
transfer_service = LanTransferAppService()


def success_response(data=None):
    return jsonify({"code": 200, "msg": "成功", "data": data})


def error_response(code, msg):
    return jsonify({"code": code, "msg": msg, "data": None})


@transfer_bp.route("/items", methods=["GET"])
def list_items():
    try:
        result = transfer_service.list_items()
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"局域网传输列表接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@transfer_bp.route("/text", methods=["POST"])
def publish_text():
    try:
        payload = request.get_json(silent=True) or {}
        result = transfer_service.publish_text(payload.get("text", ""), payload.get("name", ""))
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"局域网发布文字接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@transfer_bp.route("/server-file", methods=["POST"])
def register_server_file():
    try:
        payload = request.get_json(silent=True) or {}
        result = transfer_service.register_server_file(payload.get("path", ""), payload.get("name", ""))
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"局域网登记服务器文件接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@transfer_bp.route("/upload", methods=["POST"])
def upload_file():
    try:
        uploaded_file = request.files.get("file")
        result = transfer_service.save_upload(uploaded_file)
        if result.success:
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"局域网上传文件接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@transfer_bp.route("/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    try:
        result = transfer_service.delete_item(item_id)
        if result.success:
            return success_response(result.data)
        return error_response(404, result.message)
    except Exception as exc:
        error_logger.error(f"局域网删除传输项接口失败: {exc}")
        return error_response(500, "服务器内部错误")


@transfer_bp.route("/download/<item_id>", methods=["GET"])
def download_item(item_id):
    try:
        result = transfer_service.resolve_download(item_id)
        if not result.success:
            return error_response(404, result.message)
        payload = result.data or {}
        if payload.get("kind") == "text":
            stream = BytesIO(str(payload.get("content") or "").encode("utf-8"))
            return send_file(
                stream,
                as_attachment=True,
                download_name=payload.get("name") or "shared-text.txt",
                mimetype=payload.get("mime_type") or "text/plain; charset=utf-8",
            )
        return send_file(
            payload["path"],
            as_attachment=True,
            download_name=payload.get("name") or "download",
            mimetype=payload.get("mime_type") or "application/octet-stream",
        )
    except Exception as exc:
        error_logger.error(f"局域网下载传输项接口失败: {exc}")
        return error_response(500, "服务器内部错误")
