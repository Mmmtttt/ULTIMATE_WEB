"""
演员 API 路由
"""

from flask import Blueprint, request, jsonify
from application.actor_app_service import ActorAppService
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger

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


@actor_bp.route('/list', methods=['GET'])
def actor_list():
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
def all_actors():
    try:
        result = actor_service.get_all_actors()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取所有演员失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.json
        name = data.get('name')
        actor_id = data.get('actor_id', '')
        
        if not name:
            return error_response(400, "缺少演员名称")
        
        result = actor_service.subscribe_actor(name, actor_id)
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"订阅演员失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/unsubscribe', methods=['DELETE'])
def unsubscribe():
    try:
        actor_subscription_id = request.args.get('actor_subscription_id')
        if not actor_subscription_id:
            return error_response(400, "缺少参数")
        
        result = actor_service.unsubscribe_actor(actor_subscription_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"取消订阅失败: {e}")
        return error_response(500, "服务器内部错误")


@actor_bp.route('/videos', methods=['GET'])
def actor_videos():
    try:
        actor_name = request.args.get('actor_name')
        if not actor_name:
            return error_response(400, "缺少演员名称")
        
        result = actor_service.get_actor_videos(actor_name)
        if result.success:
            return success_response(result.data)
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
