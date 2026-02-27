from flask import Blueprint, request, jsonify, send_file
import time
from utils import json_handler
from utils.file_parser import file_parser
from utils.image_handler import image_handler
from utils.logger import app_logger, error_logger, access_logger

comic_bp = Blueprint('comic', __name__)

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

@comic_bp.route('/init', methods=['POST'])
def comic_init():
    """漫画初始化"""
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数")
        
        comic_id = data['comic_id']
        title = data.get('title', f"漫画_{comic_id}")
        
        # 解析图片
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画目录不存在或无有效图片")
        
        # 生成封面
        cover_path = image_handler.generate_cover(comic_id, image_paths[0])
        
        # 读取现有数据
        db_data = json_handler.read_json()
        
        # 检查是否已存在
        existing_comic = next((c for c in db_data.get('comics', []) if c['id'] == comic_id), None)
        if existing_comic:
            return error_response(400, "漫画已存在")
        
        # 构建新漫画对象
        new_comic = {
            "id": comic_id,
            "title": title,
            "title_jp": "",
            "author": "",
            "desc": "",
            "cover_path": cover_path,
            "total_page": len(image_paths),
            "current_page": 1,
            "score": None,
            "tag_ids": [],
            "list_ids": [],
            "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_read_time": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        
        # 更新数据
        db_data['comics'].append(new_comic)
        db_data['total_comics'] = len(db_data['comics'])
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        # 写入数据
        if not json_handler.write_json(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"漫画初始化成功: {comic_id}")
        return success_response(new_comic)
    except Exception as e:
        error_logger.error(f"漫画初始化失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/list', methods=['GET'])
def comic_list():
    """漫画列表"""
    try:
        db_data = json_handler.read_json()
        comics = db_data.get('comics', [])
        # 返回完整信息
        comic_list = [{
            "id": c['id'],
            "title": c['title'],
            "author": c.get('author', ''),
            "cover_path": c['cover_path'],
            "total_page": c['total_page'],
            "current_page": c['current_page'],
            "tag_ids": c.get('tag_ids', []),
            "last_read_time": c['last_read_time']
        } for c in comics]
        app_logger.info(f"获取漫画列表成功，共 {len(comic_list)} 个漫画")
        return success_response(comic_list)
    except Exception as e:
        error_logger.error(f"获取漫画列表失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/detail', methods=['GET'])
def comic_detail():
    """漫画详情"""
    try:
        comic_id = request.args.get('comic_id')
        if not comic_id:
            return error_response(400, "缺少参数")
        
        db_data = json_handler.read_json()
        comic = next((c for c in db_data.get('comics', []) if c['id'] == comic_id), None)
        if not comic:
            return error_response(404, "漫画不存在")
        
        app_logger.info(f"获取漫画详情成功: {comic_id}")
        return success_response(comic)
    except Exception as e:
        error_logger.error(f"获取漫画详情失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/images', methods=['GET'])
def comic_images():
    """图片列表"""
    try:
        comic_id = request.args.get('comic_id')
        if not comic_id:
            return error_response(400, "缺少参数")
        
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画图片不存在")
        
        # 转换为相对路径
        relative_paths = [f"/api/v1/comic/image?comic_id={comic_id}&page_num={i+1}" for i in range(len(image_paths))]
        app_logger.info(f"获取图片列表成功: {comic_id}, 共 {len(relative_paths)} 张图片")
        return success_response(relative_paths)
    except Exception as e:
        error_logger.error(f"获取图片列表失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/image', methods=['GET'])
def comic_image():
    """单张图片"""
    try:
        comic_id = request.args.get('comic_id')
        page_num = request.args.get('page_num', type=int)
        if not comic_id or not page_num:
            return error_response(400, "缺少参数")
        
        stream = image_handler.get_image_stream(comic_id, page_num)
        if not stream:
            return error_response(404, "图片不存在")
        
        # 确定文件类型
        from utils.file_parser import file_parser
        image_paths = file_parser.parse_comic_images(comic_id)
        if page_num <= len(image_paths):
            ext = image_paths[page_num - 1].split('.')[-1].lower()
            mimetype = f"image/{ext}"
            if ext == 'jpg':
                mimetype = 'image/jpeg'
        else:
            mimetype = 'image/jpeg'
        
        app_logger.info(f"获取图片成功: {comic_id}, 第 {page_num} 页")
        return send_file(stream, mimetype=mimetype)
    except Exception as e:
        error_logger.error(f"获取图片失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/progress', methods=['PUT'])
def comic_progress():
    """进度保存"""
    try:
        data = request.json
        if not data or 'comic_id' not in data or 'current_page' not in data:
            return error_response(400, "缺少参数")
        
        comic_id = data['comic_id']
        current_page = data['current_page']
        
        # 读取现有数据
        db_data = json_handler.read_json()
        
        # 查找漫画
        comic = next((c for c in db_data.get('comics', []) if c['id'] == comic_id), None)
        if not comic:
            return error_response(404, "漫画不存在")
        
        # 更新进度
        comic['current_page'] = current_page
        comic['last_read_time'] = time.strftime("%Y-%m-%dT%H:%M:%S")
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        # 写入数据
        if not json_handler.write_json(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"保存阅读进度成功: {comic_id}, 第 {current_page} 页")
        return success_response({"current_page": current_page, "last_read_time": comic['last_read_time']})
    except Exception as e:
        error_logger.error(f"保存阅读进度失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/tags', methods=['GET'])
def get_tags():
    """获取标签列表"""
    try:
        db_data = json_handler.read_json()
        tags = db_data.get('tags', [])
        app_logger.info(f"获取标签列表成功，共 {len(tags)} 个标签")
        return success_response(tags)
    except Exception as e:
        error_logger.error(f"获取标签列表失败: {e}")
        return error_response(500, "服务器内部错误")
