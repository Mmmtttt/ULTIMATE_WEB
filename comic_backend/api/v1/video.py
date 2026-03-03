"""
视频 API 路由
"""

from flask import Blueprint, request, jsonify
from application.video_app_service import VideoAppService
from application.actor_app_service import ActorAppService
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
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
        
        adapter = JavdbAdapter()
        videos = adapter.search_videos(keyword, max_pages=1)
        
        return success_response(videos)
    except Exception as e:
        error_logger.error(f"第三方搜索失败: {e}")
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
        
        if not video_id:
            return error_response(400, "缺少视频ID")
        
        from third_party.javdb_api_scraper import JavdbAdapter
        
        adapter = JavdbAdapter()
        detail = adapter.get_video_detail(video_id)
        
        if not detail:
            return error_response(404, "视频不存在")
        
        video_data = {
            "id": f"JAVDB_{video_id}",
            "title": detail.get("title", ""),
            "code": detail.get("code", ""),
            "date": detail.get("date", ""),
            "series": detail.get("series", ""),
            "creator": detail.get("actors", [""])[0] if detail.get("actors") else "",
            "actors": detail.get("actors", []),
            "magnets": detail.get("magnets", []),
            "thumbnail_images": detail.get("thumbnail_images", []),
            "preview_video": detail.get("preview_video", ""),
            "tag_ids": []
        }
        
        result = video_service.import_video(video_data)
        if result.success:
            cover_url = detail.get("cover_url", "")
            if cover_url:
                video_service.download_cover_async(video_data["id"], cover_url)
            
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"第三方导入失败: {e}")
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
