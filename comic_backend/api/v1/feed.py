from flask import Blueprint, jsonify, request

from application.random_feed_service import random_feed_service
from infrastructure.logger import error_logger

feed_bp = Blueprint("feed", __name__)


def success_response(data=None, msg="成功"):
    return jsonify({"code": 200, "msg": msg, "data": data})


def error_response(code, msg):
    return jsonify({"code": code, "msg": msg, "data": None})


def _normalize_mode(value: str) -> str:
    text = str(value or "").strip().lower()
    return "video" if text == "video" else "comic"


@feed_bp.route("/session", methods=["POST"])
def create_feed_session():
    try:
        data = request.json or {}
        mode = _normalize_mode(data.get("mode", "comic"))
        strategy_name = str(data.get("strategy_name", "") or "").strip() or None

        payload = random_feed_service.create_session(mode=mode, strategy_name=strategy_name)
        return success_response(payload)
    except Exception as exc:
        error_logger.error(f"create random feed session failed: {exc}")
        return error_response(500, "创建随机流会话失败")


@feed_bp.route("/session/refresh", methods=["POST"])
def refresh_feed_session():
    try:
        data = request.json or {}
        session_id = str(data.get("session_id", "") or "").strip()

        if session_id:
            payload = random_feed_service.refresh_session(session_id=session_id)
            if not payload:
                return error_response(404, "会话不存在")
            return success_response(payload, "序列已刷新")

        mode = _normalize_mode(data.get("mode", "comic"))
        strategy_name = str(data.get("strategy_name", "") or "").strip() or None
        payload = random_feed_service.create_session(mode=mode, strategy_name=strategy_name)
        return success_response(payload, "已创建新序列")
    except Exception as exc:
        error_logger.error(f"refresh random feed session failed: {exc}")
        return error_response(500, "刷新随机流会话失败")


@feed_bp.route("/items", methods=["GET"])
def get_feed_items():
    try:
        session_id = str(request.args.get("session_id", "") or "").strip()
        limit = request.args.get("limit", default=16, type=int)
        if not session_id:
            return error_response(400, "缺少参数: session_id")

        payload = random_feed_service.next_items(session_id=session_id, limit=limit)
        if payload is None:
            return error_response(404, "会话不存在")
        return success_response(payload)
    except Exception as exc:
        error_logger.error(f"get random feed items failed: {exc}")
        return error_response(500, "获取随机流内容失败")


@feed_bp.route("/strategies", methods=["GET"])
def list_feed_strategies():
    try:
        return success_response(
            {
                "strategies": random_feed_service.list_strategies(),
                "default": "random_priority_v1",
            }
        )
    except Exception as exc:
        error_logger.error(f"list random feed strategies failed: {exc}")
        return error_response(500, "获取随机流策略失败")

