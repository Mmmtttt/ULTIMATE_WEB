from flask import Blueprint, request, jsonify
from application.list_app_service import ListAppService
from infrastructure.logger import app_logger, error_logger

list_bp = Blueprint('list', __name__)
list_service = ListAppService()


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


@list_bp.route('/list', methods=['GET'])
def get_list_all():
    try:
        content_type = request.args.get('content_type')
        result = list_service.get_list_all(content_type)
        if result.success:
            app_logger.info(f"获取清单列表成功，共 {len(result.data)} 个清单")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取清单列表失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/detail', methods=['GET'])
def get_list_detail():
    try:
        list_id = request.args.get('list_id')
        if not list_id:
            return error_response(400, "缺少参数: list_id")
        
        result = list_service.get_list_detail(list_id)
        if result.success:
            app_logger.info(f"获取清单详情成功: {list_id}")
            return success_response(result.data)
        else:
            return error_response(404, result.message)
    except Exception as e:
        error_logger.error(f"获取清单详情失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/add', methods=['POST'])
def create_list():
    try:
        data = request.json
        if not data or 'list_name' not in data:
            return error_response(400, "缺少参数: list_name")
        
        name = data['list_name']
        desc = data.get('desc', '')
        content_type = data.get('content_type', 'comic')
        
        result = list_service.create_list(name, desc, content_type)
        if result.success:
            app_logger.info(f"创建清单成功: {result.data['id']}, 名称: {name}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"创建清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/edit', methods=['PUT'])
def update_list():
    try:
        data = request.json
        if not data or 'list_id' not in data:
            return error_response(400, "缺少参数: list_id")
        
        list_id = data['list_id']
        name = data.get('list_name')
        desc = data.get('desc')
        
        result = list_service.update_list(list_id, name, desc)
        if result.success:
            app_logger.info(f"更新清单成功: {list_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/delete', methods=['DELETE'])
def delete_list():
    try:
        list_id = request.args.get('list_id')
        if not list_id:
            return error_response(400, "缺少参数: list_id")
        
        result = list_service.delete_list(list_id)
        if result.success:
            app_logger.info(f"删除清单成功: {list_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"删除清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/comic/bind', methods=['PUT'])
def bind_comics():
    try:
        data = request.json
        if not data or 'list_id' not in data or 'comic_id_list' not in data:
            return error_response(400, "缺少参数: list_id 或 comic_id_list")
        
        list_id = data['list_id']
        comic_ids = data['comic_id_list']
        source = data.get('source', 'local')
        
        result = list_service.bind_comics(list_id, comic_ids, source)
        if result.success:
            app_logger.info(f"批量加入清单成功: 清单 {list_id}, {result.data['updated_count']}个漫画")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量加入清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/comic/remove', methods=['DELETE'])
def remove_comics():
    try:
        list_id = request.args.get('list_id')
        comic_id_list = request.args.getlist('comic_id_list')
        source = request.args.get('source', 'local')
        
        if not list_id or not comic_id_list:
            return error_response(400, "缺少参数: list_id 或 comic_id_list")
        
        result = list_service.remove_comics(list_id, comic_id_list, source)
        if result.success:
            app_logger.info(f"批量移出清单成功: 清单 {list_id}, {result.data['updated_count']}个漫画")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移出清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/favorite/toggle', methods=['PUT'])
def toggle_favorite():
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数: comic_id")
        
        comic_id = data['comic_id']
        source = data.get('source', 'local')
        
        result = list_service.toggle_favorite(comic_id, source)
        if result.success:
            action = "收藏" if result.data['is_favorited'] else "取消收藏"
            app_logger.info(f"{action}成功: {comic_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"收藏操作失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/favorite/check', methods=['GET'])
def check_favorite():
    try:
        comic_id = request.args.get('comic_id')
        source = request.args.get('source', 'local')
        if not comic_id:
            return error_response(400, "缺少参数: comic_id")
        
        is_favorited = list_service.is_favorited(comic_id, source)
        return success_response({"comic_id": comic_id, "is_favorited": is_favorited})
    except Exception as e:
        error_logger.error(f"检查收藏状态失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/video/bind', methods=['PUT'])
def bind_videos():
    try:
        data = request.json
        if not data or 'list_id' not in data or 'video_id_list' not in data:
            return error_response(400, "缺少参数: list_id 或 video_id_list")
        
        list_id = data['list_id']
        video_ids = data['video_id_list']
        source = data.get('source', 'local')
        
        result = list_service.bind_videos(list_id, video_ids, source)
        if result.success:
            app_logger.info(f"批量加入清单成功: 清单 {list_id}, {result.data['updated_count']}个视频")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量加入清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/video/remove', methods=['DELETE'])
def remove_videos():
    try:
        list_id = request.args.get('list_id')
        video_id_list = request.args.getlist('video_id_list')
        source = request.args.get('source', 'local')
        
        if not list_id or not video_id_list:
            return error_response(400, "缺少参数: list_id 或 video_id_list")
        
        result = list_service.remove_videos(list_id, video_id_list, source)
        if result.success:
            app_logger.info(f"批量移出清单成功: 清单 {list_id}, {result.data['updated_count']}个视频")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移出清单失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/video/favorite/toggle', methods=['PUT'])
def toggle_favorite_video():
    try:
        data = request.json
        if not data or 'video_id' not in data:
            return error_response(400, "缺少参数: video_id")
        
        video_id = data['video_id']
        source = data.get('source', 'local')
        
        result = list_service.toggle_favorite_video(video_id, source)
        if result.success:
            action = "收藏" if result.data['is_favorited'] else "取消收藏"
            app_logger.info(f"{action}成功: {video_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"收藏操作失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/video/favorite/check', methods=['GET'])
def check_favorite_video():
    try:
        video_id = request.args.get('video_id')
        source = request.args.get('source', 'local')
        if not video_id:
            return error_response(400, "缺少参数: video_id")
        
        is_favorited = list_service.is_favorited_video(video_id, source)
        return success_response({"video_id": video_id, "is_favorited": is_favorited})
    except Exception as e:
        error_logger.error(f"检查收藏状态失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/platform/lists', methods=['GET'])
def get_platform_user_lists():
    try:
        platform = request.args.get('platform')
        if not platform:
            return error_response(400, "缺少参数: platform")
        
        result = list_service.get_platform_user_lists(platform)
        if result.success:
            app_logger.info(f"获取平台用户清单列表成功: {platform}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取平台用户清单列表失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/platform/list/detail', methods=['GET'])
def get_platform_list_detail():
    try:
        platform = request.args.get('platform')
        list_id = request.args.get('list_id')
        if not platform or not list_id:
            return error_response(400, "缺少参数: platform 或 list_id")
        
        result = list_service.get_platform_list_detail(platform, list_id)
        if result.success:
            app_logger.info(f"获取平台清单详情成功: {platform}, {list_id}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取平台清单详情失败: {e}")
        return error_response(500, "服务器内部错误")


@list_bp.route('/import', methods=['POST'])
def import_platform_list():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少请求体")
        
        platform = data.get('platform')
        platform_list_id = data.get('platform_list_id')
        platform_list_name = data.get('platform_list_name', '')
        source = data.get('source', 'local')
        
        if not platform or not platform_list_id:
            return error_response(400, "缺少必要参数: platform, platform_list_id")
        
        result = list_service.import_platform_list(platform, platform_list_id, platform_list_name, source)
        if result.success:
            app_logger.info(f"导入平台清单成功: {platform}, {platform_list_id} ({platform_list_name})")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"导入平台清单失败: {e}")
        return error_response(500, "服务器内部错误")
