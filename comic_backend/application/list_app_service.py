import os
from typing import List as ListType, Optional
from domain.list import List, ListRepository
from domain.comic import ComicRepository
from domain.video import VideoRepository, Video
from domain.recommendation import RecommendationRepository
from domain.video_recommendation import VideoRecommendationRepository, VideoRecommendation
from infrastructure.persistence.repositories import ListJsonRepository, ComicJsonRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id, generate_uuid
from core.enums import ContentType
from core.platform import Platform
from third_party.platform_service import get_platform_service


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
                # 自动修复旧数据：如果清单描述包含"远程清单ID"但缺少 platform 和 platform_list_id
                if (not lst.platform or not lst.platform_list_id) and lst.desc and "远程清单ID" in lst.desc:
                    import re
                    match = re.search(r'远程清单ID[：:]\s*(\S+)', lst.desc)
                    if match:
                        lst.platform = "JAVDB"
                        lst.platform_list_id = match.group(1)
                        lst.import_source = "local"
                        self._list_repo.save(lst)
                        app_logger.info(f"自动修复旧清单数据: {lst.id}, {lst.platform}, {lst.platform_list_id}")
                
                comic_count = self._list_repo.get_comic_count(lst.id)
                video_count = self._list_repo.get_video_count(lst.id)
                list_data = {
                    "id": lst.id,
                    "name": lst.name,
                    "desc": lst.desc,
                    "content_type": lst.content_type.value,
                    "is_default": lst.is_default,
                    "comic_count": comic_count,
                    "video_count": video_count,
                    "create_time": lst.create_time,
                    "platform": lst.platform,
                    "platform_list_id": lst.platform_list_id,
                    "import_source": lst.import_source,
                    "last_sync_time": lst.last_sync_time
                }
                app_logger.info(f"清单数据: {list_data}")
                result.append(list_data)
            
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
                "platform": lst.platform,
                "platform_list_id": lst.platform_list_id,
                "import_source": lst.import_source,
                "last_sync_time": lst.last_sync_time,
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
    
    def get_platform_user_lists(self, platform_str: str) -> ServiceResult:
        """获取平台用户清单列表
        
        Args:
            platform_str: 平台字符串
            
        Returns:
            包含清单列表的结果
        """
        try:
            app_logger.info(f"获取平台用户清单列表: {platform_str}")
            
            platform = Platform(platform_str)
            
            if platform in [Platform.JM, Platform.PK]:
                result = {
                    "lists": [{
                        "list_id": "favorites",
                        "list_name": "我的收藏",
                        "list_desc": "平台收藏夹中的所有漫画",
                        "total": 0
                    }]
                }
                app_logger.info(f"获取平台用户清单列表成功: {platform_str}, 返回虚拟收藏夹清单")
                return ServiceResult.ok(result)
            
            platform_service = get_platform_service()
            result = platform_service.get_user_lists(platform)
            
            app_logger.info(f"获取平台用户清单列表成功: {len(result.get('lists', []))} 个清单")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取平台用户清单列表失败: {e}")
            return ServiceResult.error(f"获取平台用户清单列表失败: {e}")
    
    def get_platform_list_detail(self, platform_str: str, list_id: str) -> ServiceResult:
        """获取平台清单详情
        
        Args:
            platform_str: 平台字符串
            list_id: 清单ID
            
        Returns:
            包含清单详情的结果
        """
        try:
            app_logger.info(f"获取平台清单详情: {platform_str}, {list_id}")
            
            platform = Platform(platform_str)
            platform_service = get_platform_service()
            
            if platform in [Platform.JM, Platform.PK] and list_id == "favorites":
                favorites_result = platform_service.get_favorites(platform)
                albums = favorites_result.get('albums', [])
                
                works = []
                for album in albums:
                    album_id = album.get('album_id', '') or album.get('comic_id', '')
                    works.append({
                        'album_id': album_id,
                        'comic_id': album_id,
                        'title': album.get('title', ''),
                        'author': album.get('author', ''),
                        'cover_url': album.get('cover_url', ''),
                        'tags': album.get('tags', [])
                    })
                
                result = {
                    "list_id": "favorites",
                    "list_name": "我的收藏",
                    "list_desc": "平台收藏夹中的所有漫画",
                    "total": len(works),
                    "works": works
                }
                app_logger.info(f"获取平台收藏夹详情成功: {platform_str}, {len(works)} 个漫画")
                return ServiceResult.ok(result)
            
            result = platform_service.get_list_detail(platform, list_id)
            
            app_logger.info(f"获取平台清单详情成功: {list_id}, {len(result.get('works', []))} 个作品")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取平台清单详情失败: {e}")
            return ServiceResult.error(f"获取平台清单详情失败: {e}")
    
    def import_platform_list(
        self, 
        platform_str: str, 
        platform_list_id: str, 
        platform_list_name: str, 
        source: str = "local"
    ) -> ServiceResult:
        """导入平台清单到本地清单
        
        Args:
            platform_str: 平台字符串
            platform_list_id: 平台清单ID
            platform_list_name: 平台清单名称
            source: 导入来源 - "local" 本地库, "preview" 预览库
            
        Returns:
            导入结果
        """
        try:
            app_logger.info(f"开始导入平台清单: {platform_str}, {platform_list_id} ({platform_list_name}), source={source}")
            
            platform = Platform(platform_str)
            platform_service = get_platform_service()
            
            from core.enums import ContentType
            content_type = ContentType.VIDEO if platform == Platform.JAVDB else ContentType.COMIC
            
            if platform in [Platform.JM, Platform.PK] and platform_list_id == "favorites":
                self._list_repo.ensure_default_list()
                target_list_id = self.DEFAULT_COMIC_LIST_ID
                
                favorites_result = platform_service.get_favorites(platform)
                works = favorites_result.get('albums', [])
                
                if not works:
                    return ServiceResult.error("收藏夹中没有内容")
                
                converted_works = []
                for album in works:
                    album_id = album.get('album_id', '') or album.get('comic_id', '')
                    converted_works.append({
                        'album_id': album_id,
                        'comic_id': album_id,
                        'title': album.get('title', ''),
                        'author': album.get('author', ''),
                        'cover_url': album.get('cover_url', ''),
                        'tags': album.get('tags', [])
                    })
                
                result = self._import_comics(converted_works, target_list_id, source, platform)
                
                if result.success:
                    lst = self._list_repo.get_by_id(target_list_id)
                    if lst:
                        lst.platform = platform_str
                        lst.import_source = source
                        lst.last_sync_time = get_current_time()
                        self._list_repo.save(lst)
                    result.data['list_id'] = target_list_id
                
                app_logger.info(f"导入平台收藏夹完成: {result.data}")
                return result
            
            list_name = f"远程跟踪：{platform_list_name}"
            list_desc = f"远程清单ID：{platform_list_id}"
            
            new_list = self._list_repo.create(
                name=list_name,
                desc=list_desc,
                content_type=content_type
            )
            
            if not new_list:
                return ServiceResult.error("创建本地清单失败")
            
            new_list.platform = platform_str
            new_list.platform_list_id = platform_list_id
            new_list.import_source = source
            new_list.last_sync_time = get_current_time()
            self._list_repo.save(new_list)
            
            app_logger.info(f"已创建本地清单: {new_list.id} - {new_list.name}")
            
            list_detail = platform_service.get_list_detail(platform, platform_list_id)
            works = list_detail.get('works', [])
            
            if not works:
                return ServiceResult.error("清单中没有内容")
            
            if platform == Platform.JAVDB:
                result = self._import_javdb_videos(works, new_list.id, source)
            else:
                result = self._import_comics(works, new_list.id, source, platform)
            
            app_logger.info(f"导入平台清单完成: {result.data}")
            
            if result.success:
                result.data['list_id'] = new_list.id
            
            return result
        except Exception as e:
            error_logger.error(f"导入平台清单失败: {e}")
            return ServiceResult.error(f"导入平台清单失败: {e}")
    
    def sync_platform_list(self, list_id: str) -> ServiceResult:
        """同步平台清单
        
        Args:
            list_id: 本地清单ID
            
        Returns:
            同步结果
        """
        try:
            app_logger.info(f"开始同步清单: {list_id}")
            
            lst = self._list_repo.get_by_id(list_id)
            if not lst:
                return ServiceResult.error("清单不存在")
            
            # 如果没有 platform 和 platform_list_id，从描述中解析
            if not lst.platform or not lst.platform_list_id:
                import re
                match = re.search(r'远程清单ID[：:]\s*(\S+)', lst.desc)
                if match:
                    lst.platform = "JAVDB"
                    lst.platform_list_id = match.group(1)
                    lst.import_source = "local"
                    self._list_repo.save(lst)
                    app_logger.info(f"从描述中解析出清单信息: {lst.platform}, {lst.platform_list_id}")
                else:
                    return ServiceResult.error("该清单不是网络清单，无法同步")
            
            platform = Platform(lst.platform)
            platform_service = get_platform_service()
            source = lst.import_source or "local"
            
            app_logger.info(f"从平台 {lst.platform} 同步清单 {lst.platform_list_id}")
            
            # 获取平台最新的清单内容
            list_detail = platform_service.get_list_detail(platform, lst.platform_list_id)
            works = list_detail.get('works', [])
            
            if not works:
                return ServiceResult.error("清单中没有内容")
            
            # 获取当前清单已有的视频
            videos = self._video_repo.get_all()
            existing_video_codes = set()
            for video in videos:
                if list_id in video.list_ids and not video.is_deleted:
                    existing_video_codes.add(video.code)
            
            app_logger.info(f"当前清单已有 {len(existing_video_codes)} 个视频")
            
            # 筛选出新增的视频
            new_works = []
            for work in works:
                code = work.get('code', '')
                if code and code not in existing_video_codes:
                    new_works.append(work)
                    app_logger.info(f"发现新视频: {code}")
            
            app_logger.info(f"需要导入 {len(new_works)} 个新视频")
            
            if not new_works:
                # 更新最后同步时间
                lst.last_sync_time = get_current_time()
                self._list_repo.save(lst)
                
                return ServiceResult.ok({
                    'imported_count': 0,
                    'skipped_count': 0,
                    'total_count': len(works),
                    'list_id': list_id
                }, "清单已是最新，无需同步")
            
            # 导入新增的视频
            if platform == Platform.JAVDB:
                result = self._import_javdb_videos(new_works, list_id, source)
            else:
                result = self._import_comics(new_works, list_id, source, platform)
            
            # 更新最后同步时间
            if result.success:
                lst.last_sync_time = get_current_time()
                self._list_repo.save(lst)
                result.data['list_id'] = list_id
            
            app_logger.info(f"同步清单完成: {result.data}")
            return result
        except Exception as e:
            error_logger.error(f"同步清单失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error(f"同步清单失败: {e}")
    
    def _import_javdb_videos(
        self, 
        works: ListType[dict], 
        target_list_id: str, 
        source: str = "local"
    ) -> ServiceResult:
        """导入JAVDB视频
        
        Args:
            works: JAVDB视频列表
            target_list_id: 目标清单ID
            source: 导入来源
            
        Returns:
            导入结果
        """
        try:
            from core.platform import add_platform_prefix
            from application.tag_app_service import TagAppService
            from domain.tag.entity import ContentType
            from core.constants import JAV_PICTURES_DIR, JAV_COVER_DIR
            from application.video_app_service import VideoAppService
            
            repo = self._video_repo if source == "local" else self._video_rec_repo
            entity_class = Video if source == "local" else VideoRecommendation
            video_service = VideoAppService()
            
            tag_service = TagAppService()
            existing_tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
            
            tag_name_to_id = {}
            for tag in existing_tags:
                tag_name_to_id[tag["name"]] = tag["id"]
            
            imported_count = 0
            skipped_count = 0
            
            # 获取平台服务来获取视频详情
            from third_party.platform_service import get_platform_service
            platform_service = get_platform_service()
            
            for work in works:
                try:
                    video_id = work.get('video_id', '')
                    if not video_id:
                        skipped_count += 1
                        continue
                    
                    prefixed_id = add_platform_prefix(Platform.JAVDB, video_id)
                    
                    existing_video = repo.get_by_id(prefixed_id)
                    if existing_video:
                        if target_list_id not in existing_video.list_ids:
                            existing_video.add_to_list(target_list_id)
                            repo.save(existing_video)
                            imported_count += 1
                        else:
                            skipped_count += 1
                        continue
                    
                    # 获取完整的视频详情
                    app_logger.info(f"获取视频详情: {video_id}")
                    detail = platform_service.get_album_by_id(Platform.JAVDB, video_id)
                    
                    if not detail:
                        app_logger.warning(f"无法获取视频详情: {video_id}")
                        skipped_count += 1
                        continue
                    
                    # 从详情中提取第一个视频（因为 get_album_by_id 返回的是 videos 数组）
                    videos = detail.get('videos', [])
                    if not videos:
                        app_logger.warning(f"视频详情中没有视频数据: {video_id}")
                        skipped_count += 1
                        continue
                    
                    video_detail = videos[0]
                    
                    # 处理标签
                    video_tag_ids = []
                    for tag_name in video_detail.get("tags", []):
                        if tag_name not in tag_name_to_id:
                            result = tag_service.create_tag(tag_name, ContentType.VIDEO)
                            if result.success:
                                tag_name_to_id[tag_name] = result.data["id"]
                                app_logger.info(f"创建新标签: {result.data['id']} - {tag_name}")
                        if tag_name in tag_name_to_id:
                            video_tag_ids.append(tag_name_to_id[tag_name])
                    
                    # 构建视频数据
                    video_data = {
                        'id': prefixed_id,
                        'title': video_detail.get('title', ''),
                        'code': video_detail.get('code', ''),
                        'date': video_detail.get('date', ''),
                        'series': video_detail.get('series', ''),
                        'creator': video_detail.get('actors', [''])[0] if video_detail.get('actors') else '',
                        'actors': video_detail.get('actors', []),
                        'magnets': video_detail.get('magnets', []),
                        'thumbnail_images': video_detail.get('thumbnail_images', []),
                        'preview_video': video_detail.get('preview_video', ''),
                        'tag_ids': video_tag_ids,
                        'list_ids': [target_list_id],
                        'create_time': get_current_time(),
                        'last_access_time': get_current_time()
                    }
                    
                    # 处理评分
                    rating = work.get('rating', '')
                    score = 8.0
                    if rating:
                        try:
                            rating_num = float(rating.replace('分', ''))
                            score = min(max(rating_num, 1.0), 10.0)
                        except:
                            pass
                    video_data['score'] = score
                    
                    # 对于本地库，使用 VideoAppService 导入
                    if source == "local":
                        result = video_service.import_video(video_data)
                        if result.success:
                            imported_count += 1
                            # 下载封面
                            cover_url = video_detail.get('cover_url', '')
                            app_logger.info(f"视频 {prefixed_id} 的封面 URL: {cover_url}")
                            if cover_url:
                                app_logger.info(f"开始下载封面: {prefixed_id}")
                                video_service.download_cover_async(prefixed_id, cover_url)
                                video_service.download_high_quality_thumbnail_async(
                                    prefixed_id, cover_url, JAV_PICTURES_DIR, JAV_COVER_DIR
                                )
                            else:
                                app_logger.warning(f"视频 {prefixed_id} 没有封面 URL")
                        else:
                            skipped_count += 1
                    else:
                        # 预览库直接保存
                        from infrastructure.persistence.json_storage import JsonStorage
                        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
                        
                        video_data['cover_path'] = video_detail.get('cover_url', '')
                        
                        db_file = VIDEO_RECOMMENDATION_JSON_FILE
                        storage = JsonStorage(db_file)
                        db_data = storage.read()
                        videos_key = 'video_recommendations'
                        
                        if videos_key not in db_data:
                            db_data[videos_key] = []
                        db_data[videos_key].append(video_data)
                        
                        if storage.write(db_data):
                            imported_count += 1
                            # 下载封面
                            cover_url = video_detail.get('cover_url', '')
                            app_logger.info(f"推荐视频 {prefixed_id} 的封面 URL: {cover_url}")
                            if cover_url:
                                app_logger.info(f"开始下载推荐封面: {prefixed_id}")
                                video_service.download_cover_async_for_recommendation(prefixed_id, cover_url, JAV_COVER_DIR)
                            else:
                                app_logger.warning(f"推荐视频 {prefixed_id} 没有封面 URL")
                        else:
                            skipped_count += 1
                        
                except Exception as e:
                    app_logger.warning(f"导入单个视频失败: {work.get('video_id', '')}, {e}")
                    import traceback
                    app_logger.warning(traceback.format_exc())
                    skipped_count += 1
            
            return ServiceResult.ok({
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'total_count': len(works)
            }, f"成功导入 {imported_count} 个视频，跳过 {skipped_count} 个")
            
        except Exception as e:
            error_logger.error(f"导入JAVDB视频失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error(f"导入JAVDB视频失败: {e}")
    
    def _import_comics(
        self, 
        works: ListType[dict], 
        target_list_id: str, 
        source: str = "local",
        platform: Platform = None
    ) -> ServiceResult:
        """导入漫画
        
        Args:
            works: 漫画列表
            target_list_id: 目标清单ID
            source: 导入来源 - "local" 本地库, "preview" 预览库
            platform: 平台
            
        Returns:
            导入结果
        """
        try:
            from core.platform import add_platform_prefix
            from application.tag_app_service import TagAppService
            from domain.tag.entity import ContentType
            from domain.comic import Comic
            from domain.recommendation import Recommendation
            from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR, JM_COVER_DIR, PK_COVER_DIR
            
            repo = self._comic_repo if source == "local" else self._rec_repo
            entity_class = Comic if source == "local" else Recommendation
            
            tag_service = TagAppService()
            existing_tags = tag_service.get_tag_list(ContentType.COMIC).data or []
            
            tag_name_to_id = {}
            for tag in existing_tags:
                tag_name_to_id[tag["name"]] = tag["id"]
            
            imported_count = 0
            skipped_count = 0
            
            platform_service = get_platform_service()
            
            download_dir = JM_PICTURES_DIR if platform == Platform.JM else PK_PICTURES_DIR
            cover_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
            
            for work in works:
                try:
                    album_id = work.get('album_id', '')
                    if not album_id:
                        album_id = work.get('comic_id', '')
                    
                    if not album_id:
                        skipped_count += 1
                        continue
                    
                    prefixed_id = add_platform_prefix(platform, str(album_id))
                    
                    existing_comic = repo.get_by_id(prefixed_id)
                    if existing_comic:
                        if target_list_id not in existing_comic.list_ids:
                            existing_comic.add_to_list(target_list_id)
                            repo.save(existing_comic)
                            imported_count += 1
                        else:
                            skipped_count += 1
                        continue
                    
                    app_logger.info(f"获取漫画详情: {album_id}")
                    detail_result = platform_service.get_album_by_id(platform, str(album_id))
                    
                    if not detail_result:
                        app_logger.warning(f"无法获取漫画详情: {album_id}")
                        skipped_count += 1
                        continue
                    
                    albums = detail_result.get('albums', [])
                    if not albums:
                        app_logger.warning(f"漫画详情中没有数据: {album_id}")
                        skipped_count += 1
                        continue
                    
                    comic_detail = albums[0]
                    
                    video_tag_ids = []
                    for tag_name in comic_detail.get("tags", []):
                        if tag_name not in tag_name_to_id:
                            result = tag_service.create_tag(tag_name, ContentType.COMIC)
                            if result.success:
                                tag_name_to_id[tag_name] = result.data["id"]
                                app_logger.info(f"创建新标签: {result.data['id']} - {tag_name}")
                        if tag_name in tag_name_to_id:
                            video_tag_ids.append(tag_name_to_id[tag_name])
                    
                    platform_prefix = "JM" if platform == Platform.JM else "PK"
                    cover_path = f"/static/cover/{platform_prefix}/{album_id}.jpg"
                    
                    comic_data = {
                        'id': prefixed_id,
                        'title': comic_detail.get('title', ''),
                        'title_jp': comic_detail.get('title_jp', ''),
                        'author': comic_detail.get('author', ''),
                        'desc': '',
                        'cover_path': cover_path,
                        'total_page': comic_detail.get('pages', 0),
                        'current_page': 1,
                        'tag_ids': video_tag_ids,
                        'list_ids': [target_list_id],
                        'create_time': get_current_time(),
                        'last_access_time': get_current_time()
                    }
                    
                    if source == "local":
                        comic = Comic.from_dict(comic_data)
                        if repo.save(comic):
                            imported_count += 1
                            
                            cover_url = comic_detail.get('cover_url', '')
                            if cover_url:
                                app_logger.info(f"开始下载封面: {prefixed_id}")
                                try:
                                    save_path = os.path.join(cover_dir, f"{album_id}.jpg")
                                    os.makedirs(cover_dir, exist_ok=True)
                                    platform_service.download_cover(platform, str(album_id), save_path, show_progress=False)
                                except Exception as e:
                                    app_logger.warning(f"下载封面失败: {prefixed_id}, {e}")
                        else:
                            skipped_count += 1
                    else:
                        from infrastructure.persistence.json_storage import JsonStorage
                        from core.constants import RECOMMENDATION_JSON_FILE
                        from core.utils import get_preview_pages
                        
                        comic_data['cover_path'] = comic_detail.get('cover_url', '') or cover_path
                        
                        # 获取预览图片 URL
                        try:
                            total_page = comic_detail.get('pages', 0)
                            preview_pages = get_preview_pages(total_page)
                            
                            preview_urls = platform_service.get_preview_image_urls(
                                platform,
                                str(album_id),
                                preview_pages
                            )
                            
                            comic_data['preview_image_urls'] = preview_urls
                            comic_data['preview_pages'] = preview_pages
                            
                            app_logger.info(f"获取推荐页预览图片成功: {prefixed_id}, 共 {len(preview_urls)} 张")
                        except Exception as e:
                            from infrastructure.logger import error_logger
                            error_logger.error(f"获取推荐页预览图片失败 {prefixed_id}: {e}")
                            comic_data['preview_image_urls'] = []
                            comic_data['preview_pages'] = []
                        
                        db_file = RECOMMENDATION_JSON_FILE
                        storage = JsonStorage(db_file)
                        db_data = storage.read()
                        comics_key = 'recommendations'
                        
                        if comics_key not in db_data:
                            db_data[comics_key] = []
                        db_data[comics_key].append(comic_data)
                        
                        if storage.write(db_data):
                            imported_count += 1
                            
                            cover_url = comic_detail.get('cover_url', '')
                            if cover_url:
                                app_logger.info(f"开始下载推荐封面: {prefixed_id}")
                                try:
                                    save_path = os.path.join(cover_dir, f"{album_id}.jpg")
                                    os.makedirs(cover_dir, exist_ok=True)
                                    platform_service.download_cover(platform, str(album_id), save_path, show_progress=False)
                                except Exception as e:
                                    app_logger.warning(f"下载推荐封面失败: {prefixed_id}, {e}")
                        else:
                            skipped_count += 1
                        
                except Exception as e:
                    app_logger.warning(f"导入单个漫画失败: {work.get('album_id', work.get('comic_id', ''))}, {e}")
                    import traceback
                    app_logger.warning(traceback.format_exc())
                    skipped_count += 1
            
            return ServiceResult.ok({
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'total_count': len(works)
            }, f"成功导入 {imported_count} 个漫画，跳过 {skipped_count} 个")
            
        except Exception as e:
            error_logger.error(f"导入漫画失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error(f"导入漫画失败: {e}")
    
    def import_platform_favorites(self, platform_str: str, source: str = "local") -> ServiceResult:
        """导入平台收藏夹到本地默认收藏清单
        
        Args:
            platform_str: 平台字符串 (JM 或 PK)
            source: 导入来源 - "local" 本地库, "preview" 预览库
            
        Returns:
            导入结果
        """
        try:
            app_logger.info(f"开始导入平台收藏夹: {platform_str}, source={source}")
            
            platform = Platform(platform_str)
            platform_service = get_platform_service()
            
            self._list_repo.ensure_default_list()
            
            target_list_id = self.DEFAULT_COMIC_LIST_ID
            
            app_logger.info(f"从平台 {platform_str} 获取收藏夹")
            
            favorites_result = platform_service.get_favorites(platform)
            
            if not favorites_result:
                return ServiceResult.error("获取收藏夹失败")
            
            works = favorites_result.get('albums', [])
            
            if not works:
                return ServiceResult.error("收藏夹中没有内容")
            
            app_logger.info(f"获取到 {len(works)} 个收藏漫画")
            
            result = self._import_comics(works, target_list_id, source, platform)
            
            if result.success:
                lst = self._list_repo.get_by_id(target_list_id)
                if lst:
                    lst.platform = platform_str
                    lst.import_source = source
                    lst.last_sync_time = get_current_time()
                    self._list_repo.save(lst)
            
            app_logger.info(f"导入平台收藏夹完成: {result.data}")
            return result
            
        except Exception as e:
            error_logger.error(f"导入平台收藏夹失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error(f"导入平台收藏夹失败: {e}")
    
    def sync_platform_favorites(self, platform_str: str, source: str = "local") -> ServiceResult:
        """同步平台收藏夹
        
        只导入新增的漫画，不重复导入已存在的漫画
        
        Args:
            platform_str: 平台字符串 (JM 或 PK)
            source: 导入来源 - "local" 本地库, "preview" 预览库
            
        Returns:
            同步结果
        """
        try:
            app_logger.info(f"开始同步平台收藏夹: {platform_str}, source={source}")
            
            platform = Platform(platform_str)
            platform_service = get_platform_service()
            
            self._list_repo.ensure_default_list()
            
            target_list_id = self.DEFAULT_COMIC_LIST_ID
            
            app_logger.info(f"从平台 {platform_str} 获取收藏夹")
            
            favorites_result = platform_service.get_favorites(platform)
            
            if not favorites_result:
                return ServiceResult.error("获取收藏夹失败")
            
            works = favorites_result.get('albums', [])
            
            if not works:
                return ServiceResult.ok({
                    'imported_count': 0,
                    'skipped_count': 0,
                    'total_count': 0
                }, "收藏夹中没有内容")
            
            app_logger.info(f"获取到 {len(works)} 个收藏漫画")
            
            from core.platform import add_platform_prefix
            repo = self._comic_repo if source == "local" else self._rec_repo
            
            existing_ids = set()
            comics = repo.get_all()
            for comic in comics:
                if target_list_id in comic.list_ids and not comic.is_deleted:
                    existing_ids.add(comic.id)
            
            app_logger.info(f"当前收藏清单已有 {len(existing_ids)} 个漫画")
            
            new_works = []
            for work in works:
                album_id = work.get('album_id', '') or work.get('comic_id', '')
                if album_id:
                    prefixed_id = add_platform_prefix(platform, str(album_id))
                    if prefixed_id not in existing_ids:
                        new_works.append(work)
                        app_logger.info(f"发现新漫画: {prefixed_id}")
            
            app_logger.info(f"需要导入 {len(new_works)} 个新漫画")
            
            if not new_works:
                lst = self._list_repo.get_by_id(target_list_id)
                if lst:
                    lst.last_sync_time = get_current_time()
                    self._list_repo.save(lst)
                
                return ServiceResult.ok({
                    'imported_count': 0,
                    'skipped_count': 0,
                    'total_count': len(works)
                }, "收藏夹已是最新，无需同步")
            
            result = self._import_comics(new_works, target_list_id, source, platform)
            
            if result.success:
                lst = self._list_repo.get_by_id(target_list_id)
                if lst:
                    lst.last_sync_time = get_current_time()
                    self._list_repo.save(lst)
            
            app_logger.info(f"同步平台收藏夹完成: {result.data}")
            return result
            
        except Exception as e:
            error_logger.error(f"同步平台收藏夹失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error(f"同步平台收藏夹失败: {e}")
