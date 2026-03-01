"""
备份管理 API
提供备份状态查询和手动恢复功能
"""

from flask import Blueprint, request, jsonify
from infrastructure.backup_manager import backup_factory
from infrastructure.logger import app_logger, error_logger
from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE

backup_bp = Blueprint('backup', __name__)


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


@backup_bp.route('/info', methods=['GET'])
def get_backup_info():
    """获取所有备份信息"""
    try:
        info = backup_factory.get_all_info()
        return success_response(info)
    except Exception as e:
        error_logger.error(f"获取备份信息失败: {e}")
        return error_response(500, "获取备份信息失败")


@backup_bp.route('/restore', methods=['POST'])
def restore_backup():
    """
    手动恢复备份
    
    请求参数:
    {
        "target": "home" | "recommendation",
        "tier": 1 | 2 | 3
    }
    """
    try:
        data = request.get_json()
        if not data:
            return error_response(400, "缺少请求体")
        
        target = data.get('target')
        tier = data.get('tier')
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "target 必须是 'home' 或 'recommendation'")
        
        if tier not in [1, 2, 3]:
            return error_response(400, "tier 必须是 1, 2 或 3")
        
        # 确定目标文件
        json_file = RECOMMENDATION_JSON_FILE if target == 'recommendation' else JSON_FILE
        
        # 获取备份管理器
        manager = backup_factory.get_manager(json_file)
        
        # 执行恢复
        if manager.restore_from_tier(tier):
            return success_response({
                "target": target,
                "tier": tier,
                "restored": True
            })
        else:
            return error_response(500, "恢复失败，请检查备份文件是否存在")
            
    except Exception as e:
        error_logger.error(f"恢复备份失败: {e}")
        return error_response(500, f"恢复备份失败: {str(e)}")


@backup_bp.route('/trigger', methods=['POST'])
def trigger_backup():
    """
    手动触发备份
    
    请求参数:
    {
        "target": "home" | "recommendation" | "all"  # 可选，默认 all
    }
    """
    try:
        data = request.get_json() or {}
        target = data.get('target', 'all')
        
        results = {}
        
        if target in ['home', 'all']:
            manager = backup_factory.get_manager(JSON_FILE)
            manager.perform_backup()
            results['home'] = manager.get_backup_info()
        
        if target in ['recommendation', 'all']:
            manager = backup_factory.get_manager(RECOMMENDATION_JSON_FILE)
            manager.perform_backup()
            results['recommendation'] = manager.get_backup_info()
        
        return success_response(results)
        
    except Exception as e:
        error_logger.error(f"触发备份失败: {e}")
        return error_response(500, f"触发备份失败: {str(e)}")
