from flask import Blueprint, request, jsonify
from application.recommendation_app_service import RecommendationAppService
from infrastructure.logger import app_logger, error_logger

recommendation_bp = Blueprint('recommendation', __name__)
recommendation_service = RecommendationAppService()


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
    """获取推荐漫画的图片列表 - 返回图床 URL 列表"""
    try:
        recommendation_id = request.args.get('recommendation_id')
        if not recommendation_id:
            return error_response(400, "缺少参数: recommendation_id")
        
        result = recommendation_service.get_recommendation_detail(recommendation_id)
        if not result.success:
            return error_response(404, result.message)
        
        # 从详情中获取图片列表（存储在 JSON 中）
        detail = result.data
        total_page = detail.get('total_page', 0)
        
        # 假设图片 URL 按页码存储，格式为 cover_path 中的基础 URL + 页码
        base_url = detail.get('cover_path', '').rsplit('/', 1)[0] if detail.get('cover_path') else ''
        
        # 构建图片 URL 列表
        image_urls = []
        for i in range(1, total_page + 1):
            # 根据你的图床格式调整 URL 构建逻辑
            image_url = f"{base_url}/{i:03d}.jpg" if base_url else ""
            image_urls.append(image_url)
        
        app_logger.info(f"获取图片列表成功: {recommendation_id}, 共 {len(image_urls)} 张")
        return success_response(image_urls)
    except Exception as e:
        error_logger.error(f"获取图片列表失败: {e}")
        return error_response(500, "服务器内部错误")
