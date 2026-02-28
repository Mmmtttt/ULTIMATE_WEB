from flask import Blueprint, request, jsonify, send_file
from application.comic_app_service import ComicAppService
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from utils.file_parser import file_parser
from utils.image_handler import image_handler
from core.constants import CACHE_MAX_AGE, PICTURES_DIR, SUPPORTED_FORMATS
import os
import time

comic_bp = Blueprint('comic', __name__)
comic_service = ComicAppService()


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


@comic_bp.route('/init', methods=['POST'])
def comic_init():
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数")
        
        import time
        comic_id = data['comic_id']
        title = data.get('title', f"漫画_{comic_id}")
        
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画目录不存在或无有效图片")
        
        cover_path = image_handler.generate_cover(comic_id, image_paths[0])
        
        from infrastructure.persistence.json_storage import JsonStorage
        storage = JsonStorage()
        db_data = storage.read()
        
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
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"漫画初始化成功: {comic_id}")
        return success_response(new_comic)
    except Exception as e:
        error_logger.error(f"漫画初始化失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/list', methods=['GET'])
def comic_list():
    try:
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        
        result = comic_service.get_comic_list(sort_type, min_score, max_score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取漫画列表失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/detail', methods=['GET'])
def comic_detail():
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
        response = send_file(stream, mimetype=mimetype)
        response.headers['Cache-Control'] = f'public, max-age={CACHE_MAX_AGE}'
        return response
    except Exception as e:
        error_logger.error(f"获取图片失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/progress', methods=['PUT'])
def comic_progress():
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
    try:
        from application.tag_app_service import TagAppService
        tag_service = TagAppService()
        result = tag_service.get_tag_list()
        
        if result.success:
            app_logger.info(f"获取标签列表成功，共 {len(result.data)} 个标签")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取标签列表失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/score', methods=['PUT'])
def update_score():
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
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        result = comic_service.search(keyword)
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
    try:
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        
        result = comic_service.filter_by_tags(include_tag_ids, exclude_tag_ids)
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


@comic_bp.route('/download', methods=['GET'])
def download_comic():
    try:
        comic_id = request.args.get('comic_id')
        if not comic_id:
            return error_response(400, "缺少参数: comic_id")
        
        import zipfile
        import io
        import time
        
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画图片不存在")
        
        result = comic_service.get_comic_detail(comic_id)
        if not result.success:
            return error_response(404, result.message)
        
        comic_data = result.data
        comic_title = comic_data.get('title', comic_id)
        safe_title = "".join(c for c in comic_title if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{comic_id}-{safe_title}.zip"
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, image_path in enumerate(image_paths, 1):
                if os.path.exists(image_path):
                    ext = os.path.splitext(image_path)[1]
                    arcname = f"{i:04d}{ext}"
                    zf.write(image_path, arcname)
        
        memory_file.seek(0)
        
        app_logger.info(f"下载漫画成功: {comic_id}")
        response = send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
        return response
    except Exception as e:
        error_logger.error(f"下载漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-download', methods=['POST'])
def batch_download_comics():
    try:
        data = request.json
        if not data or 'comic_ids' not in data:
            return error_response(400, "缺少参数: comic_ids")
        
        comic_ids = data['comic_ids']
        if not comic_ids or len(comic_ids) == 0:
            return error_response(400, "漫画ID列表为空")
        
        import zipfile
        import io
        import time
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for comic_id in comic_ids:
                image_paths = file_parser.parse_comic_images(comic_id)
                if not image_paths:
                    continue
                
                result = comic_service.get_comic_detail(comic_id)
                if not result.success:
                    continue
                
                comic_data = result.data
                comic_title = comic_data.get('title', comic_id)
                safe_title = "".join(c for c in comic_title if c.isalnum() or c in (' ', '-', '_')).strip()
                folder_name = f"{comic_id}-{safe_title}"
                
                for i, image_path in enumerate(image_paths, 1):
                    if os.path.exists(image_path):
                        ext = os.path.splitext(image_path)[1]
                        arcname = f"{folder_name}/{i:04d}{ext}"
                        zf.write(image_path, arcname)
        
        memory_file.seek(0)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"comics_batch_{timestamp}.zip"
        
        app_logger.info(f"批量下载漫画成功: {len(comic_ids)}个漫画")
        response = send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
        return response
    except Exception as e:
        error_logger.error(f"批量下载漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/upload', methods=['POST'])
def upload_comic():
    try:
        if 'file' not in request.files:
            return error_response(400, "没有上传文件")
        
        file = request.files['file']
        if not file or not file.filename:
            return error_response(400, "文件无效")
        
        if not file.filename.lower().endswith('.zip'):
            return error_response(400, "只支持 .zip 格式")
        
        import zipfile
        import tempfile
        import shutil
        
        from infrastructure.persistence.json_storage import JsonStorage
        storage = JsonStorage()
        db_data = storage.read()
        
        comics = db_data.get('comics', [])
        max_id = 1000000000
        for c in comics:
            try:
                cid = int(c.get('id', '0'))
                if cid >= max_id:
                    max_id = cid + 1
            except:
                pass
        
        comic_id = str(max_id)
        
        filename = file.filename
        title = os.path.splitext(filename)[0]
        
        comic_dir = os.path.join(PICTURES_DIR, comic_id)
        if os.path.exists(comic_dir):
            shutil.rmtree(comic_dir)
        os.makedirs(comic_dir, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            image_count = 0
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('/'):
                        continue
                    
                    ext = os.path.splitext(name)[1].lower()
                    if ext in SUPPORTED_FORMATS:
                        source = zf.open(name)
                        target_path = os.path.join(comic_dir, os.path.basename(name))
                        with open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        image_count += 1
            
            if image_count == 0:
                shutil.rmtree(comic_dir)
                return error_response(400, "ZIP 文件中没有有效图片")
            
            image_paths = file_parser.parse_comic_images(comic_id)
            cover_path = image_handler.generate_cover(comic_id, image_paths[0])
            
            new_comic = {
                "id": comic_id,
                "title": title,
                "title_jp": "",
                "author": "",
                "desc": "",
                "cover_path": cover_path,
                "total_page": image_count,
                "current_page": 1,
                "score": 8.0,
                "tag_ids": [],
                "list_ids": [],
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "last_read_time": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            db_data['comics'].append(new_comic)
            db_data['total_comics'] = len(db_data['comics'])
            db_data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not storage.write(db_data):
                shutil.rmtree(comic_dir)
                return error_response(500, "数据写入失败")
            
            app_logger.info(f"上传漫画成功: {comic_id}, 标题: {title}, 页数: {image_count}")
            return success_response(new_comic)
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        error_logger.error(f"上传漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload', methods=['POST'])
def batch_upload_comics():
    try:
        if 'files' not in request.files:
            return error_response(400, "没有上传文件")
        
        files = request.files.getlist('files')
        if not files:
            return error_response(400, "文件列表为空")
        
        import zipfile
        import tempfile
        import shutil
        
        from infrastructure.persistence.json_storage import JsonStorage
        storage = JsonStorage()
        db_data = storage.read()
        
        comics = db_data.get('comics', [])
        max_id = 1000000000
        for c in comics:
            try:
                cid = int(c.get('id', '0'))
                if cid >= max_id:
                    max_id = cid + 1
            except:
                pass
        
        uploaded_comics = []
        
        for file in files:
            if not file or not file.filename:
                continue
            
            if not file.filename.lower().endswith('.zip'):
                continue
            
            comic_id = str(max_id)
            max_id += 1
            
            filename = file.filename
            title = os.path.splitext(filename)[0]
            
            comic_dir = os.path.join(PICTURES_DIR, comic_id)
            if os.path.exists(comic_dir):
                shutil.rmtree(comic_dir)
            os.makedirs(comic_dir, exist_ok=True)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                file.save(tmp_file.name)
                tmp_path = tmp_file.name
            
            try:
                image_count = 0
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith('/'):
                            continue
                        
                        ext = os.path.splitext(name)[1].lower()
                        if ext in SUPPORTED_FORMATS:
                            source = zf.open(name)
                            target_path = os.path.join(comic_dir, os.path.basename(name))
                            with open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            image_count += 1
                
                if image_count == 0:
                    shutil.rmtree(comic_dir)
                    continue
                
                image_paths = file_parser.parse_comic_images(comic_id)
                cover_path = image_handler.generate_cover(comic_id, image_paths[0])
                
                new_comic = {
                    "id": comic_id,
                    "title": title,
                    "title_jp": "",
                    "author": "",
                    "desc": "",
                    "cover_path": cover_path,
                    "total_page": image_count,
                    "current_page": 1,
                    "score": 8.0,
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "last_read_time": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                
                db_data['comics'].append(new_comic)
                uploaded_comics.append(new_comic)
                
            except Exception as e:
                error_logger.error(f"处理文件 {filename} 失败: {e}")
                if os.path.exists(comic_dir):
                    shutil.rmtree(comic_dir)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        if not uploaded_comics:
            return error_response(400, "没有成功上传任何漫画")
        
        db_data['total_comics'] = len(db_data['comics'])
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"批量上传漫画成功: {len(uploaded_comics)} 部")
        return success_response({
            "count": len(uploaded_comics),
            "comics": uploaded_comics
        })
        
    except Exception as e:
        error_logger.error(f"批量上传漫画失败: {e}")
        return error_response(500, "服务器内部错误")
