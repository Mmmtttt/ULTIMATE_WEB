import os
import tempfile

from flask import Blueprint, after_this_request, jsonify, request, send_file

from application.sync_app_service import SyncAppService
from application.sync_directional_service import DirectionalSyncService
from infrastructure.logger import error_logger


sync_bp = Blueprint("sync", __name__)
sync_service = SyncAppService()
directional_service = DirectionalSyncService()


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


def _extract_sync_token(payload=None):
    token = str(request.headers.get("X-Sync-Token", "")).strip()
    if token:
        return token
    if isinstance(payload, dict):
        token = str(payload.get("auth_token", "")).strip()
    return token


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


@sync_bp.route("/pairing/invite", methods=["POST"])
def create_pairing_invite():
    try:
        payload = request.get_json(silent=True) or {}
        invite = directional_service.create_invite(payload)
        return success_response(invite)
    except Exception as exc:
        error_logger.error(f"sync create pairing invite failed: {exc}")
        return error_response(500, "create pairing invite failed")


@sync_bp.route("/pairing/claim", methods=["POST"])
def claim_pairing_invite():
    try:
        payload = request.get_json(silent=True) or {}
        result = directional_service.claim_invite(payload)
        if not result:
            return error_response(404, "pairing code invalid or expired")
        return success_response(result)
    except Exception as exc:
        error_logger.error(f"sync claim pairing invite failed: {exc}")
        return error_response(500, "claim pairing invite failed")


@sync_bp.route("/pairing/connect", methods=["POST"])
def connect_pairing():
    try:
        payload = request.get_json(silent=True) or {}
        peer = directional_service.connect_peer(payload)
        return success_response(peer)
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"sync connect pairing failed: {exc}")
        return error_response(500, "connect pairing failed")


@sync_bp.route("/peers", methods=["GET"])
def list_peers():
    try:
        return success_response(directional_service.list_peers())
    except Exception as exc:
        error_logger.error(f"sync list peers failed: {exc}")
        return error_response(500, "list peers failed")


@sync_bp.route("/peers/<peer_id>", methods=["DELETE"])
def remove_peer(peer_id):
    try:
        ok = directional_service.remove_peer(str(peer_id or "").strip())
        if not ok:
            return error_response(404, "peer not found")
        return success_response({"peer_id": peer_id, "removed": True})
    except Exception as exc:
        error_logger.error(f"sync remove peer failed: {exc}")
        return error_response(500, "remove peer failed")


@sync_bp.route("/directional/inventory", methods=["GET"])
def directional_inventory():
    try:
        token = _extract_sync_token()
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")
        return success_response(directional_service.inventory())
    except Exception as exc:
        error_logger.error(f"sync directional inventory failed: {exc}")
        return error_response(500, "directional inventory failed")


@sync_bp.route("/directional/assets/inventory", methods=["GET"])
def directional_assets_inventory():
    try:
        token = _extract_sync_token()
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")
        return success_response(directional_service.asset_inventory())
    except Exception as exc:
        error_logger.error(f"sync directional assets inventory failed: {exc}")
        return error_response(500, "directional assets inventory failed")


@sync_bp.route("/directional/assets/apply", methods=["POST"])
def directional_assets_apply():
    try:
        token = _extract_sync_token()
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")

        package = request.files.get("package")
        if package is None:
            return error_response(400, "package file is required")

        fd, temp_path = tempfile.mkstemp(prefix="sync_assets_apply_", suffix=".zip")
        os.close(fd)
        package.save(temp_path)
        try:
            result = directional_service.apply_asset_zip_file(temp_path)
        finally:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        return success_response(result)
    except Exception as exc:
        error_logger.error(f"sync directional assets apply failed: {exc}")
        return error_response(500, "directional assets apply failed")


@sync_bp.route("/directional/assets/delta/download", methods=["GET", "POST"])
def directional_assets_delta_download():
    try:
        payload = request.get_json(silent=True) or {}
        token = _extract_sync_token(payload)
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")

        known_files = payload.get("known_files", {})
        delta = directional_service.build_asset_delta_zip(known_files if isinstance(known_files, dict) else {})
        zip_path = str(delta.get("zip_path", "")).strip()
        file_count = int(delta.get("file_count", 0))
        if not zip_path or file_count <= 0:
            return ("", 204)

        @after_this_request
        def _cleanup(response):
            try:
                if os.path.isfile(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass
            return response

        return send_file(
            zip_path,
            as_attachment=True,
            download_name="assets_delta.zip",
            mimetype="application/zip",
        )
    except Exception as exc:
        error_logger.error(f"sync directional assets delta download failed: {exc}")
        return error_response(500, "directional assets delta download failed")


@sync_bp.route("/directional/estimate", methods=["POST"])
def directional_estimate():
    try:
        payload = request.get_json(silent=True) or {}
        token = _extract_sync_token(payload)
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")
        known_inventory = payload.get("known_inventory", {})
        known_files = payload.get("known_files", {})
        result = directional_service.estimate_delta_for_known(
            known_inventory if isinstance(known_inventory, dict) else {},
            known_files if isinstance(known_files, dict) else {},
        )
        return success_response(result)
    except Exception as exc:
        error_logger.error(f"sync directional estimate failed: {exc}")
        return error_response(500, "directional estimate failed")


@sync_bp.route("/directional/preview", methods=["POST"])
def directional_preview():
    try:
        payload = request.get_json(silent=True) or {}
        peer_id = str(payload.get("peer_id", "")).strip()
        direction = str(payload.get("direction", "")).strip().lower()
        if not peer_id:
            return error_response(400, "peer_id is required")
        if direction not in {"push", "pull"}:
            return error_response(400, "direction must be push or pull")
        result = directional_service.estimate_peer_sync(peer_id, direction)
        return success_response(result)
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"sync directional preview failed: {exc}")
        return error_response(500, "directional preview failed")


@sync_bp.route("/directional/delta", methods=["POST"])
def directional_delta():
    try:
        payload = request.get_json(silent=True) or {}
        token = _extract_sync_token(payload)
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")
        known_inventory = payload.get("known_inventory", {})
        return success_response(directional_service.delta_from_known(known_inventory))
    except Exception as exc:
        error_logger.error(f"sync directional delta failed: {exc}")
        return error_response(500, "directional delta failed")


@sync_bp.route("/directional/apply", methods=["POST"])
def directional_apply():
    try:
        payload = request.get_json(silent=True) or {}
        token = _extract_sync_token(payload)
        peer = directional_service.verify_token(token)
        if not peer:
            return error_response(401, "invalid sync token")
        result = directional_service.apply_delta(payload)
        return success_response(result)
    except Exception as exc:
        error_logger.error(f"sync directional apply failed: {exc}")
        return error_response(500, "directional apply failed")


@sync_bp.route("/directional/push", methods=["POST"])
def directional_push():
    try:
        payload = request.get_json(silent=True) or {}
        peer_id = str(payload.get("peer_id", "")).strip()
        if not peer_id:
            return error_response(400, "peer_id is required")
        result = directional_service.push_to_peer(peer_id)
        return success_response(result)
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"sync directional push failed: {exc}")
        return error_response(500, "directional push failed")


@sync_bp.route("/directional/pull", methods=["POST"])
def directional_pull():
    try:
        payload = request.get_json(silent=True) or {}
        peer_id = str(payload.get("peer_id", "")).strip()
        if not peer_id:
            return error_response(400, "peer_id is required")
        result = directional_service.pull_from_peer(peer_id)
        return success_response(result)
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"sync directional pull failed: {exc}")
        return error_response(500, "directional pull failed")
