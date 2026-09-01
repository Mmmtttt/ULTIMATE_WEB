from __future__ import annotations

from flask import Blueprint, jsonify, make_response, request, send_file

from application.cover_thumbnail_service import CoverThumbnailError, build_cover_thumbnail
from core.constants import CACHE_MAX_AGE
from infrastructure.persistence.catalog_index import CatalogIndex


performance_bp = Blueprint("performance", __name__)


def _success(data=None, msg="成功"):
    return jsonify({"code": 200, "msg": msg, "data": data})


def _error(code: int, msg: str):
    return jsonify({"code": code, "msg": msg, "data": None}), code


@performance_bp.route("/catalog-index/status", methods=["GET"])
def catalog_index_status():
    try:
        return _success(CatalogIndex().status())
    except Exception as exc:
        return _error(500, f"读取索引状态失败: {exc}")


@performance_bp.route("/catalog-index/rebuild", methods=["POST"])
def catalog_index_rebuild():
    try:
        return _success(CatalogIndex().rebuild(), "索引重建完成")
    except Exception as exc:
        return _error(500, f"索引重建失败: {exc}")


@performance_bp.route("/cover-thumbnail", methods=["GET"])
def cover_thumbnail():
    try:
        target_path, generated = build_cover_thumbnail(
            request.args.get("src", ""),
            request.args.get("w", ""),
        )
        response = make_response(send_file(target_path, mimetype="image/jpeg"))
        if str(request.args.get("v", "") or "").strip():
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"
        response.headers["X-Cover-Thumbnail-Cache"] = "miss" if generated else "hit"
        return response
    except CoverThumbnailError as exc:
        return make_response(exc.message, exc.status_code)
    except Exception as exc:
        return make_response(f"thumbnail generation failed: {exc}", 500)
