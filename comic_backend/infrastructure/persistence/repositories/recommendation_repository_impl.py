from typing import List, Optional
from domain.recommendation import Recommendation, RecommendationRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_date
from core.constants import RECOMMENDATION_JSON_FILE


class RecommendationJsonRepository(RecommendationRepository):
    """推荐漫画 JSON 仓库实现 - 使用独立的 JSON 文件存储"""
    
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage(RECOMMENDATION_JSON_FILE)
    
    def get_by_id(self, recommendation_id: str) -> Optional[Recommendation]:
        """根据ID获取推荐漫画"""
        data = self._storage.read()
        recommendations = data.get("recommendations", [])
        rec_data = next((r for r in recommendations if r["id"] == recommendation_id), None)
        return Recommendation.from_dict(rec_data) if rec_data else None
    
    def get_all(self) -> List[Recommendation]:
        """获取所有推荐漫画"""
        data = self._storage.read()
        recommendations = data.get("recommendations", [])
        return [Recommendation.from_dict(r) for r in recommendations]
    
    def save(self, recommendation: Recommendation) -> bool:
        """保存推荐漫画 - 使用原子更新防止并发竞争"""
        try:
            app_logger.info(f"[RecommendationRepo.save] 保存推荐: id={recommendation.id}")
            
            def update_data(data):
                recommendations = data.get("recommendations", [])
                
                index = next((i for i, r in enumerate(recommendations) if r["id"] == recommendation.id), -1)
                
                if index >= 0:
                    recommendations[index] = recommendation.to_dict()
                else:
                    recommendations.append(recommendation.to_dict())
                
                data["recommendations"] = recommendations
                data["total_recommendations"] = len(recommendations)
                data["last_updated"] = get_current_date()
                return data
            
            result = self._storage.atomic_update(update_data)
            app_logger.info(f"[RecommendationRepo.save] 写入结果: {result}")
            return result
        except Exception as e:
            error_logger.error(f"保存推荐漫画失败: {e}")
            return False
    
    def delete(self, recommendation_id: str) -> bool:
        """删除推荐漫画 - 使用原子更新防止并发竞争"""
        try:
            def update_data(data):
                recommendations = data.get("recommendations", [])
                recommendations = [r for r in recommendations if r["id"] != recommendation_id]
                data["recommendations"] = recommendations
                data["total_recommendations"] = len(recommendations)
                data["last_updated"] = get_current_date()
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"删除推荐漫画失败: {e}")
            return False
    
    def search(self, keyword: str) -> List[Recommendation]:
        """搜索推荐漫画"""
        data = self._storage.read()
        recommendations = data.get("recommendations", [])
        keyword_lower = keyword.lower()
        
        results = []
        for r in recommendations:
            if (keyword_lower in r.get("title", "").lower() or
                keyword_lower in r.get("author", "").lower() or
                keyword_lower in r.get("desc", "").lower()):
                results.append(Recommendation.from_dict(r))
        
        return results
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Recommendation]:
        """根据标签筛选"""
        data = self._storage.read()
        recommendations = data.get("recommendations", [])
        
        results = []
        for r in recommendations:
            tag_ids = set(r.get("tag_ids", []))
            
            # 检查是否包含所有必需标签
            if include_tags and not all(tag in tag_ids for tag in include_tags):
                continue
            
            # 检查是否包含任何排除标签
            if exclude_tags and any(tag in tag_ids for tag in exclude_tags):
                continue
            
            results.append(Recommendation.from_dict(r))
        
        return results
