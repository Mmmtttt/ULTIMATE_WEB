from flask import Blueprint, request, jsonify, send_file
from application.comic_app_service import ComicAppService
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from utils.file_parser import file_parser
from utils.image_handler import image_handler
from core.constants import CACHE_MAX_AGE, PICTURES_DIR, SUPPORTED_FORMATS, RECOMMENDATION_JSON_FILE
import os
import time

comic_bp = Blueprint('comic', __name__)
comic_service = ComicAppService()


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


@comic_bp.route('/third-party/config', methods=['GET'])
def get_third_party_config():
    try:
        from third_party.adapter_factory import AdapterConfig
        
        config_manager = AdapterConfig()
        
        jmcomic_config = config_manager.get_adapter_config('jmcomic')
        picacomic_config = config_manager.get_adapter_config('picacomic')
        
        return success_response({
            "jmcomic": {
                "username": jmcomic_config.get('username', ''),
                "password": jmcomic_config.get('password', ''),
                "download_dir": jmcomic_config.get('download_dir', '../../data/pictures/JM'),
                "output_json": jmcomic_config.get('output_json', 'comics_database.json'),
                "progress_file": jmcomic_config.get('progress_file', 'download_progress.json'),
                "favorite_list_file": jmcomic_config.get('favorite_list_file', 'favorite_comics.txt'),
                "consecutive_hit_threshold": jmcomic_config.get('consecutive_hit_threshold', 10),
                "collection_name": jmcomic_config.get('collection_name', '我的最爱')
            },
            "picacomic": {
                "account": picacomic_config.get('account', ''),
                "password": picacomic_config.get('password', ''),
                "base_dir": picacomic_config.get('base_dir', '../../data/pictures/PK')
            }
        })
        
    except Exception as e:
        error_logger.error(f"获取第三方库配置失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/third-party/config', methods=['POST'])
def save_third_party_config():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        adapter = data.get('adapter')
        
        from third_party.adapter_factory import AdapterConfig
        
        config_manager = AdapterConfig()
        
        if adapter == 'jmcomic':
            username = data.get('username', '')
            password = data.get('password', '')
            download_dir = data.get('download_dir', '../../data/pictures/JM')
            output_json = data.get('output_json', 'comics_database.json')
            progress_file = data.get('progress_file', 'download_progress.json')
            favorite_list_file = data.get('favorite_list_file', 'favorite_comics.txt')
            consecutive_hit_threshold = data.get('consecutive_hit_threshold', 10)
            collection_name = data.get('collection_name', '我的最爱')
            
            config_manager.set_adapter_config(adapter, {
                "enabled": True,
                "config_path": "JMComic-Crawler-Python/config.json",
                "username": username,
                "password": password,
                "download_dir": download_dir,
                "output_json": output_json,
                "progress_file": progress_file,
                "favorite_list_file": favorite_list_file,
                "consecutive_hit_threshold": consecutive_hit_threshold,
                "collection_name": collection_name
            })
        elif adapter == 'picacomic':
            account = data.get('account', '')
            password = data.get('password', '')
            base_dir = data.get('base_dir', '../../data/pictures/PK')
            
            config_manager.set_adapter_config(adapter, {
                "enabled": True,
                "account": account,
                "password": password,
                "base_dir": base_dir
            })
        else:
            return error_response(400, "不支持的适配器")
        
        from third_party.adapter_factory import AdapterFactory
        from third_party.external_api import reset_config_manager
        AdapterFactory.reset_instance(adapter)
        reset_config_manager()
        
        app_logger.info(f"保存第三方库配置成功: 适配器={adapter}")
        
        return success_response({"message": "配置保存成功"})
        
    except Exception as e:
        error_logger.error(f"保存第三方库配置失败: {e}")
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


@comic_bp.route('/search-third-party', methods=['GET'])
def search_third_party_comics():
    try:
        keyword = request.args.get('keyword')
        platform = request.args.get('platform', 'all')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 20))
        max_pages = int(request.args.get('max_pages', 3))
        
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        from third_party.external_api import search_albums
        from core.platform import Platform, is_platform_supported, get_supported_platforms
        
        all_results = []
        
        platforms_to_search = []
        if platform == 'all':
            platforms_to_search = get_supported_platforms()
        else:
            platform_name = platform.upper()
            if is_platform_supported(platform_name):
                platforms_to_search = [platform_name]
            else:
                return error_response(400, f"不支持的平台: {platform}，支持的平台: {get_supported_platforms()}")
        
        platform_albums = {}
        max_result_count = 0
        
        for plat in platforms_to_search:
            try:
                adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                meta_json = search_albums(keyword, max_pages=max_pages, adapter_name=adapter_name, fast_mode=True)
                
                if meta_json and meta_json.get('albums'):
                    albums = []
                    for album in meta_json['albums']:
                        album['platform'] = plat
                        albums.append(album)
                    platform_albums[plat] = albums
                    if len(albums) > max_result_count:
                        max_result_count = len(albums)
            except Exception as e:
                error_logger.error(f"搜索平台 {plat} 失败: {e}")
                continue
        
        all_results = []
        for i in range(max_result_count):
            for plat in platforms_to_search:
                if plat in platform_albums and i < len(platform_albums[plat]):
                    all_results.append(platform_albums[plat][i])
        
        total = len(all_results)
        paginated_results = all_results[offset:offset + limit]
        has_more = offset + limit < total
        
        app_logger.info(f"第三方搜索成功: 关键词 '{keyword}', 平台 {platform}, offset {offset}, limit {limit}, 结果数量: {len(paginated_results)}/{total}")
        return success_response({
            'results': paginated_results,
            'total': total,
            'offset': offset,
            'limit': limit,
            'has_more': has_more
        })
        
    except Exception as e:
        error_logger.error(f"第三方搜索失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/filter', methods=['GET'])
def filter_comics():
    try:
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        authors = request.args.getlist('authors')
        list_ids = request.args.getlist('list_ids')
        
        if authors or list_ids:
            result = comic_service.filter_multi(
                include_tags=include_tag_ids if include_tag_ids else None,
                exclude_tags=exclude_tag_ids if exclude_tag_ids else None,
                authors=authors if authors else None,
                list_ids=list_ids if list_ids else None
            )
        else:
            result = comic_service.filter_by_tags(include_tag_ids, exclude_tag_ids)
        
        if result.success:
            app_logger.info(f"筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(result.data)}")
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
        
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                file.save(tmp_file.name)
                tmp_path = tmp_file.name
            
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
                        source.close()
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
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
                
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
            
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                    file.save(tmp_file.name)
                    tmp_path = tmp_file.name
                
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
                            source.close()
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
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
        
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


@comic_bp.route('/import/online', methods=['POST'])
def import_online():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        import_type = data.get('import_type')
        target = data.get('target', 'home')
        platform_name = data.get('platform', 'JM').upper()
        
        if import_type not in ['by_id', 'by_search', 'by_favorite']:
            return error_response(400, "无效的导入方式")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")
        
        from core.platform import Platform, is_platform_supported, get_supported_platforms
        if not is_platform_supported(platform_name):
            return error_response(400, f"不支持的平台: {platform_name}，支持的平台: {get_supported_platforms()}")
        
        platform = Platform(platform_name)
        
        is_recommendation = (target == 'recommendation')
        
        from third_party.adapter import MetaDataAdapter, DuplicateChecker
        from third_party.external_api import get_album_by_id, search_albums, get_favorites
        from infrastructure.persistence.json_storage import JsonStorage
        
        storage = JsonStorage() if not is_recommendation else JsonStorage(RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        
        comics_key = 'recommendations' if is_recommendation else 'comics'
        total_key = 'total_recommendations' if is_recommendation else 'total_comics'
        
        existing_ids = [c['id'] for c in db_data.get(comics_key, [])]
        checker = DuplicateChecker(existing_ids)
        
        # 无论导入到哪里，都从主数据库读取标签
        tag_storage = JsonStorage()
        tag_db_data = tag_storage.read()
        existing_tags = tag_db_data.get('tags', [])
        adapter = MetaDataAdapter(is_recommendation, existing_tags, platform)
        
        meta_json = None
        
        # 根据平台选择适配器
        adapter_name = 'jmcomic' if platform == Platform.JM else 'picacomic'
        
        if import_type == 'by_id':
            comic_id = data.get('comic_id')
            if not comic_id:
                return error_response(400, "缺少漫画ID")
            
            from core.platform import add_platform_prefix
            full_comic_id = add_platform_prefix(platform, comic_id)
            
            if checker.is_duplicate(full_comic_id):
                return error_response(400, f"漫画 {full_comic_id} 已存在")
            
            meta_json = get_album_by_id(comic_id, adapter_name)
            
        elif import_type == 'by_search':
            keyword = data.get('keyword')
            if not keyword:
                return error_response(400, "缺少搜索关键词")
            
            max_pages = data.get('max_pages', 1)
            meta_json = search_albums(keyword, max_pages, adapter_name)
            
        elif import_type == 'by_favorite':
            meta_json = get_favorites(adapter_name)
        
        if not meta_json or not meta_json.get('albums'):
            return error_response(404, "未找到相关漫画")
        
        converted_data = adapter.parse_meta_data(meta_json)
        new_comics = converted_data.get(comics_key, [])
        
        new_comics, skipped_ids = checker.filter_duplicates(new_comics)
        
        if not new_comics:
            return error_response(400, "所有漫画已存在，无需导入")
        
        downloaded_comics = []
        failed_downloads = []
        
        if not is_recommendation:
            try:
                from third_party.platform_service import get_platform_service
                from core.platform import get_original_id
                from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR
                
                platform_service = get_platform_service()
                download_dir = JM_PICTURES_DIR if platform == Platform.JM else PK_PICTURES_DIR
                
                for comic in new_comics:
                    try:
                        original_id = get_original_id(comic['id'])
                        detail, success = platform_service.download_album(
                            platform,
                            original_id,
                            download_dir=download_dir,
                            show_progress=False
                        )
                        
                        if success:
                            downloaded_comics.append(comic['id'])
                            comic['total_page'] = detail.get('local_pages', detail.get('pages_count', comic['total_page']))
                        else:
                            failed_downloads.append(comic['id'])
                    except Exception as e:
                        error_logger.error(f"下载漫画 {comic['id']} 失败: {e}")
                        failed_downloads.append(comic['id'])
                        
            except Exception as e:
                error_logger.warning(f"无法导入下载模块: {e}")
        
        if comics_key not in db_data:
            db_data[comics_key] = []
        db_data[comics_key].extend(new_comics)
        db_data[total_key] = len(db_data[comics_key])
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        # 保存新标签到主数据库
        new_tags = converted_data.get("tags", [])
        if new_tags:
            existing_tag_ids = {t["id"] for t in tag_db_data.get("tags", [])}
            for tag in new_tags:
                if tag["id"] not in existing_tag_ids:
                    tag_db_data.setdefault("tags", []).append(tag)
                    existing_tag_ids.add(tag["id"])
            # 保存主数据库
            tag_db_data['last_updated'] = time.strftime("%Y-%m-%d")
            tag_storage.write(tag_db_data)
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        if not is_recommendation and downloaded_comics:
            try:
                from utils.file_parser import file_parser
                from utils.image_handler import ImageHandler
                
                image_handler = ImageHandler()
                
                for comic_id in downloaded_comics:
                    try:
                        image_paths = file_parser.parse_comic_images(comic_id)
                        if image_paths:
                            cover_path = image_handler.generate_cover(comic_id, image_paths[0])
                            if cover_path:
                                for comic in db_data[comics_key]:
                                    if comic['id'] == comic_id:
                                        comic['cover_path'] = cover_path
                                        break
                    except Exception as e:
                        error_logger.error(f"生成封面失败 {comic_id}: {e}")
                
                storage.write(db_data)
            except ImportError as e:
                error_logger.warning(f"无法导入封面生成模块: {e}")
        
        if is_recommendation:
            try:
                from third_party.platform_service import get_platform_service
                from core.platform import get_original_id
                from core.constants import JM_COVER_DIR, PK_COVER_DIR
                from core.utils import get_preview_pages
                
                platform_service = get_platform_service()
                cover_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
                cover_url_prefix = "JM" if platform == Platform.JM else "PK"
                
                os.makedirs(cover_dir, exist_ok=True)
                
                for comic in new_comics:
                    comic_id = comic['id']
                    original_id = get_original_id(comic_id)
                    cover_path = os.path.join(cover_dir, f"{original_id}.jpg")
                    
                    # 已有本地封面则跳过
                    if os.path.exists(cover_path):
                        comic['cover_path'] = f"/static/cover/{cover_url_prefix}/{original_id}.jpg"
                    else:
                        try:
                            # 通过 PlatformService 下载封面
                            detail, success = platform_service.download_cover(
                                platform,
                                original_id,
                                cover_path,
                                show_progress=False
                            )
                            if success and os.path.exists(cover_path):
                                comic['cover_path'] = f"/static/cover/{cover_url_prefix}/{original_id}.jpg"
                                app_logger.info(f"下载推荐页封面成功: {comic_id}")
                            else:
                                error_logger.warning(f"下载推荐页封面失败: {comic_id}")
                        except Exception as e:
                            error_logger.error(f"下载推荐页封面异常 {comic_id}: {e}")
                    
                    # 获取预览图片 URL
                    try:
                        total_page = comic.get('total_page', 0)
                        preview_pages = get_preview_pages(total_page)
                        
                        preview_urls = platform_service.get_preview_image_urls(
                            platform,
                            original_id,
                            preview_pages
                        )
                        
                        comic['preview_image_urls'] = preview_urls
                        comic['preview_pages'] = preview_pages
                        
                        app_logger.info(f"获取推荐页预览图片成功: {comic_id}, 共 {len(preview_urls)} 张")
                    except Exception as e:
                        error_logger.error(f"获取推荐页预览图片失败 {comic_id}: {e}")
                        comic['preview_image_urls'] = []
                        comic['preview_pages'] = []
            except Exception as e:
                error_logger.warning(f"无法处理推荐页导入: {e}")

        # 对推荐页导入，持久化可能更新过的 cover_path
        if is_recommendation:
            try:
                storage.write(db_data)
            except Exception as e:
                error_logger.error(f"写入推荐页封面更新失败: {e}")
        
        app_logger.info(f"在线导入成功: 平台={platform_name}, 导入方式={import_type}, 目标={target}, 新增={len(new_comics)}, 跳过={len(skipped_ids)}, 下载成功={len(downloaded_comics)}, 下载失败={len(failed_downloads)}")
        
        return success_response({
            "imported_count": len(new_comics),
            "skipped_count": len(skipped_ids),
            "skipped_ids": skipped_ids,
            "downloaded_count": len(downloaded_comics),
            "failed_downloads": failed_downloads
        })
        
    except ImportError as e:
        error_logger.error(f"第三方库未安装: {e}")
        return error_response(500, "第三方库未配置，请先配置外部 API")
    except Exception as e:
        error_logger.error(f"在线导入失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/list', methods=['GET'])
def get_trash_list():
    """获取回收站漫画列表"""
    try:
        result = comic_service.get_trash_list()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取回收站列表失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/move', methods=['PUT'])
def move_to_trash():
    """移动漫画到回收站"""
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数: comic_id")
        
        result = comic_service.move_to_trash(data['comic_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"移入回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/organize', methods=['POST'])
def organize_database():
    """整理数据库"""
    try:
        result = comic_service.organize_database()
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"整理数据库失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/restore', methods=['PUT'])
def restore_from_trash():
    """从回收站恢复漫画"""
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数: comic_id")
        
        result = comic_service.restore_from_trash(data['comic_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/batch-move', methods=['PUT'])
def batch_move_to_trash():
    """批量移动漫画到回收站"""
    try:
        data = request.json
        if not data or 'comic_ids' not in data:
            return error_response(400, "缺少参数: comic_ids")
        
        result = comic_service.batch_move_to_trash(data['comic_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移入回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/batch-restore', methods=['PUT'])
def batch_restore_from_trash():
    """批量从回收站恢复漫画"""
    try:
        data = request.json
        if not data or 'comic_ids' not in data:
            return error_response(400, "缺少参数: comic_ids")
        
        result = comic_service.batch_restore_from_trash(data['comic_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/delete', methods=['DELETE'])
def delete_permanently():
    """永久删除漫画"""
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数: comic_id")
        
        result = comic_service.delete_permanently(data['comic_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/trash/batch-delete', methods=['DELETE'])
def batch_delete_permanently():
    """批量永久删除漫画"""
    try:
        data = request.json
        if not data or 'comic_ids' not in data:
            return error_response(400, "缺少参数: comic_ids")
        
        result = comic_service.batch_delete_permanently(data['comic_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


# ==================== 异步导入任务 API ====================

@comic_bp.route('/import/async', methods=['POST'])
def import_async():
    """创建异步导入任务"""
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        import_type = data.get('import_type')
        target = data.get('target', 'home')
        platform_name = data.get('platform', 'JM').upper()
        comic_id = data.get('comic_id')
        keyword = data.get('keyword')
        comic_ids = data.get('comic_ids')
        
        if import_type not in ['by_id', 'by_search', 'by_list']:
            return error_response(400, "无效的导入方式，支持: by_id, by_search, by_list")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")
        
        from core.platform import Platform, is_platform_supported, get_supported_platforms
        if not is_platform_supported(platform_name):
            return error_response(400, f"不支持的平台: {platform_name}，支持的平台: {get_supported_platforms()}")
        
        # 检查是否已存在
        if import_type == 'by_id' and comic_id:
            from core.platform import add_platform_prefix
            full_comic_id = add_platform_prefix(Platform(platform_name), comic_id)
            
            # 检查是否已存在
            from infrastructure.persistence.json_storage import JsonStorage
            db_file = 'data/meta_data/comics_database.json' if target == 'home' else 'data/meta_data/recommendations_database.json'
            storage = JsonStorage(db_file)
            db_data = storage.read()
            comics_key = 'comics' if target == 'home' else 'recommendations'
            
            existing_ids = {c['id'] for c in db_data.get(comics_key, [])}
            if full_comic_id in existing_ids:
                return error_response(400, f"漫画 {full_comic_id} 已存在")
        
        # 创建异步任务
        from infrastructure.task_manager import task_manager
        task_id = task_manager.create_task(
            platform=platform_name,
            import_type=import_type,
            target=target,
            comic_id=comic_id,
            keyword=keyword,
            comic_ids=comic_ids
        )
        
        app_logger.info(f"创建异步导入任务: {task_id}, 平台={platform_name}, 类型={import_type}, 目标={target}")
        
        return success_response({
            "task_id": task_id,
            "message": "导入任务已创建"
        }, "导入任务已创建，请通过任务ID查询进度")
        
    except Exception as e:
        error_logger.error(f"创建异步导入任务失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/import/tasks', methods=['GET'])
def get_import_tasks():
    """获取导入任务列表"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        from infrastructure.task_manager import task_manager
        tasks = task_manager.get_all_tasks(limit)
        
        tasks_data = [task.to_dict() for task in tasks]
        
        return success_response({
            "tasks": tasks_data,
            "count": len(tasks_data)
        })
        
    except Exception as e:
        error_logger.error(f"获取导入任务列表失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/import/task/<task_id>', methods=['GET'])
def get_import_task(task_id):
    """获取单个导入任务详情"""
    try:
        from infrastructure.task_manager import task_manager
        task = task_manager.get_task(task_id)
        
        if not task:
            return error_response(404, "任务不存在")
        
        return success_response(task.to_dict())
        
    except Exception as e:
        error_logger.error(f"获取导入任务详情失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/import/task/<task_id>/cancel', methods=['POST'])
def cancel_import_task(task_id):
    """取消导入任务"""
    try:
        from infrastructure.task_manager import task_manager
        success = task_manager.cancel_task(task_id)
        
        if success:
            return success_response(None, "任务已取消")
        else:
            return error_response(400, "任务不存在或已开始处理，无法取消")
        
    except Exception as e:
        error_logger.error(f"取消导入任务失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/import/tasks/clear', methods=['POST'])
def clear_completed_tasks():
    """清理已完成的任务"""
    try:
        keep_count = request.json.get('keep_count', 20) if request.json else 20
        
        from infrastructure.task_manager import task_manager
        deleted_count = task_manager.clear_completed_tasks(keep_count)
        
        return success_response({
            "deleted_count": deleted_count
        }, f"已清理 {deleted_count} 个已完成任务")
        
    except Exception as e:
        error_logger.error(f"清理已完成任务失败: {e}")
        return error_response(500, "服务器内部错误")
