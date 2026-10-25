"""引用式入库的接口层。

只做三件事：列出谁能同步、预览一次扫描、真的并进预览库。
字节不在这里流动——播放时由各插件自己的 playback.* 通道现取。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from application.remote_library_service import get_remote_library_service
from infrastructure.logger import error_logger

library_sync_bp = Blueprint("library_sync", __name__)


def _ok(data):
    return jsonify({"code": 200, "data": data, "msg": "成功"})


def _fail(message: str, status: int = 400):
    return jsonify({"code": status, "data": None, "msg": str(message)}), status


@library_sync_bp.route("/plugins", methods=["GET"])
def list_plugins():
    """列出声明了 library.sync.apply 的插件。"""
    try:
        return _ok({"plugins": get_remote_library_service().list_sync_plugins()})
    except Exception as exc:
        error_logger.error(f"列出可同步插件失败: {exc}", exc_info=True)
        return _fail(f"列出可同步插件失败: {exc}", 500)


def _plugin_id_from_request() -> str:
    payload = request.get_json(silent=True) or {}
    plugin_id = str(payload.get("plugin_id") or request.args.get("plugin_id") or "").strip()
    return plugin_id


@library_sync_bp.route("/preview", methods=["POST"])
def preview_sync():
    """只扫描、只报告，不写库。"""
    plugin_id = _plugin_id_from_request()
    if not plugin_id:
        return _fail("缺少 plugin_id。")
    try:
        return _ok(get_remote_library_service().sync(plugin_id, dry_run=True))
    except Exception as exc:
        error_logger.error(f"预览入库失败 plugin={plugin_id}: {exc}", exc_info=True)
        return _fail(f"预览入库失败: {exc}", 500)


@library_sync_bp.route("", methods=["POST"])
@library_sync_bp.route("/apply", methods=["POST"])
def apply_sync():
    """真的并进预览库。"""
    plugin_id = _plugin_id_from_request()
    if not plugin_id:
        return _fail("缺少 plugin_id。")
    try:
        return _ok(get_remote_library_service().sync(plugin_id, dry_run=False))
    except Exception as exc:
        error_logger.error(f"执行入库失败 plugin={plugin_id}: {exc}", exc_info=True)
        return _fail(f"执行入库失败: {exc}", 500)
