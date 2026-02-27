from flask import Blueprint, request, jsonify
from services.tag_service import TagService
from utils.logger import app_logger, error_logger

tag_bp = Blueprint('tag', __name__)
tag_service = TagService()

def success_response(data=None):
    """成功响应"""
    return jsonify({
        "code": 200,
        "msg": "成功",
        "data": data
    })

def error_response(code, msg):
    """错误响应"""
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None
    })

@tag_bp.route('/add', methods=['POST'])
def add_tag():
    """新增标签"""
    try:
        data = request.json
        if not data or 'tag_name' not in data:
            return error_response(400, "缺少参数: tag_name")
        
        tag_name = data['tag_name']
        result = tag_service.create_tag(tag_name)
        
        if result.success:
            app_logger.info(f"新增标签成功: {tag_name}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"新增标签失败: {e}")
        return error_response(500, "服务器内部错误")

@tag_bp.route('/list', methods=['GET'])
def list_tags():
    """获取标签列表"""
    try:
        result = tag_service.get_tag_list()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取标签列表失败: {e}")
        return error_response(500, "服务器内部错误")

@tag_bp.route('/edit', methods=['PUT'])
def edit_tag():
    """编辑标签"""
    try:
        data = request.json
        if not data or 'tag_id' not in data or 'tag_name' not in data:
            return error_response(400, "缺少参数: tag_id 或 tag_name")
        
        tag_id = data['tag_id']
        tag_name = data['tag_name']
        
        result = tag_service.update_tag(tag_id, tag_name)
        
        if result.success:
            app_logger.info(f"编辑标签成功: {tag_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"编辑标签失败: {e}")
        return error_response(500, "服务器内部错误")

@tag_bp.route('/delete', methods=['DELETE'])
def delete_tag():
    """删除标签"""
    try:
        data = request.json
        if not data or 'tag_id' not in data:
            return error_response(400, "缺少参数: tag_id")
        
        tag_id = data['tag_id']
        result = tag_service.delete_tag(tag_id)
        
        if result.success:
            app_logger.info(f"删除标签成功: {tag_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"删除标签失败: {e}")
        return error_response(500, "服务器内部错误")

@tag_bp.route('/comics', methods=['GET'])
def get_tag_comics():
    """获取标签下的漫画列表"""
    try:
        tag_id = request.args.get('tag_id')
        if not tag_id:
            return error_response(400, "缺少参数: tag_id")
        
        result = tag_service.get_comics_by_tag(tag_id)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取标签下漫画失败: {e}")
        return error_response(500, "服务器内部错误")
