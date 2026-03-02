from flask import Blueprint, request, jsonify
from application.tag_app_service import TagAppService
from infrastructure.logger import app_logger, error_logger

tag_bp = Blueprint('tag', __name__)
tag_service = TagAppService()


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


@tag_bp.route('/add', methods=['POST'])
def add_tag():
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


@tag_bp.route('/all-comics', methods=['GET'])
def get_all_comics():
    try:
        result = tag_service.get_all_comics()
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取所有漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@tag_bp.route('/batch-add-tags', methods=['POST'])
def batch_add_tags():
    try:
        data = request.json
        if not data or 'comic_data' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: comic_data 或 tag_ids")
        
        comic_data = data['comic_data']
        tag_ids = data['tag_ids']
        
        result = tag_service.batch_add_tags(comic_data, tag_ids)
        
        if result.success:
            app_logger.info(f"批量添加标签成功")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量添加标签失败: {e}")
        return error_response(500, "服务器内部错误")


@tag_bp.route('/batch-remove-tags', methods=['POST'])
def batch_remove_tags():
    try:
        data = request.json
        if not data or 'comic_data' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: comic_data 或 tag_ids")
        
        comic_data = data['comic_data']
        tag_ids = data['tag_ids']
        
        result = tag_service.batch_remove_tags(comic_data, tag_ids)
        
        if result.success:
            app_logger.info(f"批量移除标签成功")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移除标签失败: {e}")
        return error_response(500, "服务器内部错误")
