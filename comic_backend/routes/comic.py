from flask import Blueprint, request, jsonify, send_file
import time
from utils import json_handler
from utils.file_parser import file_parser
from utils.image_handler import image_handler
from utils.logger import app_logger, error_logger
from services.comic_service import ComicService
from services.search_service import SearchService

comic_bp = Blueprint('comic', __name__)
comic_service = ComicService()
search_service = SearchService()

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
        
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画目录不存在或无有效图片")
        
        cover_path = image_handler.generate_cover(comic_id, image_paths[0])
        
        db_data = json_handler.read_json()
        
        existing_comic = next((c for c in db_data.get('comics', []) if c['id'] == comic_id), None)
        if existing_comic:
            return error_response(400, "漫画已存在")
        
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
        
        db_data['comics'].append(new_comic)
        db_data['total_comics'] = len(db_data['comics'])
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
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
        result = comic_service.get_comic_list()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
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
        
        result = comic_service.get_comic_detail(comic_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(404, result.message)
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
        
        result = comic_service.update_progress(comic_id, current_page)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
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

@comic_bp.route('/score', methods=['PUT'])
def update_score():
    """更新漫画评分"""
    try:
        data = request.json
        if not data or 'comic_id' not in data or 'score' not in data:
            return error_response(400, "缺少参数: comic_id 或 score")
        
        comic_id = data['comic_id']
        score = data['score']
        
        result = comic_service.update_score(comic_id, score)
        if result.success:
            app_logger.info(f"更新评分成功: {comic_id}, 评分: {score}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新评分失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/tag/bind', methods=['PUT'])
def bind_tags():
    """绑定漫画标签"""
    try:
        data = request.json
        if not data or 'comic_id' not in data or 'tag_id_list' not in data:
            return error_response(400, "缺少参数: comic_id 或 tag_id_list")
        
        comic_id = data['comic_id']
        tag_id_list = data['tag_id_list']
        
        result = comic_service.bind_tags(comic_id, tag_id_list)
        if result.success:
            app_logger.info(f"绑定标签成功: {comic_id}, 标签: {tag_id_list}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"绑定标签失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/edit', methods=['PUT'])
def edit_comic():
    """编辑漫画元数据"""
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数: comic_id")
        
        comic_id = data['comic_id']
        meta = {
            'title': data.get('title'),
            'author': data.get('author'),
            'desc': data.get('desc'),
            'cover_path': data.get('cover_path')
        }
        meta = {k: v for k, v in meta.items() if v is not None}
        
        result = comic_service.update_meta(comic_id, meta)
        if result.success:
            app_logger.info(f"编辑漫画元数据成功: {comic_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"编辑漫画元数据失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/search', methods=['GET'])
def search_comics():
    """搜索漫画"""
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        result = search_service.search_by_keyword(keyword)
        if result.success:
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(result.data)}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/filter', methods=['GET'])
def filter_comics():
    """高级筛选漫画"""
    try:
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        
        result = search_service.filter_by_tags(include_tag_ids, exclude_tag_ids)
        if result.success:
            app_logger.info(f"筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}, 结果数量: {len(result.data)}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"筛选失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/tag/batch-add', methods=['PUT'])
def batch_add_tags():
    """批量添加标签"""
    try:
        data = request.json
        if not data or 'comic_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: comic_ids 或 tag_ids")
        
        comic_ids = data['comic_ids']
        tag_ids = data['tag_ids']
        
        result = comic_service.batch_add_tags(comic_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量添加标签成功: {len(comic_ids)}个漫画, 标签: {tag_ids}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量添加标签失败: {e}")
        return error_response(500, "服务器内部错误")

@comic_bp.route('/tag/batch-remove', methods=['PUT'])
def batch_remove_tags():
    """批量移除标签"""
    try:
        data = request.json
        if not data or 'comic_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: comic_ids 或 tag_ids")
        
        comic_ids = data['comic_ids']
        tag_ids = data['tag_ids']
        
        result = comic_service.batch_remove_tags(comic_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量移除标签成功: {len(comic_ids)}个漫画, 标签: {tag_ids}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移除标签失败: {e}")
        return error_response(500, "服务器内部错误")
