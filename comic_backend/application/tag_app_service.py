from typing import List
from domain.tag import Tag, TagRepository
from domain.comic import ComicRepository
from domain.recommendation import RecommendationRepository
from domain.video import VideoRepository
from infrastructure.persistence.repositories import TagJsonRepository, ComicJsonRepository, RecommendationJsonRepository, VideoJsonRepository, VideoRecommendationJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time
from core.enums import ContentType


class TagAppService:
    def __init__(
        self,
        tag_repo: TagRepository = None,
        comic_repo: ComicRepository = None,
        recommendation_repo: RecommendationRepository = None,
        video_repo: VideoRepository = None,
        video_recommendation_repo=None
    ):
        self._tag_repo = tag_repo or TagJsonRepository()
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._recommendation_repo = recommendation_repo or RecommendationJsonRepository()
        self._video_repo = video_repo or VideoJsonRepository()
        self._video_recommendation_repo = video_recommendation_repo or VideoRecommendationJsonRepository()
    
    def get_tag_list(self, content_type: ContentType = ContentType.COMIC) -> ServiceResult:
        try:
            tags = self._tag_repo.get_all(content_type)
            
            tag_count = {}
            if content_type == ContentType.COMIC:
                comics = self._comic_repo.get_all()
                recommendations = self._recommendation_repo.get_all()
                
                for comic in comics:
                    if comic.is_deleted:
                        continue
                    for tag_id in comic.tag_ids:
                        tag_count[tag_id] = tag_count.get(tag_id, 0) + 1
                
                for recommendation in recommendations:
                    if recommendation.is_deleted:
                        continue
                    for tag_id in recommendation.tag_ids:
                        tag_count[tag_id] = tag_count.get(tag_id, 0) + 1
                
                count_key = "comic_count"
            else:
                videos = self._video_repo.get_all()
                video_recommendations = self._video_recommendation_repo.get_all()
                
                for video in videos:
                    if video.is_deleted:
                        continue
                    for tag_id in video.tag_ids:
                        tag_count[tag_id] = tag_count.get(tag_id, 0) + 1
                
                for video_rec in video_recommendations:
                    if video_rec.is_deleted:
                        continue
                    for tag_id in video_rec.tag_ids:
                        tag_count[tag_id] = tag_count.get(tag_id, 0) + 1
                
                count_key = "video_count"
            
            tag_list = []
            for t in tags:
                tag_info = {
                    "id": t.id,
                    "name": t.name,
                    count_key: tag_count.get(t.id, 0)
                }
                tag_list.append(tag_info)
            
            app_logger.info(f"获取标签列表成功，共 {len(tag_list)} 个标签")
            return ServiceResult.ok(tag_list)
        except Exception as e:
            error_logger.error(f"获取标签列表失败: {e}")
            return ServiceResult.error("获取标签列表失败")
    
    def create_tag(self, name: str, content_type: ContentType = ContentType.COMIC) -> ServiceResult:
        try:
            if self._tag_repo.exists_by_name(name, content_type):
                return ServiceResult.error("标签名称已存在")
            
            tag = self._tag_repo.create(name, content_type)
            
            if not tag:
                return ServiceResult.error("创建标签失败")
            
            app_logger.info(f"创建标签成功: {name}")
            return ServiceResult.ok({"id": tag.id, "name": tag.name}, "创建成功")
        except Exception as e:
            error_logger.error(f"创建标签失败: {e}")
            return ServiceResult.error("创建标签失败")
    
    def update_tag(self, tag_id: str, name: str) -> ServiceResult:
        try:
            tag = self._tag_repo.get_by_id(tag_id)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            existing_tag = self._tag_repo.get_by_id(tag_id)
            if existing_tag and existing_tag.name == name:
                pass
            elif self._tag_repo.exists_by_name(name, tag.content_type):
                return ServiceResult.error("标签名称已存在")
            
            tag.update_name(name)
            
            if not self._tag_repo.save(tag):
                return ServiceResult.error("更新标签失败")
            
            app_logger.info(f"更新标签成功: {tag_id}")
            return ServiceResult.ok({"id": tag.id, "name": tag.name}, "更新成功")
        except Exception as e:
            error_logger.error(f"更新标签失败: {e}")
            return ServiceResult.error("更新标签失败")
    
    def delete_tag(self, tag_id: str) -> ServiceResult:
        try:
            tag = self._tag_repo.get_by_id(tag_id)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            if not self._tag_repo.delete(tag_id):
                return ServiceResult.error("删除标签失败")
            
            app_logger.info(f"删除标签成功: {tag_id}")
            return ServiceResult.ok({"id": tag_id}, "删除成功")
        except Exception as e:
            error_logger.error(f"删除标签失败: {e}")
            return ServiceResult.error("删除标签失败")
    
    def get_comics_by_tag(self, tag_id: str) -> ServiceResult:
        try:
            tag = self._tag_repo.get_by_id(tag_id)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            home_comics = []
            comics = self._comic_repo.filter_by_tags([tag_id], [])
            for c in comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "source": "home"
                }
                home_comics.append(comic_info)
            
            recommendation_comics = []
            recommendations = self._recommendation_repo.filter_by_tags([tag_id], [])
            for r in recommendations:
                rec_info = {
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": r.total_page,
                    "score": r.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "source": "recommendation"
                }
                recommendation_comics.append(rec_info)
            
            result = {
                "tag": {"id": tag.id, "name": tag.name},
                "home_comics": home_comics,
                "recommendation_comics": recommendation_comics,
                "home_count": len(home_comics),
                "recommendation_count": len(recommendation_comics),
                "total_count": len(home_comics) + len(recommendation_comics)
            }
            
            app_logger.info(f"获取标签下漫画成功: {tag_id}, 主页: {len(home_comics)}, 推荐: {len(recommendation_comics)}")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取标签下漫画失败: {e}")
            return ServiceResult.error("获取标签下漫画失败")

    def get_videos_by_tag(self, tag_id: str) -> ServiceResult:
        try:
            tag = self._tag_repo.get_by_id(tag_id)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            home_videos = []
            videos = self._video_repo.filter_by_tags([tag_id], [])
            for v in videos:
                if v.is_deleted:
                    continue
                video_info = {
                    "id": v.id,
                    "title": v.title,
                    "code": v.code,
                    "cover_path": v.cover_path,
                    "date": v.date,
                    "score": v.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids],
                    "source": "home"
                }
                home_videos.append(video_info)
            
            recommendation_videos = []
            recommendations = self._video_recommendation_repo.filter_by_tags([tag_id], [])
            for r in recommendations:
                rec_info = {
                    "id": r.id,
                    "title": r.title,
                    "code": r.code,
                    "cover_path": r.cover_path,
                    "date": r.date,
                    "score": r.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "source": "recommendation"
                }
                recommendation_videos.append(rec_info)
            
            result = {
                "tag": {"id": tag.id, "name": tag.name},
                "home_videos": home_videos,
                "recommendation_videos": recommendation_videos,
                "home_count": len(home_videos),
                "recommendation_count": len(recommendation_videos),
                "total_count": len(home_videos) + len(recommendation_videos)
            }
            
            app_logger.info(f"获取标签下视频成功: {tag_id}, 主页: {len(home_videos)}, 推荐: {len(recommendation_videos)}")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取标签下视频失败: {e}")
            return ServiceResult.error("获取标签下视频失败")

    def get_all_comics(self) -> ServiceResult:
        try:
            tags = self._tag_repo.get_all(ContentType.COMIC)
            tag_map = {t.id: t.name for t in tags}
            
            home_comics = []
            comics = self._comic_repo.get_all()
            for c in comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "tag_ids": c.tag_ids,
                    "source": "home"
                }
                home_comics.append(comic_info)
            
            recommendation_comics = []
            recommendations = self._recommendation_repo.get_all()
            for r in recommendations:
                rec_info = {
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": r.total_page,
                    "score": r.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "tag_ids": r.tag_ids,
                    "source": "recommendation"
                }
                recommendation_comics.append(rec_info)
            
            result = {
                "home_comics": home_comics,
                "recommendation_comics": recommendation_comics,
                "home_count": len(home_comics),
                "recommendation_count": len(recommendation_comics),
                "total_count": len(home_comics) + len(recommendation_comics)
            }
            
            app_logger.info(f"获取所有漫画成功, 主页: {len(home_comics)}, 推荐: {len(recommendation_comics)}")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取所有漫画失败: {e}")
            return ServiceResult.error("获取所有漫画失败")
    
    def get_all_videos(self) -> ServiceResult:
        try:
            tags = self._tag_repo.get_all(ContentType.VIDEO)
            tag_map = {t.id: t.name for t in tags}
            
            home_videos = []
            video_list = self._video_repo.get_all()
            for v in video_list:
                if v.is_deleted:
                    continue
                video_info = {
                    "id": v.id,
                    "title": v.title,
                    "code": v.code,
                    "cover_path": v.cover_path,
                    "date": v.date,
                    "score": v.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids],
                    "tag_ids": v.tag_ids,
                    "source": "home"
                }
                home_videos.append(video_info)
            
            recommendation_videos = []
            rec_list = self._video_recommendation_repo.get_all()
            for r in rec_list:
                rec_info = {
                    "id": r.id,
                    "title": r.title,
                    "code": r.code,
                    "cover_path": r.cover_path,
                    "date": r.date,
                    "score": r.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "tag_ids": r.tag_ids,
                    "source": "recommendation"
                }
                recommendation_videos.append(rec_info)
            
            result = {
                "home_videos": home_videos,
                "recommendation_videos": recommendation_videos,
                "home_count": len(home_videos),
                "recommendation_count": len(recommendation_videos),
                "total_count": len(home_videos) + len(recommendation_videos)
            }
            
            app_logger.info(f"获取所有视频成功, 主页: {len(home_videos)}, 推荐: {len(recommendation_videos)}")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取所有视频失败: {e}")
            return ServiceResult.error("获取所有视频失败")

    def batch_add_tags(self, comic_data: List[dict], tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            home_updated = 0
            rec_updated = 0
            
            for item in comic_data:
                comic_id = item.get('id')
                source = item.get('source')
                
                if source == 'home':
                    comic = self._comic_repo.get_by_id(comic_id)
                    if comic:
                        comic.add_tags(tag_ids)
                        if self._comic_repo.save(comic):
                            home_updated += 1
                elif source == 'recommendation':
                    recommendation = self._recommendation_repo.get_by_id(comic_id)
                    if recommendation:
                        recommendation.add_tags(tag_ids)
                        if self._recommendation_repo.save(recommendation):
                            rec_updated += 1
            
            total_updated = home_updated + rec_updated
            if total_updated == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量添加标签成功: 主页{home_updated}个, 推荐{rec_updated}个, 标签: {tag_ids}")
            return ServiceResult.ok({
                "home_updated": home_updated,
                "recommendation_updated": rec_updated,
                "total_updated": total_updated,
                "tag_ids": tag_ids
            }, f"成功为{total_updated}个漫画添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")

    def batch_remove_tags(self, comic_data: List[dict], tag_ids: List[str]) -> ServiceResult:
        try:
            home_updated = 0
            rec_updated = 0
            
            for item in comic_data:
                comic_id = item.get('id')
                source = item.get('source')
                
                if source == 'home':
                    comic = self._comic_repo.get_by_id(comic_id)
                    if comic:
                        comic.remove_tags(tag_ids)
                        if self._comic_repo.save(comic):
                            home_updated += 1
                elif source == 'recommendation':
                    recommendation = self._recommendation_repo.get_by_id(comic_id)
                    if recommendation:
                        recommendation.remove_tags(tag_ids)
                        if self._recommendation_repo.save(recommendation):
                            rec_updated += 1
            
            total_updated = home_updated + rec_updated
            if total_updated == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移除标签成功: 主页{home_updated}个, 推荐{rec_updated}个, 标签: {tag_ids}")
            return ServiceResult.ok({
                "home_updated": home_updated,
                "recommendation_updated": rec_updated,
                "total_updated": total_updated,
                "tag_ids": tag_ids
            }, f"成功从{total_updated}个漫画移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
    
    def batch_add_tags_to_videos(self, video_data: List[dict], tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            home_updated = 0
            rec_updated = 0
            
            for item in video_data:
                video_id = item.get('id')
                source = item.get('source')
                
                if source == 'home':
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.add_tags(tag_ids)
                        if self._video_repo.save(video):
                            home_updated += 1
                elif source == 'recommendation':
                    recommendation = self._video_recommendation_repo.get_by_id(video_id)
                    if recommendation:
                        recommendation.add_tags(tag_ids)
                        if self._video_recommendation_repo.save(recommendation):
                            rec_updated += 1
            
            total_updated = home_updated + rec_updated
            if total_updated == 0:
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量添加标签成功: 主页{home_updated}个, 推荐{rec_updated}个, 标签: {tag_ids}")
            return ServiceResult.ok({
                "home_updated": home_updated,
                "recommendation_updated": rec_updated,
                "total_updated": total_updated,
                "tag_ids": tag_ids
            }, f"成功为{total_updated}个视频添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags_from_videos(self, video_data: List[dict], tag_ids: List[str]) -> ServiceResult:
        try:
            home_updated = 0
            rec_updated = 0
            
            for item in video_data:
                video_id = item.get('id')
                source = item.get('source')
                
                if source == 'home':
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.remove_tags(tag_ids)
                        if self._video_repo.save(video):
                            home_updated += 1
                elif source == 'recommendation':
                    recommendation = self._video_recommendation_repo.get_by_id(video_id)
                    if recommendation:
                        recommendation.remove_tags(tag_ids)
                        if self._video_recommendation_repo.save(recommendation):
                            rec_updated += 1
            
            total_updated = home_updated + rec_updated
            if total_updated == 0:
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量移除标签成功: 主页{home_updated}个, 推荐{rec_updated}个, 标签: {tag_ids}")
            return ServiceResult.ok({
                "home_updated": home_updated,
                "recommendation_updated": rec_updated,
                "total_updated": total_updated,
                "tag_ids": tag_ids
            }, f"成功从{total_updated}个视频移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
