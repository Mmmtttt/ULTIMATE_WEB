from flask import Blueprint, request, jsonify, send_file
from application.comic_app_service import ComicAppService
from application.database_organize_service import DatabaseOrganizeService
from application.local_comic_import_service import local_comic_import_service
from application.softref_comic_reader import (
    SoftRefPasswordRequiredError,
    SoftRefSourceMissingError,
)
from application.softref_reader_protocol import require_softref_reader
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from utils.file_parser import file_parser
from utils.image_handler import image_handler
from core.constants import (
    CACHE_MAX_AGE,
    COMIC_DIR,
    COVER_DIR,
    JSON_FILE,
    PICTURES_DIR,
    RECOMMENDATION_JSON_FILE,
    SUPPORTED_FORMATS,
)
from core.utils import normalize_total_page
from protocol.compatibility import get_query_status_for_adapter_name
from protocol.gateway import get_protocol_gateway
from protocol.presentation import annotate_items
from .runtime_guard import require_third_party
import os
import time

comic_bp = Blueprint('comic', __name__)
comic_service = ComicAppService()
database_organize_service = DatabaseOrganizeService(comic_service)
softref_comic_reader = require_softref_reader("comic")


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


def _resolve_platform_manifest(platform_name: str, media_type: str = ""):
    gateway = get_protocol_gateway()
    normalized_name = str(platform_name or "").strip()
    normalized_media_type = str(media_type or "").strip().lower()
    if not normalized_name:
        return None

    manifest = gateway.get_manifest_by_lookup(
        normalized_name,
        media_type=normalized_media_type or None,
    )
    if manifest is not None:
        return manifest

    manifest = gateway.get_manifest_by_config_key(normalized_name)
    if manifest is None:
        return None

    if normalized_media_type:
        manifest_media_types = {str(item or "").strip().lower() for item in (manifest.media_types or [])}
        if normalized_media_type not in manifest_media_types:
            return None
    return manifest


