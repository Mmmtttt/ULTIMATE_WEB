from __future__ import annotations

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.teledrive_app_service import (
    TeleDriveBridgeError,
    TeleDriveAppService,
    get_teledrive_app_service,
)
from infrastructure.logger import app_logger, error_logger


teledrive_bp = Blueprint("teledrive", __name__)


def success_response(data=None, msg="成功"):
    return jsonify({
        "code": 200,
        "msg": msg,
        "data": data,
    })


def error_response(code, msg, data=None):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": data,
    })


def _service() -> TeleDriveAppService:
    return get_teledrive_app_service()


def _json_payload():
    return request.get_json(silent=True) or {}


def _handle_bridge_error(exc: TeleDriveBridgeError):
    return error_response(exc.status_code, str(exc), exc.response_data)


def _extract_upstream_error(response, fallback: str):
    payload = None
    message = fallback
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        raw_error = payload.get("error")
        if isinstance(raw_error, dict):
            message = str(raw_error.get("message") or raw_error.get("code") or message)
        elif raw_error:
            message = str(raw_error)
        elif payload.get("message"):
            message = str(payload.get("message"))
    return message, payload


@teledrive_bp.route("/status", methods=["GET"])
def get_status():
    try:
        return success_response(_service().get_status())
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive status failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/imports/preview", methods=["POST"])
def preview_import():
    try:
        result = _service().import_once(_json_payload(), dry_run=True)
        app_logger.info("TeleDrive import preview completed")
        return success_response(result)
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive import preview failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/imports", methods=["POST"])
def run_import():
    try:
        result = _service().import_once(_json_payload(), dry_run=False)
        app_logger.info("TeleDrive import completed")
        return success_response(result)
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive import failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/catalog", methods=["GET"])
def get_catalog():
    try:
        return success_response(_service().get_catalog(request.args.to_dict(flat=True)))
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive catalog failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/tree", methods=["GET"])
def get_tree():
    try:
        root = request.args.get("root") or "/"
        limit = request.args.get("limit", type=int) or 10000
        return success_response(_service().get_tree(root, limit=limit))
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive tree failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/library-sync/preview", methods=["POST"])
def preview_library_sync():
    try:
        result = _service().sync_library(_json_payload(), dry_run=True)
        app_logger.info("TeleDrive library sync preview completed")
        return success_response(result)
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive library sync preview failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/library-sync", methods=["POST"])
def run_library_sync():
    try:
        result = _service().sync_library(_json_payload(), dry_run=False)
        app_logger.info("TeleDrive library sync completed")
        return success_response(result)
    except TeleDriveBridgeError as exc:
        return _handle_bridge_error(exc)
    except Exception as exc:
        error_logger.error(f"TeleDrive library sync failed: {exc}")
        return error_response(500, "服务器内部错误")


@teledrive_bp.route("/files/<path:file_id>/content", methods=["GET", "HEAD"])
def proxy_file_content(file_id):
    service = _service()
    upstream = None
    try:
        upstream = service.proxy_file_content(
            file_id,
            method=request.method,
            query_string=request.query_string.decode("utf-8", errors="ignore"),
            incoming_headers=request.headers,
        )
        headers = service.filter_headers(upstream.headers, service.STREAM_RESPONSE_HEADERS)
        status_code = int(getattr(upstream, "status_code", 200) or 200)
        if status_code >= 400 and status_code != 416 and request.method != "HEAD":
            message, payload = _extract_upstream_error(
                upstream,
                f"TeleDrive Bridge returned HTTP {status_code}",
            )
            service.close_response(upstream)
            return error_response(status_code, message, payload), status_code

        if request.method == "HEAD":
            service.close_response(upstream)
            return Response(status=status_code, headers=headers)

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        yield chunk
            finally:
                service.close_response(upstream)

        return Response(
            stream_with_context(generate()),
            status=status_code,
            headers=headers,
            direct_passthrough=True,
        )
    except TeleDriveBridgeError as exc:
        if upstream is not None:
            service.close_response(upstream)
        return Response(str(exc), status=exc.status_code, content_type="text/plain; charset=utf-8")
    except Exception as exc:
        if upstream is not None:
            service.close_response(upstream)
        error_logger.error(f"TeleDrive file proxy failed: {exc}")
        return Response("Internal Server Error", status=500, content_type="text/plain; charset=utf-8")
