from flask import Blueprint, request, jsonify
from application.config_app_service import ConfigAppService
from infrastructure.logger import app_logger, error_logger
from infrastructure.recommendation_cache_manager import recommendation_cache_manager

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
            cache_stats = recommendation_cache_manager.get_cache_stats()
            config_data = result.data
            config_data['cache_stats'] = cache_stats
            app_logger.info("获取配置成功")
            return success_response(config_data)
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
            cache_config = data.get('cache_config', {})
            if cache_config:
                max_size_mb = cache_config.get('recommendation_cache_max_size_mb')
                if max_size_mb:
                    recommendation_cache_manager.update_max_size(max_size_mb)
                    app_logger.info(f"更新推荐页缓存最大容量: {max_size_mb}MB")
            
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
            recommendation_cache_manager.update_max_size(5120)
            app_logger.info("重置配置成功")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"重置配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    try:
        stats = recommendation_cache_manager.get_cache_stats()
        return success_response(stats)
    except Exception as e:
        error_logger.error(f"获取缓存统计失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/clear', methods=['DELETE'])
def clear_cache():
    try:
        count, freed_size = recommendation_cache_manager.clear_cache()
        freed_mb = freed_size / (1024 * 1024)
        app_logger.info(f"清除缓存完成: 清理 {count} 个漫画, 释放 {freed_mb:.2f} MB")
        return success_response({
            "deleted_count": count,
            "freed_size_bytes": freed_size,
            "freed_size_mb": round(freed_mb, 2)
        }, "缓存清除成功")
    except Exception as e:
        error_logger.error(f"清除缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/orphan', methods=['DELETE'])
def clean_orphan_cache():
    try:
        count = recommendation_cache_manager.clean_orphan_cache()
        app_logger.info(f"清理孤立缓存完成: 清理 {count} 个孤立目录")
        return success_response({
            "deleted_count": count
        }, "孤立缓存清理成功")
    except Exception as e:
        error_logger.error(f"清理孤立缓存失败: {e}")
        return error_response(500, "服务器内部错误")
