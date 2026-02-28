from flask import Blueprint, request, jsonify
from application.config_app_service import ConfigAppService
from infrastructure.logger import app_logger, error_logger

config_bp = Blueprint('config', __name__)
config_service = ConfigAppService()


def success_response(data=None):
    return jsonify({
        "code": 200,
        "msg": "成功",
        "data": data
    })


def error_response(code, msg):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None
    })


@config_bp.route('', methods=['GET'])
def get_config():
    try:
        result = config_service.get_config()
        if result.success:
            app_logger.info("获取配置成功")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('', methods=['PUT'])
def update_config():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        result = config_service.update_config(**data)
        if result.success:
            app_logger.info(f"更新配置成功: {data}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/reset', methods=['POST'])
def reset_config():
    try:
        result = config_service.reset_config()
        if result.success:
            app_logger.info("重置配置成功")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"重置配置失败: {e}")
        return error_response(500, "服务器内部错误")
