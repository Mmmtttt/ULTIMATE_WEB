from typing import List as ListType, Optional
from domain.list import List, ListRepository
from domain.comic import ComicRepository
from domain.video import VideoRepository
from domain.recommendation import RecommendationRepository
from domain.video_recommendation import VideoRecommendationRepository
from infrastructure.persistence.repositories import ListJsonRepository, ComicJsonRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id
from core.enums import ContentType


class ListAppService:
    DEFAULT_COMIC_LIST_ID = "list_favorites_comic"
    DEFAULT_VIDEO_LIST_ID = "list_favorites_video"
    
    def __init__(
        self,
        list_repo: ListRepository = None,
        comic_repo: ComicRepository = None,
        video_repo: VideoRepository = None,
        rec_repo: RecommendationRepository = None,
        video_rec_repo: VideoRecommendationRepository = None
    ):
        self._list_repo = list_repo or ListJsonRepository()
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._video_repo = video_repo or VideoJsonRepository()
        self._rec_repo = rec_repo or RecommendationJsonRepository()
        self._video_rec_repo = video_rec_repo or VideoRecommendationJsonRepository()
    
    def get_list_all(self, content_type_str: str = None) -> ServiceResult:
        try:
            self._list_repo.ensure_default_list()
            
            content_type = None
            if content_type_str:
                try:
                    content_type = ContentType(content_type_str)
                except ValueError:
                    pass
            
            lists = self._list_repo.get_all(content_type)
            
            result = []
            for lst in lists:
                comic_count = self._list_repo.get_comic_count(lst.id)
                video_count = self._list_repo.get_video_count(lst.id)
                result.append({
                    "id": lst.id,
                    "name": lst.name,
                    "desc": lst.desc,
                    "content_type": lst.content_type.value,
                    "is_default": lst.is_default,
                    "comic_count": comic_count,
                    "video_count": video_count,
                    "create_time": lst.create_time
                })
            
            app_logger.info(f"获取清单列表成功，共 {len(result)} 个清单")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取清单列表失败: {e}")
            return ServiceResult.error("获取清单列表失败")
    
    def get_list_detail(self, list_id: str) -> ServiceResult:
        try:
            self._list_repo.ensure_default_list()
            
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            comics = self._comic_repo.get_all()
            list_comics = [c for c in comics if list_id in c.list_ids and not c.is_deleted]
            
            recommendations = self._rec_repo.get_all()
            list_recommendations = [r for r in recommendations if list_id in r.list_ids and not r.is_deleted]
            
            videos = self._video_repo.get_all()
            list_videos = [v for v in videos if list_id in v.list_ids and not v.is_deleted]
            
            video_recommendations = self._video_rec_repo.get_all()
            list_video_recommendations = [vr for vr in video_recommendations if list_id in vr.list_ids and not vr.is_deleted]
            
            comic_list = []
            for c in list_comics:
                comic_list.append({
                    "id": c.id,
                    "title": c.title,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "current_page": c.current_page,
                    "score": c.score,
                    "tag_ids": c.tag_ids,
                    "last_read_time": c.last_access_time,
                    "create_time": c.create_time,
                    "content_type": "comic",
                    "source": "local"
                })
            
            for r in list_recommendations:
                comic_list.append({
                    "id": r.id,
                    "title": r.title,
                    "cover_path": r.cover_path,
                    "total_page": r.total_page,
                    "current_page": r.current_page,
                    "score": r.score,
                    "tag_ids": r.tag_ids,
                    "last_read_time": r.last_read_time,
                    "create_time": r.create_time,
                    "content_type": "comic",
                    "source": "preview"
                })
            
            video_list = []
            for v in list_videos:
                video_list.append({
                    "id": v.id,
                    "title": v.title,
                    "cover_path": v.cover_path,
                    "score": v.score,
                    "tag_ids": v.tag_ids,
                    "last_read_time": v.last_access_time,
                    "create_time": v.create_time,
                    "content_type": "video",
                    "source": "local",
                    "code": v.code,
                    "actors": v.actors
                })
            
            for vr in list_video_recommendations:
                video_list.append({
                    "id": vr.id,
                    "title": vr.title,
                    "cover_path": vr.cover_path,
                    "score": vr.score,
                    "tag_ids": vr.tag_ids,
                    "last_read_time": vr.last_access_time,
                    "create_time": vr.create_time,
                    "content_type": "video",
                    "source": "preview",
                    "code": vr.code,
                    "actors": vr.actors
                })
            
            result = {
                "id": lst.id,
                "name": lst.name,
                "desc": lst.desc,
                "content_type": lst.content_type.value,
                "is_default": lst.is_default,
                "comic_count": len(comic_list),
                "video_count": len(video_list),
                "create_time": lst.create_time,
                "comics": comic_list,
                "videos": video_list
            }
            
            app_logger.info(f"获取清单详情成功: {list_id}")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取清单详情失败: {e}")
            return ServiceResult.error("获取清单详情失败")
    
    def create_list(self, name: str, desc: str = "", content_type_str: str = "comic") -> ServiceResult:
        try:
            if not name or not name.strip():
                return ServiceResult.error("清单名称不能为空")
            
            try:
                content_type = ContentType(content_type_str)
            except ValueError:
                return ServiceResult.error("无效的内容类型")
            
            if self._list_repo.exists_by_name(name, content_type):
                return ServiceResult.error("清单名称已存在")
            
            lst = self._list_repo.create(name, desc, content_type)
            if not lst:
                return ServiceResult.error("创建清单失败")
            
            app_logger.info(f"创建清单成功: {lst.id}, 名称: {name}, 类型: {content_type_str}")
            return ServiceResult.ok({
                "id": lst.id,
                "name": lst.name,
                "desc": lst.desc,
                "content_type": lst.content_type.value,
                "is_default": lst.is_default,
                "create_time": lst.create_time
            }, "创建清单成功")
        except Exception as e:
            error_logger.error(f"创建清单失败: {e}")
            return ServiceResult.error("创建清单失败")
    
    def update_list(self, list_id: str, name: str = None, desc: str = None) -> ServiceResult:
        try:
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            if name and name != lst.name:
                if not name.strip():
                    return ServiceResult.error("清单名称不能为空")
                if self._list_repo.exists_by_name(name, lst.content_type):
                    return ServiceResult.error("清单名称已存在")
            
            lst.update(name, desc)
            
            if not self._list_repo.save(lst):
                return ServiceResult.error("更新清单失败")
            
            app_logger.info(f"更新清单成功: {list_id}")
            return ServiceResult.ok({
                "id": lst.id,
                "name": lst.name,
                "desc": lst.desc
            }, "更新清单成功")
        except Exception as e:
            error_logger.error(f"更新清单失败: {e}")
            return ServiceResult.error("更新清单失败")
    
    def delete_list(self, list_id: str) -> ServiceResult:
        try:
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            if lst.is_default:
                return ServiceResult.error("默认清单不能删除")
            
            if not self._list_repo.delete(list_id):
                return ServiceResult.error("删除清单失败")
            
            app_logger.info(f"删除清单成功: {list_id}")
            return ServiceResult.ok({"id": list_id}, "删除清单成功")
        except Exception as e:
            error_logger.error(f"删除清单失败: {e}")
            return ServiceResult.error("删除清单失败")
    
    def bind_comics(self, list_id: str, comic_ids: ListType[str], source: str = "local") -> ServiceResult:
        try:
            app_logger.info(f"[bind_comics] 开始绑定: list_id={list_id}, comic_ids={comic_ids}, source={source}")
            
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                app_logger.error(f"[bind_comics] 清单不存在: {list_id}")
                return ServiceResult.error("清单不存在")
            
            updated_count = 0
            repo = self._comic_repo if source == "local" else self._rec_repo
            
            for comic_id in comic_ids:
                comic = repo.get_by_id(comic_id)
                if comic:
                    app_logger.info(f"[bind_comics] 找到漫画: {comic_id}, 当前list_ids={comic.list_ids}")
                    comic.add_to_list(list_id)
                    app_logger.info(f"[bind_comics] 添加后list_ids={comic.list_ids}")
                    save_result = repo.save(comic)
                    app_logger.info(f"[bind_comics] 保存结果: {save_result}")
                    if save_result:
                        updated_count += 1
                else:
                    app_logger.warning(f"[bind_comics] 漫画不存在: {comic_id}")
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量加入清单成功: 清单 {list_id}, {updated_count}个漫画")
            return ServiceResult.ok({
                "list_id": list_id,
                "updated_count": updated_count
            }, f"成功将{updated_count}个漫画加入清单")
        except Exception as e:
            error_logger.error(f"批量加入清单失败: {e}")
            return ServiceResult.error("批量加入清单失败")
    
    def remove_comics(self, list_id: str, comic_ids: ListType[str], source: str = "local") -> ServiceResult:
        try:
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            updated_count = 0
            repo = self._comic_repo if source == "local" else self._rec_repo
            
            for comic_id in comic_ids:
                comic = repo.get_by_id(comic_id)
                if comic:
                    comic.remove_from_list(list_id)
                    if repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移出清单成功: 清单 {list_id}, {updated_count}个漫画")
            return ServiceResult.ok({
                "list_id": list_id,
                "updated_count": updated_count
            }, f"成功将{updated_count}个漫画移出清单")
        except Exception as e:
            error_logger.error(f"批量移出清单失败: {e}")
            return ServiceResult.error("批量移出清单失败")
    
    def toggle_favorite(self, comic_id: str, source: str = "local") -> ServiceResult:
        try:
            self._list_repo.ensure_default_list()
            
            repo = self._comic_repo if source == "local" else self._rec_repo
            comic = repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            is_favorited = self.DEFAULT_COMIC_LIST_ID in comic.list_ids
            
            if is_favorited:
                comic.remove_from_list(self.DEFAULT_COMIC_LIST_ID)
                action = "取消收藏"
            else:
                comic.add_to_list(self.DEFAULT_COMIC_LIST_ID)
                action = "收藏"
            
            if not repo.save(comic):
                return ServiceResult.error(f"{action}失败")
            
            app_logger.info(f"{action}成功: {comic_id}")
            return ServiceResult.ok({
                "comic_id": comic_id,
                "is_favorited": not is_favorited
            }, f"{action}成功")
        except Exception as e:
            error_logger.error(f"收藏操作失败: {e}")
            return ServiceResult.error("收藏操作失败")
    
    def is_favorited(self, comic_id: str, source: str = "local") -> bool:
        try:
            repo = self._comic_repo if source == "local" else self._rec_repo
            comic = repo.get_by_id(comic_id)
            if comic:
                return self.DEFAULT_COMIC_LIST_ID in comic.list_ids
            return False
        except:
            return False
    
    def ensure_default_list(self) -> bool:
        return self._list_repo.ensure_default_list()
    
    def bind_videos(self, list_id: str, video_ids: ListType[str], source: str = "local") -> ServiceResult:
        try:
            app_logger.info(f"[bind_videos] 开始绑定: list_id={list_id}, video_ids={video_ids}, source={source}")
            
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                app_logger.error(f"[bind_videos] 清单不存在: {list_id}")
                return ServiceResult.error("清单不存在")
            
            updated_count = 0
            repo = self._video_repo if source == "local" else self._video_rec_repo
            
            for video_id in video_ids:
                video = repo.get_by_id(video_id)
                if video:
                    app_logger.info(f"[bind_videos] 找到视频: {video_id}, 当前list_ids={video.list_ids}")
                    video.add_to_list(list_id)
                    app_logger.info(f"[bind_videos] 添加后list_ids={video.list_ids}")
                    save_result = repo.save(video)
                    app_logger.info(f"[bind_videos] 保存结果: {save_result}")
                    if save_result:
                        updated_count += 1
                else:
                    app_logger.warning(f"[bind_videos] 视频不存在: {video_id}")
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量加入清单成功: 清单 {list_id}, {updated_count}个视频")
            return ServiceResult.ok({
                "list_id": list_id,
                "updated_count": updated_count
            }, f"成功将{updated_count}个视频加入清单")
        except Exception as e:
            error_logger.error(f"批量加入清单失败: {e}")
            return ServiceResult.error("批量加入清单失败")
    
    def remove_videos(self, list_id: str, video_ids: ListType[str], source: str = "local") -> ServiceResult:
        try:
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            updated_count = 0
            repo = self._video_repo if source == "local" else self._video_rec_repo
            
            for video_id in video_ids:
                video = repo.get_by_id(video_id)
                if video:
                    video.remove_from_list(list_id)
                    if repo.save(video):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量移出清单成功: 清单 {list_id}, {updated_count}个视频")
            return ServiceResult.ok({
                "list_id": list_id,
                "updated_count": updated_count
            }, f"成功将{updated_count}个视频移出清单")
        except Exception as e:
            error_logger.error(f"批量移出清单失败: {e}")
            return ServiceResult.error("批量移出清单失败")
    
    def toggle_favorite_video(self, video_id: str, source: str = "local") -> ServiceResult:
        try:
            self._list_repo.ensure_default_list()
            
            repo = self._video_repo if source == "local" else self._video_rec_repo
            video = repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")
            
            is_favorited = self.DEFAULT_VIDEO_LIST_ID in video.list_ids
            
            if is_favorited:
                video.remove_from_list(self.DEFAULT_VIDEO_LIST_ID)
                action = "取消收藏"
            else:
                video.add_to_list(self.DEFAULT_VIDEO_LIST_ID)
                action = "收藏"
            
            if not repo.save(video):
                return ServiceResult.error(f"{action}失败")
            
            app_logger.info(f"{action}成功: {video_id}")
            return ServiceResult.ok({
                "video_id": video_id,
                "is_favorited": not is_favorited
            }, f"{action}成功")
        except Exception as e:
            error_logger.error(f"收藏操作失败: {e}")
            return ServiceResult.error("收藏操作失败")
    
    def is_favorited_video(self, video_id: str, source: str = "local") -> bool:
        try:
            repo = self._video_repo if source == "local" else self._video_rec_repo
            video = repo.get_by_id(video_id)
            if video:
                return self.DEFAULT_VIDEO_LIST_ID in video.list_ids
            return False
        except:
            return False
