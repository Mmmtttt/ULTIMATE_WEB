"""下载能力 API 路由（磁力链接下载）。

调用声明 `download.*` 能力的第三方插件（如 Aria2）：
- GET    /api/v1/download/engines        列出可用下载引擎
- POST   /api/v1/download/magnet         投递磁力链接到下载引擎
- GET    /api/v1/download/task           按 gid 查询任务状态
- GET    /api/v1/download/tasks          查询任务列表
- POST   /api/v1/download/task/pause     暂停任务
- POST   /api/v1/download/task/resume    继续任务
- POST   /api/v1/download/task/remove    删除任务
"""
from flask import Blueprint, request, jsonify

from infrastructure.logger import error_logger
from protocol.host_service import get_protocol_host_service
from .runtime_guard import require_third_party

download_bp = Blueprint('download', __name__)


def success_response(data=None, msg="成功"):
    return jsonify({
        "code": 200,
        "msg": msg,
        "data": data
    })


def error_response(code, msg):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None
    })


def _host_service():
    return get_protocol_host_service()


@download_bp.route('/engines', methods=['GET'])
@require_third_party(error_response)
def list_engines():
    """列出声明了 download.magnet.add 能力的下载引擎及其就绪状态。"""
    try:
        engines = _host_service().list_download_engines()
    except Exception as exc:
        error_logger.error(f"download engines list failed: {exc}")
        return error_response(500, f"获取下载引擎失败: {exc}")
    return success_response({"engines": engines})


@download_bp.route('/magnet', methods=['POST'])
@require_third_party(error_response)
def add_magnet():
    """投递磁力链接到下载引擎。

    body: { engine?, magnet?, uris?, dir?, out? }
    """
    body = request.get_json(silent=True) or {}
    engine = str(body.get("engine") or "").strip()
    magnet = str(body.get("magnet") or "").strip()
    raw_uris = body.get("uris") or []
    if not isinstance(raw_uris, list):
        raw_uris = []
    uris = [str(item or "").strip() for item in raw_uris if str(item or "").strip()]
    if not magnet and not uris:
        return error_response(400, "缺少 magnet 或 uris 参数")

    params = {
        "magnet": magnet,
        "uris": uris,
        "dir": str(body.get("dir") or "").strip(),
        "out": str(body.get("out") or "").strip(),
    }
    try:
        plugin_id, platform_label, payload = _host_service().execute_download_capability(
            engine, "download.magnet.add", params
        )
    except Exception as exc:
        error_logger.error(f"download magnet add failed: {exc}")
        return error_response(500, f"投递磁力链接失败: {exc}")

    return success_response({
        "engine": plugin_id,
        "platform": platform_label,
        "gid": (payload or {}).get("gid"),
        "added": bool((payload or {}).get("added")),
    }, "已投递到下载引擎")


@download_bp.route('/task', methods=['GET'])
@require_third_party(error_response)
def task_status():
    """按 gid 查询下载任务状态。

    query: gid, engine?
    """
    gid = str(request.args.get("gid") or "").strip()
    engine = str(request.args.get("engine") or "").strip()
    if not gid:
        return error_response(400, "缺少 gid 参数")
    try:
        _plugin_id, _platform_label, payload = _host_service().execute_download_capability(
            engine, "download.task.status", {"gid": gid}
        )
    except Exception as exc:
        error_logger.error(f"download task status failed: {exc}")
        return error_response(500, f"查询任务状态失败: {exc}")
    return success_response(payload)


@download_bp.route('/tasks', methods=['GET'])
@require_third_party(error_response)
def task_list():
    """查询下载任务列表。

    query: engine?, status?（active / waiting / paused / stopped / complete / error）
    """
    engine = str(request.args.get("engine") or "").strip()
    status = str(request.args.get("status") or "").strip()
    try:
        _plugin_id, _platform_label, payload = _host_service().execute_download_capability(
            engine, "download.task.list", {"status": status}
        )
    except Exception as exc:
        error_logger.error(f"download task list failed: {exc}")
        return error_response(500, f"查询任务列表失败: {exc}")
    return success_response(payload)


@download_bp.route('/task/pause', methods=['POST'])
@require_third_party(error_response)
def task_pause():
    """暂停下载任务。

    body: { gid, engine? }
    """
    body = request.get_json(silent=True) or {}
    gid = str(body.get("gid") or "").strip()
    if not gid:
        return error_response(400, "缺少 gid 参数")
    engine = str(body.get("engine") or "").strip()
    try:
        _plugin_id, _platform_label, payload = _host_service().execute_download_capability(
            engine, "download.task.pause", {"gid": gid}
        )
    except Exception as exc:
        error_logger.error(f"download task pause failed: {exc}")
        return error_response(500, f"暂停任务失败: {exc}")
    return success_response(payload)


@download_bp.route('/task/resume', methods=['POST'])
@require_third_party(error_response)
def task_resume():
    """继续下载任务。

    body: { gid, engine? }
    """
    body = request.get_json(silent=True) or {}
    gid = str(body.get("gid") or "").strip()
    if not gid:
        return error_response(400, "缺少 gid 参数")
    engine = str(body.get("engine") or "").strip()
    try:
        _plugin_id, _platform_label, payload = _host_service().execute_download_capability(
            engine, "download.task.resume", {"gid": gid}
        )
    except Exception as exc:
        error_logger.error(f"download task resume failed: {exc}")
        return error_response(500, f"继续任务失败: {exc}")
    return success_response(payload)


@download_bp.route('/task/remove', methods=['POST'])
@require_third_party(error_response)
def task_remove():
    """删除下载任务。

    body: { gid, engine?, force? }
    """
    body = request.get_json(silent=True) or {}
    gid = str(body.get("gid") or "").strip()
    if not gid:
        return error_response(400, "缺少 gid 参数")
    engine = str(body.get("engine") or "").strip()
    force = bool(body.get("force", True))
    try:
        _plugin_id, _platform_label, payload = _host_service().execute_download_capability(
            engine, "download.task.remove", {"gid": gid, "force": force}
        )
    except Exception as exc:
        error_logger.error(f"download task remove failed: {exc}")
        return error_response(500, f"删除任务失败: {exc}")
    return success_response(payload)
