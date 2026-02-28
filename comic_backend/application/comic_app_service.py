from typing import List, Optional
from domain.comic import Comic, ComicRepository
from domain.tag import TagRepository
from infrastructure.persistence.repositories import ComicJsonRepository, TagJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, get_preview_pages

FAVORITES_LIST_ID = "list_favorites"


class ComicAppService:
    def __init__(
        self,
        comic_repo: ComicRepository = None,
        tag_repo: TagRepository = None
    ):
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
    
    def get_comic_list(
        self,
        sort_type: str = None,
        min_score: float = None,
        max_score: float = None
    ) -> ServiceResult:
        try:
            comics = self._comic_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            if min_score is not None:
                comics = [c for c in comics if c.score is not None and c.score >= min_score]
            if max_score is not None:
                comics = [c for c in comics if c.score is not None and c.score <= max_score]
            
            if sort_type == "create_time":
                comics = sorted(comics, key=lambda c: c.create_time or "", reverse=True)
            elif sort_type == "score":
                comics = sorted(comics, key=lambda c: c.score or 0, reverse=True)
            elif sort_type == "read_time":
                comics = sorted(comics, key=lambda c: c.last_read_time or "", reverse=True)
            
            comic_list = []
            for c in comics:
                is_favorited = FAVORITES_LIST_ID in c.list_ids
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "desc": c.desc,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "current_page": c.current_page,
                    "score": c.score,
                    "tag_ids": c.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "last_read_time": c.last_read_time,
                    "create_time": c.create_time,
                    "is_favorited": is_favorited
                }
                comic_list.append(comic_info)
            
            app_logger.info(f"获取漫画列表成功，共 {len(comic_list)} 个漫画")
            return ServiceResult.ok(comic_list)
        except Exception as e:
            error_logger.error(f"获取漫画列表失败: {e}")
            return ServiceResult.error("获取漫画列表失败")
    
    def get_comic_detail(self, comic_id: str) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            preview_pages = get_preview_pages(comic.total_page)
            
            is_favorited = FAVORITES_LIST_ID in comic.list_ids
            
            detail = {
                "id": comic.id,
                "title": comic.title,
                "title_jp": comic.title_jp,
                "author": comic.author,
                "desc": comic.desc,
                "cover_path": comic.cover_path,
                "total_page": comic.total_page,
                "current_page": comic.current_page,
                "score": comic.score,
                "tag_ids": comic.tag_ids,
                "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in comic.tag_ids],
                "preview_images": [f"/api/v1/comic/image?comic_id={comic_id}&page_num={p}" for p in preview_pages],
                "preview_pages": preview_pages,
                "last_read_time": comic.last_read_time,
                "create_time": comic.create_time,
                "list_ids": comic.list_ids,
                "is_favorited": is_favorited
            }
            
            app_logger.info(f"获取漫画详情成功: {comic_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取漫画详情失败: {e}")
            return ServiceResult.error("获取漫画详情失败")
    
    def update_score(self, comic_id: str, score: float) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if not comic.update_score(score):
                return ServiceResult.error("评分验证失败")
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("保存评分失败")
            
            app_logger.info(f"更新漫画评分成功: {comic_id}, 评分: {score}")
            return ServiceResult.ok({"comic_id": comic_id, "score": score}, "评分保存成功")
        except Exception as e:
            error_logger.error(f"更新漫画评分失败: {e}")
            return ServiceResult.error("更新评分失败")
    
    def update_progress(self, comic_id: str, current_page: int) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if not comic.update_progress(current_page):
                return ServiceResult.error("页码超出范围")
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("保存进度失败")
            
            app_logger.info(f"保存阅读进度成功: {comic_id}, 页码: {current_page}")
            return ServiceResult.ok({"comic_id": comic_id, "current_page": current_page}, "进度保存成功")
        except Exception as e:
            error_logger.error(f"保存阅读进度失败: {e}")
            return ServiceResult.error("保存进度失败")
    
    def bind_tags(self, comic_id: str, tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.bind_tags(tag_ids)
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("绑定标签失败")
            
            app_logger.info(f"绑定漫画标签成功: {comic_id}, 标签: {tag_ids}")
            return ServiceResult.ok({"comic_id": comic_id, "tag_ids": tag_ids}, "标签绑定成功")
        except Exception as e:
            error_logger.error(f"绑定漫画标签失败: {e}")
            return ServiceResult.error("绑定标签失败")
    
    def update_meta(self, comic_id: str, meta: dict) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.update_meta(meta)
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("更新元数据失败")
            
            app_logger.info(f"更新漫画元数据成功: {comic_id}")
            return ServiceResult.ok(comic.to_dict(), "更新成功")
        except Exception as e:
            error_logger.error(f"更新漫画元数据失败: {e}")
            return ServiceResult.error("更新元数据失败")
    
    def search(self, keyword: str) -> ServiceResult:
        try:
            comics = self._comic_repo.search(keyword)
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
            
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"搜索失败: {e}")
            return ServiceResult.error("搜索失败")
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> ServiceResult:
        try:
            comics = self._comic_repo.filter_by_tags(include_tags, exclude_tags)
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
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def batch_add_tags(self, comic_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.add_tags(tag_ids)
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为{updated_count}个漫画添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, comic_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.remove_tags(tag_ids)
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功从{updated_count}个漫画移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
