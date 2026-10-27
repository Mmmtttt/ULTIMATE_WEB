from flask import Blueprint, jsonify, request

from application.semantic_search_app_service import get_semantic_search_service
from application.vision_metadata_service import get_vision_metadata_service
from infrastructure.logger import error_logger

semantic_search_bp = Blueprint("semantic_search", __name__)


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


def _parse_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@semantic_search_bp.route("/status", methods=["GET"])
def get_semantic_search_status():
    try:
        payload = get_semantic_search_service().get_status()
        return success_response(payload)
    except Exception as exc:
        error_logger.error(f"获取语义检索状态失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/rebuild", methods=["POST"])
def rebuild_semantic_search_index():
    try:
        data = request.json or {}
        build_embeddings = _parse_bool(data.get("build_embeddings"), default=True)
        # 异步构建：首次带向量构建要下载模型，不能占着这个请求
        result = get_semantic_search_service().start_rebuild(build_embeddings=build_embeddings)
        if result.success:
            return success_response(result.data, result.message or "语义索引开始构建")
        return error_response(400, result.message)
    except Exception as exc:
        error_logger.error(f"构建语义索引失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/search", methods=["GET"])
def semantic_search_query():
    try:
        keyword = str(request.args.get("keyword", "")).strip()
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        source = str(request.args.get("source", "local")).strip() or "local"
        media_type = str(request.args.get("media_type", "comic")).strip() or "comic"
        limit = request.args.get("limit", default=30, type=int) or 30
        limit = max(1, min(int(limit), 200))

        payload = get_semantic_search_service().search_with_debug(
            keyword,
            source=source,
            media_type=media_type,
            limit=limit,
        )
        if not payload.get("supported"):
            return error_response(400, payload.get("reason") or "当前平台不支持语义检索")
        return success_response(payload)
    except Exception as exc:
        error_logger.error(f"语义检索失败: {exc}")
        return error_response(500, "服务器内部错误")


# ---------- 识图补全（VLM → vibe / catalog / tags 草稿） ----------
@semantic_search_bp.route("/vision/status", methods=["GET"])
def vision_status():
    try:
        return success_response(get_vision_metadata_service().status())
    except Exception as exc:
        error_logger.error(f"获取识图补全状态失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/providers", methods=["GET"])
def vision_providers():
    try:
        from application.vision_providers import list_vision_providers

        service = get_vision_metadata_service()
        return success_response({
            "providers": list_vision_providers(),
            "context": service.status().get("context"),
        })
    except Exception as exc:
        error_logger.error(f"获取识图服务商预设失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/models", methods=["POST"])
def vision_models():
    try:
        data = request.json or {}
        payload = get_vision_metadata_service().fetch_models(
            base_url=str(data.get("base_url") or "").strip(),
            api_key=str(data.get("api_key") or "").strip(),
        )
        return success_response(payload, "模型列表已刷新" if payload.get("live") else "未能从接口拉取模型，已回退预设")
    except Exception as exc:
        error_logger.error(f"获取视觉模型列表失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/drafts", methods=["POST"])
def create_vision_draft():
    try:
        data = request.json or {}
        comic_id = str(data.get("comic_id") or "").strip()
        if not comic_id:
            return error_response(400, "缺少参数: comic_id")
        state = get_vision_metadata_service().start_draft(comic_id)
        return success_response({"comic_id": comic_id, **state}, "已开始识图补全")
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"提交识图补全失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/drafts", methods=["GET"])
def list_vision_drafts():
    try:
        service = get_vision_metadata_service()
        comic_id = str(request.args.get("comic_id", "")).strip()
        if comic_id:
            return success_response({
                "draft": service.get_draft(comic_id),
                "state": service.draft_state(comic_id),
                "failure": next(
                    (item for item in service.list_failures() if item.get("comic_id") == comic_id),
                    None,
                ),
            })
        return success_response({
            "drafts": service.list_drafts(),
            "failures": service.list_failures(),
            "status": service.status(),
        })
    except Exception as exc:
        error_logger.error(f"读取识图补全草稿失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/failures", methods=["GET"])
def list_vision_failures():
    try:
        items = get_vision_metadata_service().list_failures()
        return success_response({"items": items, "count": len(items)})
    except Exception as exc:
        error_logger.error(f"读取识图失败记录失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/failures/<comic_id>", methods=["DELETE"])
def delete_vision_failure(comic_id: str):
    try:
        removed = get_vision_metadata_service().clear_failure(comic_id)
        if not removed:
            return error_response(404, "没有这条失败记录")
        return success_response({"comic_id": comic_id}, "已清除失败记录")
    except Exception as exc:
        error_logger.error(f"清除识图失败记录失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/missing", methods=["GET"])
def list_vision_missing():
    try:
        only_missing = str(request.args.get("only_missing", "1")).strip().lower() not in {"0", "false", "no"}
        items = get_vision_metadata_service().list_missing_comics(only_missing=only_missing)
        return success_response({"items": items, "count": len(items)})
    except Exception as exc:
        error_logger.error(f"读取缺失元数据的漫画列表失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/batch", methods=["POST"])
def start_vision_batch():
    try:
        data = request.json or {}
        payload = get_vision_metadata_service().start_batch(
            only_missing=bool(data.get("only_missing", True)),
            limit=int(data.get("limit") or 0),
            comic_ids=data.get("comic_ids") or None,
        )
        message = "已开始批量识图补全" if payload.get("running") else (payload.get("error") or "没有需要补全的漫画")
        return success_response(payload, message)
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"启动批量识图补全失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/batch", methods=["GET"])
def get_vision_batch():
    try:
        return success_response(get_vision_metadata_service().batch_state())
    except Exception as exc:
        error_logger.error(f"读取批量识图补全状态失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/batch/stop", methods=["POST"])
def stop_vision_batch():
    try:
        return success_response(get_vision_metadata_service().stop_batch(), "已请求停止批量补全")
    except Exception as exc:
        error_logger.error(f"停止批量识图补全失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/drafts/<comic_id>/apply", methods=["POST"])
def apply_vision_draft(comic_id: str):
    try:
        data = request.json or {}
        payload = get_vision_metadata_service().apply_draft(comic_id, data)
        # 元数据变了 → 后台重建语义索引（带向量），避免下次搜索回落关键词路
        try:
            get_semantic_search_service().start_rebuild(build_embeddings=True)
        except Exception as rebuild_exc:  # 重建失败不影响写回结果
            error_logger.warning(f"写回后触发语义索引重建失败: {rebuild_exc}")
        return success_response(payload, "已写回漫画元数据")
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        error_logger.error(f"应用识图补全草稿失败: {exc}")
        return error_response(500, "服务器内部错误")


@semantic_search_bp.route("/vision/drafts/<comic_id>", methods=["DELETE"])
def delete_vision_draft(comic_id: str):
    try:
        removed = get_vision_metadata_service().delete_draft(comic_id)
        if not removed:
            return error_response(404, "草稿不存在")
        return success_response({"comic_id": comic_id}, "草稿已丢弃")
    except Exception as exc:
        error_logger.error(f"删除识图补全草稿失败: {exc}")
        return error_response(500, "服务器内部错误")