def _resolve_manifest_platform_label(manifest) -> str:
    identity = manifest.identity if manifest is not None else {}
    for candidate in (
        identity.get("platform_label"),
        *(manifest.identity_aliases if manifest is not None else []),
        identity.get("host_id_prefix"),
        manifest.config_key if manifest is not None else "",
        manifest.name if manifest is not None else "",
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            return normalized.upper()
    return ""


def _resolve_manifest_host_prefix(manifest) -> str:
    identity = manifest.identity if manifest is not None else {}
    host_prefix = str(identity.get("host_id_prefix") or "").strip().upper()
    if host_prefix:
        return host_prefix
    return _resolve_manifest_platform_label(manifest)


def _resolve_manifest_content_type(manifest) -> str:
    media_types = [str(item or "").strip().lower() for item in (manifest.media_types if manifest else [])]
    if "video" in media_types:
        return "video"
    return "comic"


def _resolve_cover_path_mode(manifest) -> str:
    try:
        cover = (((manifest.presentation or {}).get("media_card") or {}).get("cover") or {})
        return str(cover.get("path_mode") or "").strip().lower() or "local_static"
    except Exception:
        return "local_static"


def _build_prefixed_id(host_prefix: str, original_id: str) -> str:
    normalized_prefix = str(host_prefix or "").strip().upper()
    normalized_original_id = str(original_id or "").strip()
    if not normalized_original_id:
        return normalized_original_id
    if not normalized_prefix:
        return normalized_original_id
    if normalized_original_id.upper().startswith(normalized_prefix):
        return normalized_original_id
    return f"{normalized_prefix}{normalized_original_id}"


def _list_supported_platform_labels(media_type: str = "") -> list:
    gateway = get_protocol_gateway()
    manifests = gateway.list_manifests(media_type=str(media_type or "").strip().lower() or None)
    labels = []
    for manifest in manifests:
        label = _resolve_manifest_platform_label(manifest)
        if label:
            labels.append(label)
    return sorted(set(labels))


def _get_default_platform_name(media_type: str = "comic") -> str:
    manifests = list(
        get_protocol_gateway().list_manifests(
            media_type=str(media_type or "").strip().lower() or None
        )
    )
    if not manifests:
        return ""
    return _resolve_manifest_platform_label(manifests[0])


@comic_bp.route('/init', methods=['POST'])
def comic_init():
    try:
        data = request.json
        if not data or 'comic_id' not in data:
            return error_response(400, "缺少参数")
        
        import time
        comic_id = data['comic_id']
        title = data.get('title', f"漫画_{comic_id}")

        from infrastructure.persistence.json_storage import JsonStorage
        storage = JsonStorage()
        db_data = storage.read()
        
        existing_comic = next((c for c in db_data.get('comics', []) if c['id'] == comic_id), None)
        if existing_comic:
            return error_response(400, "漫画已存在")
        
        image_paths = file_parser.parse_comic_images(comic_id)
        if not image_paths:
            return error_response(404, "漫画目录不存在或无有效图片")
        
        cover_path = image_handler.generate_cover(comic_id, image_paths[0])
        
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
@require_third_party(error_response)
def get_third_party_config():
    try:
        from protocol.config_service import get_plugin_config_service

        return success_response(get_plugin_config_service().build_response())
    except Exception as e:
        error_logger.error(f"获取第三方库配置失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/third-party/config', methods=['POST'])
@require_third_party(error_response)
def save_third_party_config():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")

        from protocol.config_service import get_plugin_config_service

        result = get_plugin_config_service().save_updates(data)
        app_logger.info(f"保存第三方库配置成功: {result.get('updated_adapters')}")
        return success_response(result)
    except ValueError as e:
        return error_response(400, str(e))
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

        if softref_comic_reader.is_soft_ref_content(comic_id):
            try:
                page_count = softref_comic_reader.get_page_count(comic_id)
                if page_count > 0:
                    # Trigger one real read to surface password challenge early.
                    softref_comic_reader.get_image_stream(comic_id, 1)
            except SoftRefPasswordRequiredError as exc:
                return success_response({
                    "images": [],
                    "password_required": softref_comic_reader.get_password_required_payload(comic_id, exc),
                })
            except SoftRefSourceMissingError as exc:
                return error_response(404, str(exc))
            except ValueError as exc:
                return error_response(404, str(exc))
            relative_paths = [f"/api/v1/comic/image?comic_id={comic_id}&page_num={i+1}" for i in range(page_count)]
            app_logger.info(f"获取软连接漫画图片列表成功: {comic_id}, 共 {len(relative_paths)} 张图片")
            return success_response(relative_paths)
        
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

        if softref_comic_reader.is_soft_ref_content(comic_id):
            try:
                stream, mimetype = softref_comic_reader.get_image_stream(comic_id, page_num)
            except SoftRefPasswordRequiredError:
                return error_response(428, "该压缩包需要密码，请先在阅读页输入密码")
            except SoftRefSourceMissingError as exc:
                return error_response(404, str(exc))
            except ValueError as exc:
                return error_response(404, str(exc))
            response = send_file(stream, mimetype=mimetype or 'image/jpeg')
            response.headers['Cache-Control'] = f'public, max-age={CACHE_MAX_AGE}'
            return response
        
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


@comic_bp.route('/softref/password', methods=['POST'])
def comic_softref_set_password():
    try:
        data = request.json or {}
        comic_id = str(data.get('comic_id', '') or '').strip()
        archive_fingerprint = str(data.get('archive_fingerprint', '') or '').strip()
        password = str(data.get('password', '') or '')
        if not comic_id:
            return error_response(400, "缺少参数: comic_id")
        if not archive_fingerprint:
            return error_response(400, "缺少参数: archive_fingerprint")
        if not password:
            return error_response(400, "缺少参数: password")

        result = softref_comic_reader.set_archive_password(
            comic_id=comic_id,
            archive_fingerprint=archive_fingerprint,
            password=password,
        )
        return success_response(result, "密码保存成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"保存软连接压缩包密码失败: {e}")
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
@require_third_party(error_response)
def search_third_party_comics():
    try:
        keyword = request.args.get('keyword')
        platform = request.args.get('platform', 'all')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 40))
        
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        from protocol.adapter_api import search_albums
        
        available_plugins = []
        platform_lookup = {}
        for manifest in get_protocol_gateway().list_manifests(media_type="comic", capability="catalog.search"):
            config_key = str(manifest.config_key or "").strip()
            if not config_key:
                continue

            platform_label = str((manifest.identity or {}).get("platform_label") or "").strip()
            if not platform_label:
                platform_label = str(
                    (
                        getattr(manifest, "identity_aliases", None)
                        or [str((manifest.identity or {}).get("platform_label") or "").strip(), manifest.name]
                    )[0]
                    or ""
                ).strip()
            if not platform_label:
                continue

            descriptor = {
                "manifest": manifest,
                "adapter_name": config_key,
                "platform_label": platform_label.upper(),
            }
            available_plugins.append(descriptor)
            platform_lookup[descriptor["platform_label"]] = descriptor

        supported_platforms = sorted(platform_lookup.keys())
        if platform == 'all':
            platforms_to_search = available_plugins
        else:
            descriptor = platform_lookup.get(str(platform or "").strip().upper())
            if descriptor is None:
                return error_response(400, f"不支持的漫画平台: {platform}，支持的平台: {supported_platforms}")
            platforms_to_search = [descriptor]
        
        platform_results = {}
        platform_errors = {}
        all_albums = []
        
        for descriptor in platforms_to_search:
            manifest = descriptor["manifest"]
            plat = descriptor["platform_label"]
            adapter_name = descriptor["adapter_name"]

            credential_status = get_query_status_for_adapter_name(adapter_name)
            if not bool(credential_status.get("configured", False)):
                platform_errors[plat] = str(credential_status.get("message") or f"{plat} 平台未配置查询凭据")
                if platform != 'all':
                    return error_response(400, platform_errors[plat])
                continue

            try:
                result = search_albums(
                    keyword, 
                    page=page, 
                    max_pages=1, 
                    adapter_name=adapter_name, 
                    fast_mode=True
                )
                
                if result and result.get('albums'):
                    albums_with_platform = []
                    for album in annotate_items(
                        result.get('albums', []),
                        plugin_id=manifest.plugin_id,
                        media_type="comic",
                        capability="catalog.search",
                    ):
                        album_with_platform = album.copy()
                        album_with_platform['platform'] = plat
                        album_with_platform['platform_page'] = result.get('page', 1)
                        album_with_platform['platform_total_pages'] = result.get('total_pages')
                        album_with_platform['platform_has_next'] = result.get('has_next', False)
                        albums_with_platform.append(album_with_platform)
                    
                    platform_results[plat] = {
                        'page': result.get('page', 1),
                        'total_pages': result.get('total_pages'),
                        'has_next': result.get('has_next', False),
                        'albums': albums_with_platform
                    }
                    
                    all_albums.extend(albums_with_platform)
                    
            except RuntimeError as e:
                platform_errors[plat] = str(e)
                error_logger.error(f"搜索平台 {plat} 失败: {e}")
                if platform != 'all':
                    return error_response(400, platform_errors[plat])
            except Exception as e:
                error_logger.error(f"搜索平台 {plat} 失败: {e}")
                platform_errors[plat] = f"{plat} 平台搜索失败"
                if platform != 'all':
                    return error_response(500, platform_errors[plat])
                continue
        
        has_more = any(info.get('has_next', False) for info in platform_results.values())
        
        app_logger.info(f"第三方搜索成功: 关键词 '{keyword}', 平台 {platform}, page {page}, 结果数量: {len(all_albums)}")
        return success_response({
            'results': all_albums,
            'platform_info': platform_results,
            'page': page,
            'limit': limit,
            'has_more': has_more,
            'platform_errors': platform_errors,
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


@comic_bp.route('/batch-upload/session/from-path', methods=['POST'])
def batch_upload_create_session_from_path():
    """按服务端本机路径创建本地导入解析会话。"""
    try:
        data = request.json or {}
        source_path = str(data.get('source_path', '') or '').strip()
        if not source_path:
            return error_response(400, "缺少参数: source_path")

        import_mode = str(data.get('import_mode', 'copy_safe') or 'copy_safe').strip()
        archive_password = str(data.get('archive_password', '') or '').strip() or None
        result = local_comic_import_service.create_session_from_path(
            source_path,
            import_mode=import_mode,
            archive_password=archive_password,
        )
        return success_response(result, "解析会话创建成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"创建本地导入会话失败(path): {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/recoverable', methods=['GET'])
def batch_upload_list_recoverable_sessions():
    try:
        limit = request.args.get('limit', default=20, type=int)
        sessions = local_comic_import_service.list_recoverable_sessions(limit=limit)
        return success_response({
            "sessions": sessions,
            "count": len(sessions),
        })
    except Exception as e:
        error_logger.error(f"获取可恢复本地导入会话失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/resume', methods=['POST'])
def batch_upload_resume_session():
    try:
        data = request.json or {}
        session_id = str(data.get('session_id', '') or '').strip()
        if not session_id:
            return error_response(400, "缺少参数: session_id")

        result = local_comic_import_service.resume_session(session_id)
        return success_response(result, "会话恢复成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"恢复本地导入会话失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/upload', methods=['POST'])
def batch_upload_create_session_from_upload():
    """通过浏览器上传创建本地导入解析会话。"""
    try:
        files = request.files.getlist('files')
        if not files:
            return error_response(400, "没有上传文件")

        relative_paths = request.form.getlist('relative_paths')
        if not relative_paths:
            relative_paths = [f.filename or '' for f in files]

        result = local_comic_import_service.create_session_from_upload(files, relative_paths)
        return success_response(result, "解析会话创建成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"创建本地导入会话失败(upload): {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/<session_id>/tree', methods=['GET'])
def batch_upload_get_session_tree(session_id):
    try:
        result = local_comic_import_service.get_session_tree(session_id)
        return success_response(result)
    except ValueError as e:
        return error_response(404, str(e))
    except Exception as e:
        error_logger.error(f"获取本地导入会话目录树失败: {session_id}, {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/export', methods=['POST'])
def batch_upload_export_json():
    """根据层级标记生成解析结果 JSON。"""
    try:
        data = request.json or {}
        session_id = str(data.get('session_id', '') or '').strip()
        if not session_id:
            return error_response(400, "缺少参数: session_id")

        assignments = data.get('assignments', {}) or {}
        if not isinstance(assignments, dict):
            return error_response(400, "参数 assignments 格式错误")

        tag_assignments = data.get('tag_assignments', None)
        if tag_assignments is not None and not isinstance(tag_assignments, dict):
            return error_response(400, "参数 tag_assignments 格式错误")

        result = local_comic_import_service.export_session_items(session_id, assignments, tag_assignments)
        return success_response(result, "JSON 生成成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"导出本地导入 JSON 失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/commit', methods=['POST'])
def batch_upload_commit_session():
    """提交导入到本地漫画库。支持中断后继续执行。"""
    try:
        data = request.json or {}
        session_id = str(data.get('session_id', '') or '').strip()
        if not session_id:
            return error_response(400, "缺少参数: session_id")

        assignments = data.get('assignments', None)
        if assignments is not None and not isinstance(assignments, dict):
            return error_response(400, "参数 assignments 格式错误")

        tag_assignments = data.get('tag_assignments', None)
        if tag_assignments is not None and not isinstance(tag_assignments, dict):
            return error_response(400, "参数 tag_assignments 格式错误")

        result = local_comic_import_service.commit_session_import(session_id, assignments, tag_assignments)
        if result.get('failed_count', 0) > 0:
            return success_response(
                result,
                f"导入部分失败，可修复后继续: 成功 {result.get('imported_count', 0)}，失败 {result.get('failed_count', 0)}"
            )
        return success_response(result, "导入完成")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"提交本地导入会话失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/<session_id>/result.json', methods=['GET'])
def batch_upload_download_result_json(session_id):
    try:
        path = local_comic_import_service.get_result_file_path(session_id)
        return send_file(
            str(path),
            mimetype='application/json',
            as_attachment=True,
            download_name='result.json'
        )
    except ValueError as e:
        return error_response(404, str(e))
    except Exception as e:
        error_logger.error(f"下载本地导入结果 JSON 失败: {session_id}, {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/batch-upload/session/<session_id>', methods=['DELETE'])
def batch_upload_clear_session(session_id):
    try:
        local_comic_import_service.clear_session(session_id)
        return success_response({"session_id": session_id}, "会话已清理")
    except ValueError as e:
        return error_response(404, str(e))
    except Exception as e:
        error_logger.error(f"清理本地导入会话失败: {session_id}, {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/import/online', methods=['POST'])
@require_third_party(error_response)
def import_online():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        import_type = data.get('import_type')
        target = data.get('target', 'home')
        requested_platform = str(data.get('platform', '') or '').strip() or _get_default_platform_name("comic")
        
        if import_type not in ['by_id', 'by_search', 'by_favorite']:
            return error_response(400, "无效的导入方式")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")

        manifest = _resolve_platform_manifest(requested_platform, media_type="comic")
        if manifest is None:
            return error_response(
                400,
                f"不支持的平台: {requested_platform}，支持的平台: {_list_supported_platform_labels('comic')}",
            )

        platform_name = _resolve_manifest_platform_label(manifest)
        host_prefix = _resolve_manifest_host_prefix(manifest)
        config_key = str(manifest.config_key or "").strip()
        cover_path_mode = _resolve_cover_path_mode(manifest)
        
        is_recommendation = (target == 'recommendation')
        
        from protocol.adapter_api import get_album_by_id, search_albums, get_favorites
        from protocol.metadata_adapter import MetaDataAdapter, DuplicateChecker
        from infrastructure.persistence.json_storage import JsonStorage
        from core.constants import JSON_FILE as ACTIVE_JSON_FILE, RECOMMENDATION_JSON_FILE as ACTIVE_RECOMMENDATION_JSON_FILE, TAGS_JSON_FILE
        
        storage = JsonStorage(ACTIVE_JSON_FILE if not is_recommendation else ACTIVE_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        
        comics_key = 'recommendations' if is_recommendation else 'comics'
        total_key = 'total_recommendations' if is_recommendation else 'total_comics'
        
        existing_ids = [c['id'] for c in db_data.get(comics_key, [])]
        checker = DuplicateChecker(existing_ids)
        
        # 无论导入到哪里，都从独立标签数据库读取标签
        tag_storage = JsonStorage(TAGS_JSON_FILE)
        tag_db_data = tag_storage.read()
        existing_tags = tag_db_data.get('tags', [])
        adapter = MetaDataAdapter(
            is_recommendation=is_recommendation,
            existing_tags=existing_tags,
            platform=None,
            platform_prefix=host_prefix,
            cover_path_prefix=host_prefix,
            prefer_remote_cover=(cover_path_mode == "remote_first"),
        )
        
        meta_json = None
        
        adapter_name = config_key
        if not adapter_name:
            return error_response(400, f"平台未声明配置键: {platform_name}")
        credential_status = get_query_status_for_adapter_name(adapter_name)
        if not bool(credential_status.get("configured", False)):
            return error_response(400, str(credential_status.get("message") or f"{platform_name} 平台未配置查询凭据"))
        
        if import_type == 'by_id':
            comic_id = data.get('comic_id')
            if not comic_id:
                return error_response(400, "缺少漫画ID")

            full_comic_id = _build_prefixed_id(host_prefix, comic_id)
            
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
                from protocol.platform_service import get_platform_service
                from protocol.platform_meta import split_prefixed_id
                
                platform_service = get_platform_service()
                download_dir = os.path.join(COMIC_DIR, host_prefix)
                os.makedirs(download_dir, exist_ok=True)
                
                for comic in new_comics:
                    try:
                        _platform_key, original_id, _manifest = split_prefixed_id(
                            comic['id'],
                            media_type="comic",
                        )
                        detail, success = platform_service.download_album(
                            platform_name,
                            original_id,
                            download_dir=download_dir,
                            show_progress=False
                        )
                        
                        if success:
                            downloaded_comics.append(comic['id'])
                            comic['total_page'] = normalize_total_page(
                                detail.get('local_pages', detail.get('pages_count', comic['total_page'])),
                                default=normalize_total_page(comic.get('total_page', 0))
                            )
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
                from protocol.platform_service import get_platform_service
                from core.utils import get_preview_pages
                from protocol.platform_meta import split_prefixed_id
                
                platform_service = get_platform_service()
                cover_dir = os.path.join(COVER_DIR, host_prefix)
                cover_url_prefix = host_prefix
                
                os.makedirs(cover_dir, exist_ok=True)
                
                for comic in new_comics:
                    comic_id = comic['id']
                    _platform_key, original_id, _manifest = split_prefixed_id(
                        comic_id,
                        media_type="comic",
                    )
                    cover_path = os.path.join(cover_dir, f"{original_id}.jpg")
                    
                    # 已有本地封面则跳过
                    if os.path.exists(cover_path):
                        comic['cover_path'] = f"/static/cover/{cover_url_prefix}/{original_id}.jpg"
                    else:
                        try:
                            # 通过 PlatformService 下载封面
                            detail, success = platform_service.download_cover(
                                platform_name,
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
                        total_page = normalize_total_page(comic.get('total_page', 0))
                        preview_pages = get_preview_pages(total_page)
                        
                        preview_urls = platform_service.get_preview_image_urls(
                            platform_name,
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
        
        # 保存新标签到独立标签数据库
        new_tags = converted_data.get("tags", [])
        if new_tags:
            def update_tags(data):
                existing_tag_ids = {t["id"] for t in data.get("tags", [])}
                for tag in new_tags:
                    if tag["id"] not in existing_tag_ids:
                        data.setdefault("tags", []).append(tag)
                        existing_tag_ids.add(tag["id"])
                        app_logger.info(f"添加新标签: {tag['id']} - {tag['name']}")
                data['last_updated'] = time.strftime("%Y-%m-%d")
                return data
            
            tag_storage.atomic_update(update_tags)
        
        app_logger.info(f"在线导入成功: 平台={platform_name}, 导入方式={import_type}, 目标={target}, 新增={len(new_comics)}, 跳过={len(skipped_ids)}, 下载成功={len(downloaded_comics)}, 下载失败={len(failed_downloads)}")
        
        return success_response({
            "imported_count": len(new_comics),
            "skipped_count": len(skipped_ids),
            "skipped_ids": skipped_ids,
            "downloaded_count": len(downloaded_comics),
            "failed_downloads": failed_downloads
        })
        
    except RuntimeError as e:
        error_logger.error(f"在线导入失败(配置): {e}")
        return error_response(400, str(e))
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
        result = database_organize_service.run("comic", "repair_cover")
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"整理数据库失败: {e}")
        return error_response(500, "服务器内部错误")


@comic_bp.route('/local-metadata/refresh', methods=['POST'])
@require_third_party(error_response)
def refresh_local_comic_metadata():
    """Refresh a single LOCAL comic metadata from third-party sources."""
    try:
        data = request.json or {}
        comic_id = str(data.get('comic_id') or '').strip()
        if not comic_id:
            return error_response(400, "missing parameter: comic_id")

        result = comic_service.refresh_local_comic_metadata(comic_id)
        if result.success:
            return success_response(result.data, result.message or "LOCAL 漫画详情已更新")
        return error_response(400, result.message or "LOCAL 漫画详情更新失败")
    except Exception as e:
        error_logger.error(f"refresh local comic metadata api failed: {e}")
        return error_response(500, "internal server error")


@comic_bp.route('/update/check', methods=['POST'])
def check_comic_update():
    """Check whether a comic has online updates."""
    try:
        data = request.json or {}
        comic_id = data.get('comic_id')
        if not comic_id:
            return error_response(400, "missing parameter: comic_id")

        result = comic_service.check_comic_update(comic_id)
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"Check comic update api failed: {e}")
        return error_response(500, "internal server error")


@comic_bp.route('/update/download', methods=['POST'])
def download_comic_update():
    """Download online updates for a comic and sync local page count."""
    try:
        data = request.json or {}
        comic_id = data.get('comic_id')
        force = bool(data.get('force', False))
        if not comic_id:
            return error_response(400, "missing parameter: comic_id")

        result = comic_service.download_comic_update(comic_id, force=force)
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"Download comic update api failed: {e}")
        return error_response(500, "internal server error")


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
        raw_content_type = str(data.get('content_type', '') or '').strip().lower()
        default_media_type = raw_content_type if raw_content_type in ['comic', 'video'] else 'comic'
        requested_platform = str(data.get('platform', '') or '').strip() or _get_default_platform_name(default_media_type)
        manifest = _resolve_platform_manifest(requested_platform)
        if manifest is None:
            return error_response(
                400,
                f"不支持的平台: {requested_platform}，支持的平台: {_list_supported_platform_labels()}",
            )
        platform_name = _resolve_manifest_platform_label(manifest)
        host_prefix = _resolve_manifest_host_prefix(manifest)
        if raw_content_type in ['comic', 'video']:
            content_type = raw_content_type
        else:
            content_type = _resolve_manifest_content_type(manifest)
        comic_id = data.get('comic_id')
        keyword = data.get('keyword')
        comic_ids = data.get('comic_ids')
        platform_list_id = data.get('platform_list_id')
        platform_list_name = data.get('platform_list_name', '')
        source = data.get('source', 'local')

        if import_type not in ['by_id', 'by_search', 'by_list', 'by_platform_list']:
            return error_response(400, "无效的导入方式，支持: by_id, by_search, by_list, by_platform_list")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")
        
        if content_type == 'comic' and import_type == 'by_id' and comic_id:
            full_comic_id = _build_prefixed_id(host_prefix, comic_id)
            
            from infrastructure.persistence.json_storage import JsonStorage
            db_file = JSON_FILE if target == 'home' else RECOMMENDATION_JSON_FILE
            storage = JsonStorage(db_file)
            db_data = storage.read()
            comics_key = 'comics' if target == 'home' else 'recommendations'
            
            existing_ids = {c['id'] for c in db_data.get(comics_key, [])}
            if full_comic_id in existing_ids:
                return error_response(400, f"漫画 {full_comic_id} 已存在")

        extra_data = {}
        if import_type == 'by_platform_list':
            if not platform_list_id:
                return error_response(400, "缺少平台清单ID: platform_list_id")
            comic_id = str(platform_list_id).strip()
            keyword = str(platform_list_name or '').strip()
            comic_ids = None
            extra_data = {
                "platform_list_id": comic_id,
                "platform_list_name": keyword,
                "source": str(source or 'local').strip().lower() or 'local',
            }
        
        # 创建异步任务
        from infrastructure.task_manager import task_manager
        task_id = task_manager.create_task(
            platform=platform_name,
            import_type=import_type,
            target=target,
            comic_id=comic_id,
            keyword=keyword,
            comic_ids=comic_ids,
            content_type=content_type,
            extra_data=extra_data
        )
        
        app_logger.info(
            f"创建异步导入任务: {task_id}, 内容类型={content_type}, 平台={platform_name}, 类型={import_type}, 目标={target}"
        )
        
        return success_response({
            "task_id": task_id,
            "message": "导入任务已创建",
            "content_type": content_type
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
