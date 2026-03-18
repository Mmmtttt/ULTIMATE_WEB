from flask import Blueprint, jsonify, request, send_file

from application.sync_app_service import SyncAppService
from infrastructure.logger import error_logger


sync_bp = Blueprint("sync", __name__)
sync_service = SyncAppService()


def success_response(data=None, msg="success"):
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


@sync_bp.route("/session", methods=["POST"])
def create_session():
    try:
        payload = request.get_json(silent=True) or {}
        session = sync_service.create_session(payload)
        return success_response({
            "session_id": session["session_id"],
            "schema_version": session.get("schema_version", 1),
            "status": session.get("status", "open"),
            "created_at": session.get("created_at"),
            "expires_at": session.get("expires_at"),
            "manifest_path": f"/api/v1/sync/manifest/{session['session_id']}",
            "packages": session.get("packages", []),
        })
    except Exception as exc:
        error_logger.error(f"sync create session failed: {exc}")
        return error_response(500, "create sync session failed")


@sync_bp.route("/manifest/<session_id>", methods=["GET"])
def get_manifest(session_id):
    try:
        manifest = sync_service.get_manifest(str(session_id or "").strip())
        if not manifest:
            return error_response(404, "session not found or expired")
        return success_response(manifest)
    except Exception as exc:
        error_logger.error(f"sync get manifest failed: {exc}")
        return error_response(500, "get sync manifest failed")


@sync_bp.route("/download/<session_id>/<path:package_name>", methods=["GET"])
def download_package(session_id, package_name):
    try:
        package = sync_service.resolve_package(
            str(session_id or "").strip(),
            str(package_name or "").strip(),
        )
        if not package:
            return error_response(404, "package not found")
        return send_file(
            package["path"],
            as_attachment=True,
            download_name=package["name"],
            mimetype="application/zip",
        )
    except Exception as exc:
        error_logger.error(f"sync download package failed: {exc}")
        return error_response(500, "download package failed")


@sync_bp.route("/session/finish", methods=["POST"])
def finish_session():
    try:
        payload = request.get_json(silent=True) or {}
        if not str(payload.get("session_id", "")).strip():
            return error_response(400, "session_id is required")
        result = sync_service.finish_session(payload)
        if not result:
            return error_response(404, "session not found or expired")
        return success_response(result)
    except Exception as exc:
        error_logger.error(f"sync finish session failed: {exc}")
        return error_response(500, "finish sync session failed")


@sync_bp.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    try:
        session = sync_service.get_session(str(session_id or "").strip())
        if not session:
            return error_response(404, "session not found or expired")
        return success_response(session)
    except Exception as exc:
        error_logger.error(f"sync get session failed: {exc}")
        return error_response(500, "get sync session failed")
