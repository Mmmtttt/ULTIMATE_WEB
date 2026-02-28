from typing import List
from domain.tag import Tag, TagRepository
from domain.comic import ComicRepository
from infrastructure.persistence.repositories import TagJsonRepository, ComicJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id


class TagAppService:
    def __init__(
        self,
        tag_repo: TagRepository = None,
        comic_repo: ComicRepository = None
    ):
        self._tag_repo = tag_repo or TagJsonRepository()
        self._comic_repo = comic_repo or ComicJsonRepository()
    
    def get_tag_list(self) -> ServiceResult:
        try:
            tags = self._tag_repo.get_all()
            comics = self._comic_repo.get_all()
            
            tag_comic_count = {}
            for comic in comics:
                for tag_id in comic.tag_ids:
                    tag_comic_count[tag_id] = tag_comic_count.get(tag_id, 0) + 1
            
            tag_list = []
            for t in tags:
                tag_info = {
                    "id": t.id,
                    "name": t.name,
                    "comic_count": tag_comic_count.get(t.id, 0)
                }
                tag_list.append(tag_info)
            
            app_logger.info(f"获取标签列表成功，共 {len(tag_list)} 个标签")
            return ServiceResult.ok(tag_list)
        except Exception as e:
            error_logger.error(f"获取标签列表失败: {e}")
            return ServiceResult.error("获取标签列表失败")
    
    def create_tag(self, name: str) -> ServiceResult:
        try:
            if self._tag_repo.exists_by_name(name):
                return ServiceResult.error("标签名称已存在")
            
            tag = Tag(
                id=generate_id("tag"),
                name=name,
                create_time=get_current_time()
            )
            
            if not self._tag_repo.save(tag):
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
            elif self._tag_repo.exists_by_name(name):
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
            
            comics = self._comic_repo.filter_by_tags([tag_id], [])
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            results = []
            for c in comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids]
                }
                results.append(comic_info)
            
            app_logger.info(f"获取标签下漫画成功: {tag_id}, 数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"获取标签下漫画失败: {e}")
            return ServiceResult.error("获取标签下漫画失败")
