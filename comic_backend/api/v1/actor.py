from flask import Blueprint, request, jsonify
from application.actor_app_service import ActorAppService
from infrastructure.logger import app_logger, error_logger
from protocol.presentation import annotate_items

actor_bp = Blueprint('actor', __name__)
actor_service = ActorAppService()


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


def _annotate_actor_works(items, capability="person.works"):
    annotated = []
    for item in items or []:
        platform_name = str((item or {}).get("platform") or "").strip()
        annotated.extend(
            annotate_items(
                [item],
                platform_name=platform_name,
                media_type="video",
                capability=capability,
            )
        )
    return annotated


@actor_bp.route('/list', methods=['GET'])
def get_actor_list():
    try:
        result = actor_service.get_subscription_list()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取演员订阅列表失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/all', methods=['GET'])
def get_all_actors():
    """获取所有演员（主页+推荐页）"""
    try:
        result = actor_service.get_all_actors()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取所有演员失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/search-works', methods=['GET'])
def search_actor_works():
    """根据演员名搜索作品（不需要订阅）"""
    try:
        actor_name = request.args.get('actor_name')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        force_refresh = str(request.args.get('force_refresh', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
        
        if not actor_name:
            return error_response(400, "演员名称不能为空")

        if force_refresh:
            actor_service.clear_actor_works_cache(actor_name)
        
        result = actor_service.search_actor_works_by_name(actor_name, offset, limit)
        
        if result.success:
            payload = dict(result.data or {})
            payload["works"] = _annotate_actor_works(payload.get("works", []), capability="person.works")
            return success_response(payload)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/subscribe', methods=['POST'])
def subscribe_actor():
    try:
        data = request.json
        if not data or 'name' not in data:
            return error_response(400, "缺少参数: name")
        
        name = data['name']
        result = actor_service.subscribe_actor(name)
        
        if result.success:
            app_logger.info(f"订阅演员成功: {name}")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"订阅演员失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/unsubscribe', methods=['DELETE'])
def unsubscribe_actor():
    try:
        data = request.json
        if not data or 'actor_id' not in data:
            return error_response(400, "缺少参数: actor_id")
        
        actor_id = data['actor_id']
        result = actor_service.unsubscribe_actor(actor_id)
        
        if result.success:
            app_logger.info(f"取消订阅演员成功: {actor_id}")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"取消订阅演员失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/check-updates', methods=['POST'])
def check_updates():
    try:
        data = request.json or {}
        actor_id = data.get('actor_id')
        
        result = actor_service.check_actor_updates(actor_id)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"检查演员更新失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/new-works/<actor_id>', methods=['GET'])
def get_new_works(actor_id):
    try:
        result = actor_service.get_actor_new_works(actor_id)
        
        if result.success:
            payload = dict(result.data or {})
            payload["new_works"] = _annotate_actor_works(payload.get("new_works", []), capability="person.works")
            return success_response(payload)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取演员新作品失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/clear-new-count/<actor_id>', methods=['POST'])
def clear_new_count(actor_id):
    try:
        result = actor_service.clear_actor_new_count(actor_id)
        
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清除新作品计数失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/works/<actor_id>', methods=['GET'])
def get_actor_works(actor_id):
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        cache_only = str(request.args.get('cache_only', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
        force_refresh = str(request.args.get('force_refresh', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
        if force_refresh:
            cache_only = False

        result = actor_service.get_actor_works_paginated(
            actor_id,
            offset,
            limit,
            cache_only=cache_only,
            force_refresh=force_refresh
        )
        
        if result.success:
            payload = dict(result.data or {})
            payload["works"] = _annotate_actor_works(payload.get("works", []), capability="person.works")
            return success_response(payload)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/cover-cache/clear', methods=['DELETE'])
def clear_actor_cover_cache():
    """清理演员作品封面缓存"""
    try:
        result = actor_service.clear_actor_cover_cache()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清理演员封面缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/works-cache/clear', methods=['DELETE'])
def clear_actor_works_cache():
    """清理演员作品数据缓存"""
    try:
        actor_name = request.args.get('actor_name')
        
        result = actor_service.clear_actor_works_cache(actor_name)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清理演员作品缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/videos', methods=['GET'])
def actor_videos():
    try:
        actor_name = request.args.get('actor_name')
        if not actor_name:
            return error_response(400, "缺少演员名称")
        
        result = actor_service.get_actor_videos(actor_name)
        if result.success:
            return success_response(_annotate_actor_works(result.data, capability="person.works"))
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取演员视频失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/update-check-time', methods=['PUT'])
def update_check_time():
    try:
        data = request.json
        actor_subscription_id = data.get('actor_subscription_id')
        
        if not actor_subscription_id:
            return error_response(400, "缺少参数")
        
        result = actor_service.update_check_time(actor_subscription_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新检查时间失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/update-last-work', methods=['PUT'])
def update_last_work():
    try:
        data = request.json
        actor_subscription_id = data.get('actor_subscription_id')
        work_id = data.get('work_id')
        work_title = data.get('work_title')
        new_count = data.get('new_count', 0)
        
        if not actor_subscription_id:
            return error_response(400, "缺少参数")
        
        result = actor_service.update_last_work(actor_subscription_id, work_id, work_title, new_count)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新最新作品失败: {e}")
        return error_response(500, "服务器内部错误")
