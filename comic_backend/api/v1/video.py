"""
视频 API 路由
"""

from flask import Blueprint, request, jsonify
from application.video_app_service import VideoAppService
from application.actor_app_service import ActorAppService
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time
import threading
import time

video_bp = Blueprint('video', __name__)
video_service = VideoAppService()
actor_service = ActorAppService()


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


@video_bp.route('/list', methods=['GET'])
def video_list():
    try:
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        
        result = video_service.get_video_list(sort_type, min_score, max_score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/detail', methods=['GET'])
def video_detail():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.get_video_detail(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(404, result.message)
    except Exception as e:
        error_logger.error(f"获取视频详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/search', methods=['GET'])
def video_search():
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少搜索关键词")
        
        result = video_service.search_videos(keyword)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/score', methods=['PUT'])
def update_score():
    try:
        data = request.json
        video_id = data.get('video_id')
        score = data.get('score')
        
        if not video_id or score is None:
            return error_response(400, "缺少参数")
        
        result = video_service.update_video_score(video_id, score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新评分失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/progress', methods=['PUT'])
def update_progress():
    try:
        data = request.json
        video_id = data.get('video_id')
        unit = data.get('unit')
        
        if not video_id or unit is None:
            return error_response(400, "缺少参数")
        
        result = video_service.update_video_progress(video_id, unit)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新进度失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/list', methods=['GET'])
def trash_list():
    try:
        result = video_service.get_trash_list()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取回收站列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/move', methods=['PUT'])
def move_to_trash():
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.move_to_trash(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"移至回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/restore', methods=['PUT'])
def restore_from_trash():
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.restore_from_trash(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/delete', methods=['DELETE'])
def delete_permanently():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.delete_permanently(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/import', methods=['POST'])
def import_video():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        result = video_service.import_video(data)
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"导入视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/import/batch', methods=['POST'])
def batch_import():
    try:
        data = request.json
        videos = data.get('videos', [])
        
        if not videos:
            return error_response(400, "缺少视频数据")
        
        result = video_service.batch_import_videos(videos)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量导入失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/tag/<tag_id>', methods=['GET'])
def get_by_tag(tag_id):
    try:
        result = video_service.get_videos_by_tag(tag_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取标签视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/actor/<actor_name>', methods=['GET'])
def get_by_actor(actor_name):
    try:
        result = video_service.get_videos_by_actor(actor_name)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取演员视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/search', methods=['GET'])
def third_party_search():
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少搜索关键词")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        
        app_logger.info(f"开始搜索视频，关键词: {keyword}")
        adapter = JavdbAdapter()
        videos = adapter.search_videos(keyword, max_pages=1)
        app_logger.info(f"搜索完成，找到 {len(videos)} 个视频")
        
        return success_response(videos)
    except Exception as e:
        import traceback
        error_logger.error(f"第三方搜索失败: {e}")
        error_logger.error(traceback.format_exc())
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/detail', methods=['GET'])
def third_party_detail():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        
        adapter = JavdbAdapter()
        detail = adapter.get_video_detail(video_id)
        
        if detail:
            return success_response(detail)
        else:
            return error_response(404, "视频不存在")
    except Exception as e:
        error_logger.error(f"获取第三方详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/actor/search', methods=['GET'])
def third_party_actor_search():
    try:
        actor_name = request.args.get('actor_name')
        if not actor_name:
            return error_response(400, "缺少演员名称")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        
        adapter = JavdbAdapter()
        actors = adapter.search_actor(actor_name)
        
        return success_response(actors)
    except Exception as e:
        error_logger.error(f"第三方演员搜索失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/actor/works', methods=['GET'])
def third_party_actor_works():
    try:
        actor_id = request.args.get('actor_id')
        page = request.args.get('page', 1, type=int)
        
        if not actor_id:
            return error_response(400, "缺少演员ID")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        
        adapter = JavdbAdapter()
        result = adapter.get_actor_works(actor_id, page=page, max_pages=1)
        
        return success_response(result)
    except Exception as e:
        error_logger.error(f"获取演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/import', methods=['POST'])
def third_party_import():
    try:
        data = request.json
        video_id = data.get('video_id')
        target = data.get('target', 'home')
        
        if not video_id:
            return error_response(400, "缺少视频ID")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        from core.constants import VIDEO_JSON_FILE, VIDEO_RECOMMENDATION_JSON_FILE, JAV_PICTURES_DIR, JAV_COVER_DIR
        from infrastructure.persistence.json_storage import JsonStorage
        
        adapter = JavdbAdapter()
        detail = adapter.get_video_detail(video_id)
        
        if not detail:
            return error_response(404, "视频不存在")
        
        db_file = VIDEO_JSON_FILE if target == 'home' else VIDEO_RECOMMENDATION_JSON_FILE
        storage = JsonStorage(db_file)
        db_data = storage.read()
        videos_key = 'videos' if target == 'home' else 'video_recommendations'
        
        video_id_full = f"JAVDB_{video_id}"
        
        existing_ids = {v['id'] for v in db_data.get(videos_key, [])}
        if video_id_full in existing_ids:
            return error_response(400, f"视频 {video_id_full} 已存在")
        
        video_data = {
            "id": video_id_full,
            "title": detail.get("title", ""),
            "code": detail.get("code", ""),
            "date": detail.get("date", ""),
            "series": detail.get("series", ""),
            "creator": detail.get("actors", [""])[0] if detail.get("actors") else "",
            "actors": detail.get("actors", []),
            "magnets": detail.get("magnets", []),
            "thumbnail_images": detail.get("thumbnail_images", []),
            "preview_video": detail.get("preview_video", ""),
            "tag_ids": [],
            "list_ids": [],
            "create_time": get_current_time(),
            "last_access_time": get_current_time()
        }
        
        if videos_key not in db_data:
            db_data[videos_key] = []
        db_data[videos_key].append(video_data)
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        cover_url = detail.get("cover_url", "")
        if cover_url:
            if target == 'home':
                video_service.download_cover_async(video_id_full, cover_url)
                video_service.download_high_quality_thumbnail_async(video_id_full, cover_url, JAV_PICTURES_DIR, JAV_COVER_DIR)
            else:
                video_service.download_cover_async_for_recommendation(video_id_full, cover_url, JAV_COVER_DIR)
        
        app_logger.info(f"视频导入成功: {video_id_full}, 目标: {target}")
        return success_response(video_data, "导入成功")
    except Exception as e:
        error_logger.error(f"第三方导入失败: {e}")
        return error_response(500, "服务器内部错误")


# ========== 视频推荐页 API ==========

@video_bp.route('/recommendation/list', methods=['GET'])
def get_video_recommendation_list():
    """获取推荐视频列表"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        filtered_videos = []
        for video in videos:
            if video.get('is_deleted'):
                continue
            if min_score is not None and (video.get('score') or 0) < min_score:
                continue
            filtered_videos.append(video)
        
        if sort_type == 'score':
            filtered_videos.sort(key=lambda x: (x.get('score') or 0), reverse=True)
        elif sort_type == 'date':
            filtered_videos.sort(key=lambda x: (x.get('date') or ''), reverse=True)
        else:
            filtered_videos.sort(key=lambda x: (x.get('create_time') or ''), reverse=True)
        
        return success_response(filtered_videos)
    except Exception as e:
        error_logger.error(f"获取推荐视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/detail', methods=['GET'])
def get_video_recommendation_detail():
    """获取推荐视频详情"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数: video_id")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        for video in videos:
            if video.get('id') == video_id:
                return success_response(video)
        
        return error_response(404, "视频不存在")
    except Exception as e:
        error_logger.error(f"获取推荐视频详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/score', methods=['PUT'])
def update_video_recommendation_score():
    """更新推荐视频评分"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_id = data.get('video_id')
        score = data.get('score')
        
        if not video_id or score is None:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['score'] = score
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "评分更新成功"})
    except Exception as e:
        error_logger.error(f"更新推荐视频评分失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/move', methods=['PUT'])
def move_video_recommendation_to_trash():
    """移动推荐视频到回收站"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['is_deleted'] = True
                video['deleted_time'] = get_current_time()
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "已移入回收站"})
    except Exception as e:
        error_logger.error(f"移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-move', methods=['PUT'])
def batch_move_video_recommendation_to_trash():
    """批量移动推荐视频到回收站"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        count = 0
        for video in videos:
            if video.get('id') in video_ids:
                video['is_deleted'] = True
                video['deleted_time'] = get_current_time()
                count += 1
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"moved_count": count}, f"已将 {count} 个视频移入回收站")
    except Exception as e:
        error_logger.error(f"批量移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/search', methods=['GET'])
def search_video_recommendations():
    """搜索推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        keyword = keyword.lower()
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        results = []
        for video in videos:
            if video.get('is_deleted'):
                continue
            title = video.get('title', '').lower()
            code = video.get('code', '').lower()
            actors = ' '.join(video.get('actors', [])).lower()
            if keyword in title or keyword in code or keyword in actors:
                results.append(video)
        
        return success_response(results)
    except Exception as e:
        error_logger.error(f"搜索推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


# ========== 视频播放相关 API ==========

@video_bp.route('/<video_id>/play-urls', methods=['GET'])
def get_video_play_urls(video_id):
    """获取视频播放链接（从 MissAV 和 Jable 提取）"""
    try:
        # 获取视频信息
        result = video_service.get_video_detail(video_id)
        if not result.success or not result.data:
            return error_response(404, "视频不存在")
        
        video = result.data
        code = video.get('code', '')
        
        if not code:
            return error_response(400, "视频没有番号信息")
        
        # 从两个源提取播放链接
        import sys
        import os
        _player_path = os.path.join(os.path.dirname(__file__), '..', '..', 'third_party', 'javdb-api-scraper')
        if _player_path not in sys.path:
            sys.path.insert(0, _player_path)
        from player.av_player_server import extract_from_missav, extract_from_jable
        
        sources = []
        
        # MissAV 源
        try:
            missav_result, missav_error = extract_from_missav(code)
            if missav_result:
                sources.append({
                    'name': 'MissAV',
                    'source': 'missav',
                    'streams': missav_result.get('streams', []),
                    'page_url': missav_result.get('page_url', ''),
                    'available': True
                })
            else:
                sources.append({
                    'name': 'MissAV',
                    'source': 'missav',
                    'available': False,
                    'error': missav_error
                })
        except Exception as e:
            sources.append({
                'name': 'MissAV',
                'source': 'missav',
                'available': False,
                'error': str(e)
            })
        
        # Jable 源
        try:
            jable_result, jable_error = extract_from_jable(code)
            if jable_result:
                sources.append({
                    'name': 'Jable',
                    'source': 'jable',
                    'streams': jable_result.get('streams', []),
                    'page_url': jable_result.get('page_url', ''),
                    'available': True
                })
            else:
                sources.append({
                    'name': 'Jable',
                    'source': 'jable',
                    'available': False,
                    'error': jable_error
                })
        except Exception as e:
            sources.append({
                'name': 'Jable',
                'source': 'jable',
                'available': False,
                'error': str(e)
            })
        
        return success_response({
            'video_id': video_id,
            'code': code,
            'title': video.get('title', ''),
            'sources': sources
        })
        
    except Exception as e:
        error_logger.error(f"获取播放链接失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/proxy/<domain>/<path:path>', methods=['GET'])
def proxy_video_request(domain, path):
    """代理视频请求，解决跨域问题"""
    try:
        from flask import Response
        from urllib.parse import unquote
        from curl_cffi import requests as cffi_requests
        
        query_string = request.query_string.decode()
        target_url = f"https://{domain}/{path}"
        if query_string:
            target_url += f"?{query_string}"
        
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        referer = request.headers.get('Referer', '')
        if 'jable' in domain:
            referer = f'https://{domain}/'
        elif 'missav' in domain or 'surrit' in domain:
            referer = 'https://missav.ai/'
        
        headers = {**HEADERS, 'Referer': referer}
        
        resp = cffi_requests.get(
            target_url,
            headers=headers,
            stream=True,
            timeout=30,
            impersonate="chrome120"
        )
        
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        resp_headers = [(n, v) for (n, v) in resp.headers.items() if n.lower() not in excluded]
        
        def generate():
            for chunk in resp.iter_content(chunk_size=1024):
                yield chunk
        
        return Response(generate(), status=resp.status_code, headers=resp_headers)
        
    except Exception as e:
        error_logger.error(f"代理请求失败: {e}")
        return Response(f'Proxy error: {str(e)}', status=500)


@video_bp.route('/proxy2', methods=['GET', 'POST'])
def proxy_video_request2():
    """代理视频请求（完整URL方式，支持重写m3u8）"""
    try:
        from flask import make_response
        from urllib.parse import urlparse, unquote, urljoin
        import base64
        import re
        from curl_cffi import requests as cffi_requests
        
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            url = data.get('url', '')
        else:
            query_string = request.query_string.decode()
            url = None
            for param in query_string.split('&'):
                if param.startswith('url='):
                    url = param[4:]
                    break
            
            if url:
                try:
                    url = base64.b64decode(url).decode('utf-8')
                except:
                    url = unquote(url)
        
        if not url:
            return Response('Missing url parameter', status=400)
        
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f'https://{url}'
        
        parsed = urlparse(url)
        
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        referer = request.headers.get('Referer', '')
        if 'jable' in parsed.netloc:
            referer = f'https://{parsed.netloc}/'
        elif 'missav' in parsed.netloc or 'surrit' in parsed.netloc or 'mushroom' in parsed.netloc:
            referer = 'https://missav.ai/'
        
        headers = {**HEADERS, 'Referer': referer}
        
        resp = cffi_requests.get(
            url,
            headers=headers,
            timeout=30,
            impersonate="chrome120"
        )
        
        content = resp.content
        content_type = resp.headers.get('Content-Type', '').lower()
        
        if 'mpegurl' in content_type or 'm3u8' in content_type or url.endswith('.m3u8'):
            content_text = content.decode('utf-8')
            base_url = url.rsplit('/', 1)[0]
            
            def replace_key_uri(m):
                full_match = m.group(0)
                method = m.group(1)
                key_uri = m.group(2)
                
                if not key_uri.startswith('http://') and not key_uri.startswith('https://'):
                    full_key_url = f"{base_url}/{key_uri}"
                    encoded_key_url = base64.b64encode(full_key_url.encode('utf-8')).decode('utf-8')
                    proxy_key_url = f"/api/v1/video/proxy2?url={encoded_key_url}"
                    return full_match.replace(key_uri, proxy_key_url)
                
                return full_match
            
            def replace_ts_uri(uri):
                if not uri.startswith('http://') and not uri.startswith('https://'):
                    full_ts_url = f"{base_url}/{uri}"
                    encoded_ts_url = base64.b64encode(full_ts_url.encode('utf-8')).decode('utf-8')
                    return f"/api/v1/video/proxy2?url={encoded_ts_url}"
                return uri
            
            content_text = re.sub(r'#EXT-X-KEY:METHOD=([^,]+),URI="([^"]+)"', replace_key_uri, content_text)
            
            lines = content_text.split('\n')
            new_lines = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    new_lines.append(replace_ts_uri(line.strip()))
                else:
                    new_lines.append(line)
            
            content_text = '\n'.join(new_lines)
            content = content_text.encode('utf-8')
        
        response = make_response(content)
        response.status_code = resp.status_code
        
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for n, v in resp.headers.items():
            if n.lower() not in excluded:
                response.headers[n] = v
        
        return response
        
    except Exception as e:
        error_logger.error(f"代理请求2失败: {e}")
        from flask import Response
        return Response(f'Proxy error: {str(e)}', status=500)
