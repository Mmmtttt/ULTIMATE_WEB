from flask import Blueprint, request, jsonify
from application.author_app_service import AuthorAppService
from infrastructure.logger import app_logger, error_logger
from protocol.presentation import annotate_items
from .runtime_guard import require_third_party, third_party_unavailable_response

author_bp = Blueprint('author', __name__)
author_service = AuthorAppService()


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


def _annotate_author_works(items, capability="catalog.search"):
    annotated = []
    for item in items or []:
        platform_name = str((item or {}).get("platform") or "").strip()
        annotated.extend(
            annotate_items(
                [item],
                platform_name=platform_name,
                media_type="comic",
                capability=capability,
            )
        )
    return annotated


@author_bp.route('/list', methods=['GET'])
def get_author_list():
    try:
        result = author_service.get_subscription_list()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取作者订阅列表失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/all', methods=['GET'])
def get_all_authors():
    """获取所有作者（主页+推荐页）"""
    try:
        result = author_service.get_all_authors()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取所有作者失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/search-works', methods=['GET'])
@require_third_party(error_response)
def search_author_works():
    """根据作者名搜索作品（不需要订阅）"""
    try:
        author_name = request.args.get('author_name')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        
        if not author_name:
            return error_response(400, "作者名称不能为空")
        
        result = author_service.search_author_works_by_name(author_name, offset, limit)
        
        if result.success:
            payload = dict(result.data or {})
            payload["works"] = _annotate_author_works(payload.get("works", []), capability="catalog.search")
            return success_response(payload)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索作者作品失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/subscribe', methods=['POST'])
def subscribe_author():
    try:
        data = request.json
        if not data or 'name' not in data:
            return error_response(400, "缺少参数: name")
        
        name = data['name']
        result = author_service.subscribe_author(name)
        
        if result.success:
            app_logger.info(f"订阅作者成功: {name}")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"订阅作者失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/unsubscribe', methods=['DELETE'])
def unsubscribe_author():
    try:
        data = request.json
        if not data or 'author_id' not in data:
            return error_response(400, "缺少参数: author_id")
        
        author_id = data['author_id']
        result = author_service.unsubscribe_author(author_id)
        
        if result.success:
            app_logger.info(f"取消订阅作者成功: {author_id}")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"取消订阅作者失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/check-updates', methods=['POST'])
@require_third_party(error_response)
def check_updates():
    try:
        data = request.json or {}
        author_id = data.get('author_id')
        
        result = author_service.check_author_updates(author_id)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"检查作者更新失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/new-works/<author_id>', methods=['GET'])
@require_third_party(error_response)
def get_new_works(author_id):
    try:
        result = author_service.get_author_new_works(author_id)
        
        if result.success:
            payload = dict(result.data or {})
            payload["new_works"] = _annotate_author_works(payload.get("new_works", []), capability="catalog.search")
            return success_response(payload)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取作者新作品失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/clear-new-count/<author_id>', methods=['POST'])
def clear_new_count(author_id):
    try:
        result = author_service.clear_author_new_count(author_id)
        
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清除新作品计数失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/works/<author_id>', methods=['GET'])
def get_author_works(author_id):
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        cache_only = str(request.args.get('cache_only', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
        force_refresh = str(request.args.get('force_refresh', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
        if force_refresh:
            cache_only = False
        if not cache_only:
            try:
                author_service._get_external_api()
            except RuntimeError:
                return third_party_unavailable_response(error_response)

        result = author_service.get_author_works_paginated(
            author_id,
            offset,
            limit,
            cache_only=cache_only,
            force_refresh=force_refresh
        )
        
        if result.success:
            payload = dict(result.data or {})
            payload["works"] = _annotate_author_works(payload.get("works", []), capability="catalog.search")
            return success_response(payload)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取作者作品失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/works/batch-detail', methods=['POST'])
@require_third_party(error_response)
def get_works_batch_detail():
    try:
        data = request.json
        if not data or 'ids' not in data:
            return error_response(400, "缺少参数: ids")
        
        ids = data['ids']
        result = author_service.get_works_batch_detail(ids)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量获取作品详情失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/cover-cache/clear', methods=['DELETE'])
def clear_author_cover_cache():
    """清理作者作品封面缓存"""
    try:
        result = author_service.clear_author_cover_cache()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清理作者封面缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@author_bp.route('/works-cache/clear', methods=['DELETE'])
def clear_author_works_cache():
    """清理作者作品数据缓存"""
    try:
        author_name = request.args.get('author_name')
        
        result = author_service.clear_author_works_cache(author_name)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清理作者作品缓存失败: {e}")
        return error_response(500, "服务器内部错误")
