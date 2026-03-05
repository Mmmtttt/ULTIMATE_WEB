from flask import Blueprint, request, jsonify, send_file
from application.recommendation_app_service import RecommendationAppService
from infrastructure.logger import app_logger, error_logger
from infrastructure.recommendation_cache_manager import recommendation_cache_manager
import os
import sys

recommendation_bp = Blueprint('recommendation', __name__)
recommendation_service = RecommendationAppService()


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


@recommendation_bp.route('/list', methods=['GET'])
def get_recommendation_list():
    """获取推荐漫画列表 - 支持排序和评分筛选"""
    try:
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        
        result = recommendation_service.get_recommendation_list(sort_type, min_score, max_score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取推荐列表失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/detail', methods=['GET'])
def get_recommendation_detail():
    """获取推荐漫画详情"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.get_recommendation_detail(recommendation_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(404, result.message)
    except Exception as e:
        error_logger.error(f"获取推荐详情失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/progress', methods=['PUT'])
def update_progress():
    """更新阅读进度"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data or 'current_page' not in data:
            return error_response(400, "缺少参数")
        
        recommendation_id = data['recommendation_id']
        current_page = data['current_page']
        
        result = recommendation_service.update_progress(recommendation_id, current_page)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"保存阅读进度失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/score', methods=['PUT'])
def update_score():
    """更新评分"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data or 'score' not in data:
            return error_response(400, "缺少参数: recommendation_id 或 score")
        
        recommendation_id = data['recommendation_id']
        score = data['score']
        
        result = recommendation_service.update_score(recommendation_id, score)
        if result.success:
            app_logger.info(f"更新评分成功: {recommendation_id}, 评分: {score}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新评分失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/tag/bind', methods=['PUT'])
def bind_tags():
    """绑定标签"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data or 'tag_id_list' not in data:
            return error_response(400, "缺少参数: recommendation_id 或 tag_id_list")
        
        recommendation_id = data['recommendation_id']
        tag_id_list = data['tag_id_list']
        
        result = recommendation_service.bind_tags(recommendation_id, tag_id_list)
        if result.success:
            app_logger.info(f"绑定标签成功: {recommendation_id}, 标签: {tag_id_list}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"绑定标签失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/edit', methods=['PUT'])
def edit_recommendation():
    """编辑推荐漫画元数据"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data:
            return error_response(400, "缺少参数: recommendation_id")
        
        recommendation_id = data['recommendation_id']
        meta = {
            'title': data.get('title'),
            'author': data.get('author'),
            'desc': data.get('desc'),
            'cover_path': data.get('cover_path')
        }
        meta = {k: v for k, v in meta.items() if v is not None}
        
        result = recommendation_service.update_meta(recommendation_id, meta)
        if result.success:
            app_logger.info(f"编辑推荐漫画成功: {recommendation_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"编辑推荐漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/search', methods=['GET'])
def search_recommendations():
    """搜索推荐漫画"""
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        result = recommendation_service.search(keyword)
        if result.success:
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(result.data)}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/filter', methods=['GET'])
def filter_recommendations():
    """根据标签筛选"""
    try:
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        
        result = recommendation_service.filter_by_tags(include_tag_ids, exclude_tag_ids)
        if result.success:
            app_logger.info(f"筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"筛选失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/tag/batch-add', methods=['PUT'])
def batch_add_tags():
    """批量添加标签"""
    try:
        data = request.json
        if not data or 'recommendation_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: recommendation_ids 或 tag_ids")
        
        recommendation_ids = data['recommendation_ids']
        tag_ids = data['tag_ids']
        
        result = recommendation_service.batch_add_tags(recommendation_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量添加标签成功: {len(recommendation_ids)}个推荐")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量添加标签失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/tag/batch-remove', methods=['PUT'])
def batch_remove_tags():
    """批量移除标签"""
    try:
        data = request.json
        if not data or 'recommendation_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: recommendation_ids 或 tag_ids")
        
        recommendation_ids = data['recommendation_ids']
        tag_ids = data['tag_ids']
        
        result = recommendation_service.batch_remove_tags(recommendation_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量移除标签成功: {len(recommendation_ids)}个推荐")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移除标签失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/add', methods=['POST'])
def add_recommendation():
    """添加新的推荐漫画"""
    try:
        data = request.json
        if not data or 'title' not in data:
            return error_response(400, "缺少参数: title")
        
        result = recommendation_service.add_recommendation(data)
        if result.success:
            app_logger.info(f"添加推荐漫画成功: {result.data['id']}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"添加推荐漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/delete', methods=['DELETE'])
def delete_recommendation():
    """删除推荐漫画"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.delete_recommendation(recommendation_id)
        if result.success:
            app_logger.info(f"删除推荐漫画成功: {recommendation_id}")
            return success_response(result.data)
        else:
            return error_response(404, result.message)
    except Exception as e:
        error_logger.error(f"删除推荐漫画失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/images', methods=['GET'])
def get_recommendation_images():
    """获取推荐漫画的图片列表 - 返回图床 URL 列表（保留作为技术储备）"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.get_recommendation_detail(recommendation_id)
        if not result.success:
            return error_response(404, result.message)
        
        detail = result.data
        total_page = detail.get('total_page', 0)
        
        image_urls = []
        for i in range(1, total_page + 1):
            image_url = f"https://cdn-msp.jmapinodeudzn.net/media/photos/{recommendation_id}/{i:05d}.webp"
            image_urls.append(image_url)
        
        app_logger.info(f"获取图片列表成功: {recommendation_id}, 共 {len(image_urls)} 张")
        return success_response(image_urls)
    except Exception as e:
        error_logger.error(f"获取图片列表失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/download', methods=['POST'])
def download_to_cache():
    """下载推荐漫画到缓存"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data:
            return error_response(400, "缺少参数: recommendation_id")
        
        recommendation_id = data['recommendation_id']
        
        if recommendation_cache_manager.is_cached(recommendation_id):
            cache_info = recommendation_cache_manager.get_cache_info(recommendation_id)
            app_logger.info(f"漫画已在缓存中: {recommendation_id}")
            return success_response({
                "status": "cached",
                "message": "漫画已在缓存中",
                "cache_info": cache_info
            })
        
        result = recommendation_service.get_recommendation_detail(recommendation_id)
        if not result.success:
            return error_response(404, result.message)
        
        detail = result.data
        total_page = detail.get('total_page', 0)
        
        from core.platform import get_platform_from_id, get_original_id, Platform
        from core.constants import JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR
        
        platform = get_platform_from_id(recommendation_id)
        original_id = get_original_id(recommendation_id)
        
        try:
            from third_party.platform_service import get_platform_service
            from core.constants import JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR
            
            platform_service = get_platform_service()
            download_dir = JM_RECOMMENDATION_CACHE_DIR if platform == Platform.JM else PK_RECOMMENDATION_CACHE_DIR
            
            album_detail, success = platform_service.download_album(
                platform,
                original_id,
                download_dir=download_dir,
                show_progress=False
            )
            
            if success:
                local_pages = album_detail.get('local_pages', album_detail.get('pages_count', 0))
                recommendation_cache_manager.add_to_cache(recommendation_id, local_pages)
                
                cached_pages_list = list(range(1, local_pages + 1))
                
                app_logger.info(f"下载漫画到缓存成功: {recommendation_id}, 页数: {local_pages}")
                return success_response({
                    "status": "downloaded",
                    "message": "下载成功",
                    "total_pages": total_page,
                    "cached_pages": cached_pages_list
                })
            else:
                return error_response(500, "下载失败")
        except Exception as e:
            error_logger.error(f"下载漫画失败: {e}")
            return error_response(500, f"下载失败: {str(e)}")
            
    except Exception as e:
        error_logger.error(f"下载到缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/image', methods=['GET'])
def get_cached_image():
    """从缓存获取图片"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        page_num = request.args.get('page_num', type=int)
        
        if not recommendation_id or not page_num:
            return error_response(400, "缺少参数: recommendation_id 或 page_num")
        
        image_path = recommendation_cache_manager.get_cached_page_path(recommendation_id, page_num)
        
        if image_path and os.path.exists(image_path):
            return send_file(image_path, mimetype='image/jpeg')
        else:
            return error_response(404, "图片不在缓存中")
            
    except Exception as e:
        error_logger.error(f"获取缓存图片失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/status', methods=['GET'])
def get_cache_status():
    """获取漫画缓存状态"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        is_cached = recommendation_cache_manager.is_cached(recommendation_id)
        cache_info = recommendation_cache_manager.get_cache_info(recommendation_id)
        
        if is_cached:
            cached_pages = recommendation_cache_manager.get_cached_pages(recommendation_id)
            return success_response({
                "is_cached": True,
                "cache_info": cache_info,
                "cached_pages": cached_pages,
                "cached_count": len(cached_pages)
            })
        else:
            return success_response({
                "is_cached": False,
                "cache_info": None,
                "cached_pages": [],
                "cached_count": 0
            })
            
    except Exception as e:
        error_logger.error(f"获取缓存状态失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        stats = recommendation_cache_manager.get_cache_stats()
        return success_response(stats)
    except Exception as e:
        error_logger.error(f"获取缓存统计失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/clear', methods=['DELETE'])
def clear_cache():
    """清空缓存"""
    try:
        count, freed_size = recommendation_cache_manager.clear_cache()
        return success_response({
            "cleared_count": count,
            "freed_size_bytes": freed_size,
            "freed_size_mb": round(freed_size / (1024 * 1024), 2)
        })
    except Exception as e:
        error_logger.error(f"清空缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/cache/remove', methods=['DELETE'])
def remove_from_cache():
    """从缓存中移除指定漫画"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        success = recommendation_cache_manager.remove_from_cache(recommendation_id)
        if success:
            return success_response({"message": "移除成功"})
        else:
            return error_response(404, "漫画不在缓存中")
            
    except Exception as e:
        error_logger.error(f"移除缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/list', methods=['GET'])
def get_trash_list():
    """获取回收站漫画列表"""
    try:
        result = recommendation_service.get_trash_list()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取回收站列表失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/move', methods=['PUT'])
def move_to_trash():
    """移动漫画到回收站"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.move_to_trash(data['recommendation_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"移入回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/restore', methods=['PUT'])
def restore_from_trash():
    """从回收站恢复漫画"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.restore_from_trash(data['recommendation_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/batch-move', methods=['PUT'])
def batch_move_to_trash():
    """批量移动漫画到回收站"""
    try:
        data = request.json
        if not data or 'recommendation_ids' not in data:
            return error_response(400, "缺少参数: recommendation_ids")
        
        result = recommendation_service.batch_move_to_trash(data['recommendation_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移入回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/batch-restore', methods=['PUT'])
def batch_restore_from_trash():
    """批量从回收站恢复漫画"""
    try:
        data = request.json
        if not data or 'recommendation_ids' not in data:
            return error_response(400, "缺少参数: recommendation_ids")
        
        result = recommendation_service.batch_restore_from_trash(data['recommendation_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/delete', methods=['DELETE'])
def delete_permanently():
    """永久删除漫画"""
    try:
        data = request.json
        if not data or 'recommendation_id' not in data:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.delete_permanently(data['recommendation_id'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


@recommendation_bp.route('/trash/batch-delete', methods=['DELETE'])
def batch_delete_permanently():
    """批量永久删除漫画"""
    try:
        data = request.json
        if not data or 'recommendation_ids' not in data:
            return error_response(400, "缺少参数: recommendation_ids")
        
        result = recommendation_service.batch_delete_permanently(data['recommendation_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量永久删除失败: {e}")
        return error_response(500, "服务器内部错误")
