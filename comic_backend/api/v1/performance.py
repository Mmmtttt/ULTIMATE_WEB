from __future__ import annotations

from flask import Blueprint, jsonify

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
