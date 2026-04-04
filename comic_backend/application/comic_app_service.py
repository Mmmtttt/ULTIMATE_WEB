from typing import Any, Dict, List, Optional, Tuple
import base64
import json
import os
import re
from domain.comic import Comic, ComicRepository
from domain.tag import TagRepository
from infrastructure.persistence.repositories import ComicJsonRepository, TagJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, get_preview_pages, normalize_total_page
from core.enums import ContentType

FAVORITES_LIST_ID = "list_favorites_comic"


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
            app_logger.info(f"[get_comic_list] sort_type={sort_type}, min_score={min_score}, max_score={max_score}")
            comics = self._comic_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 过滤掉已删除的漫画
            comics = [c for c in comics if not c.is_deleted]
            
            if min_score is not None:
                comics = [c for c in comics if c.score is not None and c.score >= min_score]
            if max_score is not None:
                comics = [c for c in comics if c.score is not None and c.score <= max_score]
            
            app_logger.info(f"[get_comic_list] 排序前漫画数量: {len(comics)}")
            if sort_type:
                app_logger.info(f"[get_comic_list] 执行排序: {sort_type}")
            
            if sort_type == "create_time":
                comics = sorted(comics, key=lambda c: c.create_time or "", reverse=True)
            elif sort_type == "score":
                comics = sorted(comics, key=lambda c: c.score or 0, reverse=True)
            elif sort_type == "read_time":
                comics = sorted(comics, key=lambda c: c.last_read_time or "", reverse=True)
            elif sort_type == "read_status":
                def read_status_sort_key(c):
                    is_read = c.current_page >= c.total_page if c.total_page > 0 else False
                    return (is_read, -(c.score or 0))
                comics = sorted(comics, key=read_status_sort_key)
            
            app_logger.info(f"[get_comic_list] 排序后漫画数量: {len(comics)}")
            
            comic_list = []
            for c in comics:
                # 确保封面存在（特别是 PK 平台，必要时用第 1 张图片生成）
                try:
                    self._ensure_cover(c)
                except Exception as e:
                    error_logger.error(f"确保漫画封面失败（列表）: {c.id}, {e}")
                
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
                    "list_ids": c.list_ids
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
            
            # 确保封面存在（如果缺失或文件不存在，用第 1 张图片生成）
            try:
                self._ensure_cover(comic)
            except Exception as e:
                error_logger.error(f"确保漫画封面失败（详情）: {comic_id}, {e}")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            preview_pages = get_preview_pages(comic.total_page)
            
            is_favorited = FAVORITES_LIST_ID in comic.list_ids
            storage_path, storage_path_kind = self._resolve_comic_storage_path(comic)
            
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
                "is_favorited": is_favorited,
                "source": "local",
                "import_source": comic.import_source,
                "storage_mode": comic.storage_mode,
                "soft_ref_locator": comic.soft_ref_locator,
                "storage_path": storage_path,
                "storage_path_kind": storage_path_kind,
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
    
    def filter_multi(self, include_tags: List[str] = None, exclude_tags: List[str] = None,
                     authors: List[str] = None, list_ids: List[str] = None) -> ServiceResult:
        try:
            comics = self._comic_repo.filter_multi(include_tags, exclude_tags, authors, list_ids)
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
                    "current_page": c.current_page,
                    "score": c.score,
                    "tag_ids": c.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "last_read_time": c.last_read_time,
                    "create_time": c.create_time,
                    "list_ids": c.list_ids
                }
                results.append(comic_info)
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(results)}")
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
    
    def get_trash_list(self) -> ServiceResult:
        """获取回收站漫画列表"""
        try:
            comics = self._comic_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 只获取已删除的漫画
            trash_comics = [c for c in comics if c.is_deleted]
            
            comic_list = []
            for c in trash_comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "create_time": c.create_time
                }
                comic_list.append(comic_info)
            
            app_logger.info(f"获取回收站列表成功，共 {len(comic_list)} 个漫画")
            return ServiceResult.ok(comic_list)
        except Exception as e:
            error_logger.error(f"获取回收站列表失败: {e}")
            return ServiceResult.error("获取回收站列表失败")
    
    def move_to_trash(self, comic_id: str) -> ServiceResult:
        """移动漫画到回收站"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.move_to_trash()
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("移入回收站失败")
            
            app_logger.info(f"漫画移入回收站: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已移入回收站")
        except Exception as e:
            error_logger.error(f"移入回收站失败: {e}")
            return ServiceResult.error("移入回收站失败")
    
    def restore_from_trash(self, comic_id: str) -> ServiceResult:
        """从回收站恢复漫画"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.restore_from_trash()
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("恢复失败")
            
            app_logger.info(f"漫画从回收站恢复: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已从回收站恢复")
        except Exception as e:
            error_logger.error(f"从回收站恢复失败: {e}")
            return ServiceResult.error("从回收站恢复失败")
    
    def batch_move_to_trash(self, comic_ids: List[str]) -> ServiceResult:
        """批量移动漫画到回收站"""
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.move_to_trash()
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移入回收站成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已将{updated_count}个漫画移入回收站")
        except Exception as e:
            error_logger.error(f"批量移入回收站失败: {e}")
            return ServiceResult.error("批量移入回收站失败")
    
    def batch_restore_from_trash(self, comic_ids: List[str]) -> ServiceResult:
        """批量从回收站恢复漫画"""
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.restore_from_trash()
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量从回收站恢复成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已恢复{updated_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量从回收站恢复失败: {e}")
            return ServiceResult.error("批量从回收站恢复失败")
    
    def delete_permanently(self, comic_id: str) -> ServiceResult:
        """永久删除漫画"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            self._cleanup_comic_files(comic)
            
            if not self._comic_repo.delete(comic_id):
                return ServiceResult.error("永久删除失败")
            
            app_logger.info(f"漫画已永久删除: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已永久删除")
        except Exception as e:
            error_logger.error(f"永久删除失败: {e}")
            return ServiceResult.error("永久删除失败")
    
    @staticmethod
    def _is_soft_ref_storage_mode(storage_mode: str) -> bool:
        return str(storage_mode or "").strip().lower() == "soft_ref"

    @staticmethod
    def _decode_softref_locator(locator: str) -> Dict[str, Any]:
        raw = str(locator or "").strip()
        if not raw.startswith("softref://"):
            return {}
        encoded = raw[len("softref://") :]
        if not encoded:
            return {}
        try:
            padding = "=" * ((4 - len(encoded) % 4) % 4)
            decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
            payload = json.loads(decoded)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _normalize_display_path(raw_path: str) -> str:
        path = str(raw_path or "").strip()
        if not path:
            return ""
        if path.startswith("softref://"):
            return ""
        if path.startswith(("http://", "https://")):
            return path
        try:
            return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        except Exception:
            return path

    def _resolve_comic_storage_path(self, comic: Comic) -> Tuple[str, str]:
        if not comic:
            return "", ""

        if self._is_soft_ref_storage_mode(getattr(comic, "storage_mode", "")):
            locator = str(getattr(comic, "soft_ref_locator", "") or getattr(comic, "import_source", "")).strip()
            payload = self._decode_softref_locator(locator) if locator.startswith("softref://") else {}
            kind = str(payload.get("kind", "")).strip().lower()
            if kind == "archive_dir":
                archive_path = self._normalize_display_path(payload.get("top_archive_path", ""))
                if archive_path:
                    return archive_path, "archive"
            source_path = self._normalize_display_path(getattr(comic, "import_source", ""))
            if source_path:
                return source_path, "source"
            locator_path = self._normalize_display_path(locator)
            if locator_path:
                return locator_path, "source"
            return "", ""

        try:
            from utils.file_parser import file_parser

            comic_dir = self._normalize_display_path(file_parser._get_comic_dir(comic.id))
            if comic_dir:
                return comic_dir, "local_dir"
        except Exception:
            pass

        source_path = self._normalize_display_path(getattr(comic, "import_source", ""))
        if source_path:
            return source_path, "source"
        return "", ""

    @staticmethod
    def _is_missing_cover_path(cover_path: str) -> bool:
        normalized = str(cover_path or "").strip()
        if not normalized:
            return True
        return normalized == "/static/default/default_cover.jpg"

    @staticmethod
    def _build_page1_cover_url(comic_id: str) -> str:
        return f"/api/v1/comic/image?comic_id={comic_id}&page_num=1"

    @staticmethod
    def _is_local_import_comic_id(comic_id: str) -> bool:
        try:
            from core.platform import get_original_id

            original_id = str(get_original_id(str(comic_id or "")) or "").strip().upper()
            return original_id.startswith("LOCAL")
        except Exception:
            return False

    def _generate_static_cover_from_soft_ref(self, comic_id: str) -> str:
        from application.softref_reader_protocol import require_softref_reader
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        from core.platform import Platform, get_original_id, get_platform_from_id

        try:
            softref_comic_reader = require_softref_reader("comic")
            stream, mimetype = softref_comic_reader.get_image_stream(comic_id, 1)
            image_bytes = stream.read() if stream else b""
            if not image_bytes:
                return ""

            platform = get_platform_from_id(comic_id)
            if platform == Platform.PK:
                cover_dir = PK_COVER_DIR
                cover_prefix = "PK"
            else:
                cover_dir = JM_COVER_DIR
                cover_prefix = "JM"

            original_id = get_original_id(comic_id)
            os.makedirs(cover_dir, exist_ok=True)
            lowered_mime = str(mimetype or "").lower()
            suffix = ".jpg"
            if "png" in lowered_mime:
                suffix = ".png"
            elif "webp" in lowered_mime:
                suffix = ".webp"

            cover_abs_path = os.path.join(cover_dir, f"{original_id}{suffix}")
            with open(cover_abs_path, "wb") as f:
                f.write(image_bytes)

            if not os.path.exists(cover_abs_path):
                return ""
            return f"/static/cover/{cover_prefix}/{original_id}{suffix}"
        except Exception as e:
            error_logger.error(f"Generate soft_ref cover failed: {comic_id}, {e}")
            return ""

    def _repair_soft_ref_cover_for_record(self, comic_data: dict) -> tuple:
        if not isinstance(comic_data, dict):
            return False, False, False
        if not self._is_soft_ref_storage_mode(comic_data.get("storage_mode", "")):
            return False, False, False

        comic_id = str(comic_data.get("id") or "").strip()
        if not comic_id:
            return False, False, False

        current_cover = str(comic_data.get("cover_path") or "").strip()
        if current_cover.startswith("/static/cover/"):
            from core.constants import COVER_DIR

            relative_cover = current_cover[len("/static/cover/") :].replace("/", os.sep)
            local_cover_path = os.path.join(COVER_DIR, relative_cover)
            if os.path.exists(local_cover_path):
                return False, False, False

        static_cover = self._generate_static_cover_from_soft_ref(comic_id)
        if static_cover:
            if current_cover == static_cover:
                return False, False, False
            comic_data["cover_path"] = static_cover
            return True, True, False

        fallback_cover = self._build_page1_cover_url(comic_id)
        if self._is_missing_cover_path(current_cover) and current_cover != fallback_cover:
            comic_data["cover_path"] = fallback_cover
            return True, False, True

        return False, False, False

    def _repair_local_import_cover_for_record(self, comic_data: dict) -> tuple:
        if not isinstance(comic_data, dict):
            return False, False

        comic_id = str(comic_data.get("id") or "").strip()
        if not comic_id or not self._is_local_import_comic_id(comic_id):
            return False, False

        from utils.file_parser import file_parser
        from utils.image_handler import ImageHandler

        try:
            image_paths = file_parser.parse_comic_images(comic_id)
        except Exception:
            image_paths = []

        next_cover = ""
        if image_paths:
            generated_cover = ImageHandler().generate_cover(comic_id, image_paths[0])
            if generated_cover and generated_cover != "/static/default/default_cover.jpg":
                next_cover = generated_cover
            else:
                next_cover = self._build_page1_cover_url(comic_id)
        elif self._is_missing_cover_path(comic_data.get("cover_path", "")):
            # 数据存在但图片目录暂不可读时，仍给出可读接口兜底，避免列表空白。
            next_cover = self._build_page1_cover_url(comic_id)

        if not next_cover:
            return False, False
        if str(comic_data.get("cover_path") or "").strip() == next_cover:
            return False, False

        comic_data["cover_path"] = next_cover
        return True, True

    def _cleanup_comic_files(self, comic):
        """清理漫画相关的所有文件"""
        import shutil
        from core.platform import get_platform_from_id
        from core.constants import COVER_DIR
        from utils.file_parser import file_parser
        
        platform = get_platform_from_id(comic.id)
        
        pictures_dir = None
        try:
            pictures_dir = file_parser._get_comic_dir(comic.id)
        except Exception as e:
            error_logger.error(f"推断漫画图片目录失败: {e}")
        
        if pictures_dir and os.path.exists(pictures_dir):
            try:
                shutil.rmtree(pictures_dir)
                app_logger.info(f"已删除漫画图片目录: {pictures_dir}")
            except Exception as e:
                error_logger.error(f"删除漫画图片目录失败: {e}")
        
        if comic.cover_path:
            # 移除开头的 / (如果是 web 路径)
            relative_path = comic.cover_path.lstrip('/')
            # 如果路径包含 static/cover，也尝试移除（因为 COVER_DIR 可能已经指向 static/cover）
            # 这里假设 COVER_DIR 是绝对路径，指向 static/cover
            if relative_path.startswith('static/cover/'):
                relative_path = relative_path.replace('static/cover/', '', 1)
            
            cover_path_full = os.path.join(COVER_DIR, relative_path)
            if os.path.exists(cover_path_full):
                try:
                    os.remove(cover_path_full)
                    app_logger.info(f"已删除漫画封面: {cover_path_full}")
                except Exception as e:
                    error_logger.error(f"删除漫画封面失败: {e}")
    
    def batch_delete_permanently(self, comic_ids: List[str]) -> ServiceResult:
        """批量永久删除漫画"""
        try:
            deleted_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    self._cleanup_comic_files(comic)
                if self._comic_repo.delete(comic_id):
                    deleted_count += 1
            
            if deleted_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量永久删除成功: {deleted_count}个漫画")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"已永久删除{deleted_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量永久删除失败: {e}")
            return ServiceResult.error("批量永久删除失败")
    
    def _ensure_cover(self, comic: Comic):
        """
        确保漫画有可用封面：
        - 如果本地封面文件不存在，则尝试用第 1 张图片生成封面
        - 成功后会更新并持久化 cover_path
        """
        from core.platform import get_platform_from_id, get_original_id, Platform
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        from utils.file_parser import file_parser
        from utils.image_handler import ImageHandler

        if self._is_soft_ref_storage_mode(getattr(comic, "storage_mode", "")):
            if self._is_missing_cover_path(comic.cover_path):
                fallback_cover_path = self._build_page1_cover_url(comic.id)
                if comic.cover_path != fallback_cover_path:
                    comic.cover_path = fallback_cover_path
                    self._comic_repo.save(comic)
            return
        
        platform = get_platform_from_id(comic.id)
        if platform not in (Platform.JM, Platform.PK):
            return
        
        original_id = get_original_id(comic.id)
        
        # 计算本地封面文件应在的路径
        if platform == Platform.JM:
            cover_dir = JM_COVER_DIR
            expected_prefix = "JM"
        else:
            cover_dir = PK_COVER_DIR
            expected_prefix = "PK"
        
        cover_full_path = os.path.join(cover_dir, f"{original_id}.jpg")
        
        # 如果本地封面文件已经存在，只需确保 cover_path 正确即可
        if os.path.exists(cover_full_path):
            expected_url = f"/static/cover/{expected_prefix}/{original_id}.jpg"
            if comic.cover_path != expected_url:
                comic.cover_path = expected_url
                self._comic_repo.save(comic)
            return
        
        # 本地没有封面文件：用第 1 张图片生成封面
        image_paths = file_parser.parse_comic_images(comic.id)
        if not image_paths:
            return
        
        handler = ImageHandler()
        new_cover_path = handler.generate_cover(comic.id, image_paths[0])
        if not new_cover_path or new_cover_path == "/static/default/default_cover.jpg":
            fallback_cover_path = f"/api/v1/comic/image?comic_id={comic.id}&page_num=1"
            if comic.cover_path != fallback_cover_path:
                comic.cover_path = fallback_cover_path
                self._comic_repo.save(comic)
            return

        if comic.cover_path != new_cover_path:
            comic.cover_path = new_cover_path
            self._comic_repo.save(comic)

    def _get_local_page_count(self, comic_id: str) -> int:
        """Count local downloaded image pages."""
        try:
            from utils.file_parser import file_parser
            return normalize_total_page(len(file_parser.parse_comic_images(comic_id)), default=0)
        except Exception as e:
            error_logger.error(f"Count local pages failed: {comic_id}, {e}")
            return 0

    def _extract_remote_total_page(self, meta_data: dict) -> int:
        """Extract remote total pages from adapter meta response."""
        if not isinstance(meta_data, dict):
            return 0

        albums = meta_data.get("albums") or []
        if not albums:
            return 0

        first_album = albums[0] if isinstance(albums[0], dict) else {}
        for value in (
            first_album.get("pages"),
            first_album.get("pages_count"),
            first_album.get("page_count"),
            first_album.get("total_page"),
        ):
            pages = normalize_total_page(value, default=0)
            if pages > 0:
                return pages
        return 0

    def _get_download_dir(self, platform):
        from core.platform import Platform
        from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR

        if platform == Platform.JM:
            return JM_PICTURES_DIR
        if platform == Platform.PK:
            return PK_PICTURES_DIR
        return None

    def _sync_cover_for_record(self, comic_data: dict, platform_service) -> tuple:
        """
        Ensure local cover file and web cover_path for one record.
        Returns: (downloaded_cover, updated_cover_path)
        """
        from core.platform import Platform, get_platform_from_id, get_original_id
        from core.constants import JM_COVER_DIR, PK_COVER_DIR

        if self._is_soft_ref_storage_mode(comic_data.get("storage_mode", "")):
            return False, False

        if self._is_local_import_comic_id(comic_data.get("id", "")):
            updated, _ = self._repair_local_import_cover_for_record(comic_data)
            return False, updated

        comic_id = comic_data.get("id")
        platform = get_platform_from_id(comic_id)
        if platform not in (Platform.JM, Platform.PK):
            return False, False

        original_id = get_original_id(comic_id)
        cover_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
        cover_prefix = "JM" if platform == Platform.JM else "PK"
        cover_file = os.path.join(cover_dir, f"{original_id}.jpg")
        cover_url = f"/static/cover/{cover_prefix}/{original_id}.jpg"

        downloaded = False
        updated = False

        if not os.path.exists(cover_file):
            _, success = platform_service.download_cover(
                platform,
                original_id,
                save_path=cover_file,
                show_progress=False
            )
            downloaded = bool(success and os.path.exists(cover_file))

        if os.path.exists(cover_file) and comic_data.get("cover_path") != cover_url:
            comic_data["cover_path"] = cover_url
            updated = True

        return downloaded, updated

    @staticmethod
    def _strip_bracket_segments(raw_title: str) -> str:
        text = str(raw_title or "")
        if not text:
            return ""

        patterns = (
            r"\([^()]*\)",
            r"（[^（）]*）",
            r"\[[^\[\]]*\]",
            r"【[^【】]*】",
            r"\{[^{}]*\}",
            r"＜[^＜＞]*＞",
            r"<[^<>]*>",
        )

        previous = None
        current = text
        while previous != current:
            previous = current
            for pattern in patterns:
                current = re.sub(pattern, "", current)
        return current

    @classmethod
    def _normalize_title_for_compare(cls, raw_title: str) -> str:
        text = cls._strip_bracket_segments(raw_title)
        text = re.sub(r"\s+", "", text).strip().lower()
        return text

    @staticmethod
    def _chinese_numeral_to_int(raw_value: str) -> Optional[int]:
        text = str(raw_value or "").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)

        digits = {
            "零": 0,
            "〇": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }
        units = {"十": 10, "百": 100, "千": 1000}

        total = 0
        current_digit = 0
        has_value = False
        for char in text:
            if char in digits:
                current_digit = digits[char]
                has_value = True
                continue
            if char in units:
                has_value = True
                if current_digit == 0:
                    current_digit = 1
                total += current_digit * units[char]
                current_digit = 0
                continue
            return None

        if not has_value:
            return None
        total += current_digit
        return total if total > 0 else None

    @classmethod
    def _extract_chapter_signature(cls, raw_title: str) -> str:
        title_text = cls._strip_bracket_segments(raw_title)
        if not title_text:
            return ""
        text = title_text.lower()

        token_list: List[str] = []

        for match in re.finditer(r"第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*(章|话|回|卷|册|集)", text):
            raw_num = str(match.group(1) or "").strip()
            suffix = str(match.group(2) or "").strip()
            normalized_num = cls._chinese_numeral_to_int(raw_num)
            number_text = str(normalized_num) if normalized_num is not None else raw_num
            if suffix and number_text:
                token_list.append(f"{suffix}:{number_text}")

        for match in re.finditer(r"(上|中|下|前|后)\s*(卷|册|篇|部)", text):
            position = str(match.group(1) or "").strip()
            category = str(match.group(2) or "").strip()
            if position and category:
                token_list.append(f"{category}:{position}")

        for match in re.finditer(r"\b(vol(?:ume)?|ch(?:apter)?|ep(?:isode)?)\s*\.?\s*([0-9]+)\b", text):
            raw_prefix = str(match.group(1) or "").strip().lower()
            number_text = str(match.group(2) or "").strip()
            if not number_text:
                continue
            if raw_prefix.startswith("vol"):
                prefix = "vol"
            elif raw_prefix.startswith("ch"):
                prefix = "ch"
            else:
                prefix = "ep"
            token_list.append(f"{prefix}:{number_text}")

        for match in re.finditer(r"\b([0-9]+)\s*(卷|册|章|话|回|集)\b", text):
            number_text = str(match.group(1) or "").strip()
            suffix = str(match.group(2) or "").strip()
            if suffix and number_text:
                token_list.append(f"{suffix}:{number_text}")

        unique_tokens: List[str] = []
        seen_tokens = set()
        for token in token_list:
            normalized_token = str(token or "").strip().lower()
            if not normalized_token or normalized_token in seen_tokens:
                continue
            seen_tokens.add(normalized_token)
            unique_tokens.append(normalized_token)

        return "|".join(unique_tokens)

    @classmethod
    def _build_dedupe_key(cls, raw_title: str) -> Tuple[str, str]:
        clean_title = cls._normalize_title_for_compare(raw_title)
        chapter_signature = cls._extract_chapter_signature(raw_title)
        chapter_key = chapter_signature or "__no_chapter__"
        return clean_title, chapter_key

    def _deduplicate_records_by_title(self, records: List[dict]) -> Dict[str, Any]:
        grouped: Dict[Tuple[str, str], List[dict]] = {}
        stats = {
            "total_records": len(records),
            "candidate_records": 0,
            "skipped_deleted_records": 0,
            "skipped_invalid_title_records": 0,
            "duplicate_groups": 0,
            "kept_records": 0,
            "moved_to_trash": 0,
            "moved_ids": [],
        }

        for record in records:
            if not isinstance(record, dict):
                stats["skipped_invalid_title_records"] += 1
                continue

            if bool(record.get("is_deleted", False)):
                stats["skipped_deleted_records"] += 1
                continue

            clean_title, chapter_key = self._build_dedupe_key(record.get("title", ""))
            if not clean_title:
                stats["skipped_invalid_title_records"] += 1
                continue

            stats["candidate_records"] += 1
            grouped.setdefault((clean_title, chapter_key), []).append(record)

        for group_records in grouped.values():
            if len(group_records) <= 1:
                continue
            stats["duplicate_groups"] += 1
            stats["kept_records"] += 1
            for duplicate in group_records[1:]:
                if bool(duplicate.get("is_deleted", False)):
                    continue
                duplicate["is_deleted"] = True
                stats["moved_to_trash"] += 1
                duplicate_id = str(duplicate.get("id") or "").strip()
                if duplicate_id:
                    stats["moved_ids"].append(duplicate_id)

        return stats

    def organize_deduplicate_by_title(self) -> ServiceResult:
        try:
            from infrastructure.persistence.json_storage import JsonStorage
            from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE

            home_storage = JsonStorage(JSON_FILE)
            home_data = home_storage.read()
            home_records = home_data.get("comics", [])
            if not isinstance(home_records, list):
                home_records = []
                home_data["comics"] = home_records
            home_stats = self._deduplicate_records_by_title(home_records)
            if not home_storage.write(home_data):
                return ServiceResult.error("Failed to write home database")

            rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            rec_records = rec_data.get("recommendations", [])
            if not isinstance(rec_records, list):
                rec_records = []
                rec_data["recommendations"] = rec_records
            rec_stats = self._deduplicate_records_by_title(rec_records)
            if not rec_storage.write(rec_data):
                return ServiceResult.error("Failed to write recommendation database")

            moved_total = int(home_stats.get("moved_to_trash", 0)) + int(rec_stats.get("moved_to_trash", 0))
            summary = (
                f"查重完成：本地库移入回收站 {home_stats.get('moved_to_trash', 0)} 项，"
                f"预览库移入回收站 {rec_stats.get('moved_to_trash', 0)} 项，"
                f"合计 {moved_total} 项"
            )

            return ServiceResult.ok(
                {
                    "home": home_stats,
                    "recommendation": rec_stats,
                    "summary": summary,
                },
                "Deduplicate completed",
            )
        except Exception as e:
            error_logger.error(f"Organize deduplicate failed: {e}")
            return ServiceResult.error("Deduplicate failed")

    @staticmethod
    def _normalize_tag_name(raw_name: Any) -> str:
        text = str(raw_name or "").strip()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text

    def _build_comic_tag_lookup(self, tags_data: dict) -> Tuple[Dict[str, str], int]:
        tag_name_to_id: Dict[str, str] = {}
        max_tag_num = 0
        tag_items = tags_data.get("tags", [])
        if not isinstance(tag_items, list):
            tag_items = []
            tags_data["tags"] = tag_items

        for tag in tag_items:
            if not isinstance(tag, dict):
                continue
            tag_name = self._normalize_tag_name(tag.get("name", ""))
            tag_id = str(tag.get("id") or "").strip()
            if not tag_name or not tag_id:
                continue

            content_type = str(tag.get("content_type", ContentType.COMIC.value) or "").strip().lower()
            if content_type not in {ContentType.COMIC.value, ContentType.VIDEO.value}:
                content_type = ContentType.COMIC.value
            if content_type != ContentType.COMIC.value:
                continue

            tag_key = tag_name.lower()
            if tag_key not in tag_name_to_id:
                tag_name_to_id[tag_key] = tag_id

            if tag_id.startswith("tag_"):
                try:
                    tag_num = int(tag_id[4:])
                    max_tag_num = max(max_tag_num, tag_num)
                except Exception:
                    continue

        return tag_name_to_id, max_tag_num

    def _ensure_comic_tags_for_record(
        self,
        comic_data: dict,
        raw_tag_names: List[Any],
        tags_data: dict,
        tag_name_to_id: Dict[str, str],
        max_tag_num_holder: List[int],
    ) -> Tuple[int, int]:
        if not isinstance(comic_data, dict):
            return 0, 0

        normalized_tag_names: List[str] = []
        seen_names = set()
        for raw_tag_name in raw_tag_names or []:
            tag_name = self._normalize_tag_name(raw_tag_name)
            if not tag_name:
                continue
            tag_key = tag_name.lower()
            if tag_key in seen_names:
                continue
            seen_names.add(tag_key)
            normalized_tag_names.append(tag_name)

        if not normalized_tag_names:
            return 0, 0

        tag_items = tags_data.setdefault("tags", [])
        if not isinstance(tag_items, list):
            tag_items = []
            tags_data["tags"] = tag_items

        created_count = 0
        append_ids: List[str] = []

        for tag_name in normalized_tag_names:
            tag_key = tag_name.lower()
            tag_id = tag_name_to_id.get(tag_key, "")
            if not tag_id:
                max_tag_num_holder[0] += 1
                tag_id = f"tag_{max_tag_num_holder[0]:03d}"
                tag_name_to_id[tag_key] = tag_id
                tag_items.append(
                    {
                        "id": tag_id,
                        "name": tag_name,
                        "content_type": ContentType.COMIC.value,
                        "create_time": get_current_time(),
                    }
                )
                created_count += 1
            append_ids.append(tag_id)

        existing_tag_ids = comic_data.get("tag_ids", [])
        if not isinstance(existing_tag_ids, list):
            existing_tag_ids = []
        merged_tag_ids = list(existing_tag_ids)
        bound_count = 0
        for tag_id in append_ids:
            if tag_id in merged_tag_ids:
                continue
            merged_tag_ids.append(tag_id)
            bound_count += 1

        comic_data["tag_ids"] = merged_tag_ids
        return created_count, bound_count

    def _match_first_search_result(self, platform_service, platform, clean_title: str, chapter_key: str) -> Dict[str, Any]:
        if not clean_title:
            return {}

        # Use lightweight search and only inspect the first candidate, then fetch detail for that one item.
        search_result = platform_service.search_albums(platform, clean_title, max_pages=1, fast_mode=True) or {}
        albums = search_result.get("albums") or []
        if not albums or not isinstance(albums[0], dict):
            return {}

        first_album = albums[0]
        remote_album_id = str(first_album.get("album_id") or first_album.get("id") or "").strip()
        if not remote_album_id:
            return {}

        detail = first_album
        try:
            detail_result = platform_service.get_album_by_id(platform, remote_album_id) or {}
            detail_albums = detail_result.get("albums") or []
            if detail_albums and isinstance(detail_albums[0], dict):
                detail = detail_albums[0]
        except Exception as detail_error:
            error_logger.error(
                f"Fetch remote detail failed: platform={getattr(platform, 'value', platform)}, album_id={remote_album_id}, error={detail_error}"
            )

        return {
            "platform": getattr(platform, "value", str(platform)),
            "album_id": remote_album_id,
            "detail": detail,
        }

    def organize_enrich_local_metadata(self) -> ServiceResult:
        try:
            from infrastructure.persistence.json_storage import JsonStorage
            from core.constants import JSON_FILE, TAGS_JSON_FILE
            from core.platform import Platform
            from core.runtime_profile import is_third_party_enabled

            home_storage = JsonStorage(JSON_FILE)
            home_data = home_storage.read()
            home_records = home_data.get("comics", [])
            if not isinstance(home_records, list):
                home_records = []
                home_data["comics"] = home_records

            stats = {
                "total_records": len(home_records),
                "total_local_candidates": 0,
                "processed_candidates": 0,
                "skipped_deleted": 0,
                "skipped_already_enriched": 0,
                "skipped_invalid_title": 0,
                "skipped_no_match": 0,
                "skipped_third_party_disabled": 0,
                "matched_on_jm": 0,
                "matched_on_pk": 0,
                "updated_records": 0,
                "updated_authors": 0,
                "updated_tag_bindings": 0,
                "created_tags": 0,
                "failed_records": 0,
                "updated_ids": [],
            }

            if not is_third_party_enabled():
                for comic in home_records:
                    if not isinstance(comic, dict):
                        continue
                    if bool(comic.get("is_deleted", False)):
                        continue
                    comic_id = str(comic.get("id") or "").strip()
                    if not self._is_local_import_comic_id(comic_id):
                        continue
                    stats["total_local_candidates"] += 1
                    stats["skipped_third_party_disabled"] += 1

                summary = f"LOCAL 补全跳过：当前运行配置关闭第三方能力，跳过 {stats['skipped_third_party_disabled']} 项"
                stats["summary"] = summary
                return ServiceResult.ok(stats, "Local metadata enrich skipped")

            from third_party.platform_service import get_platform_service

            platform_service = get_platform_service()
            tag_storage = JsonStorage(TAGS_JSON_FILE)
            tags_data = tag_storage.read()
            tag_name_to_id, max_tag_num = self._build_comic_tag_lookup(tags_data)
            max_tag_num_holder = [max_tag_num]
            tag_changed = False
            match_cache: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

            for comic in home_records:
                if not isinstance(comic, dict):
                    continue

                if bool(comic.get("is_deleted", False)):
                    stats["skipped_deleted"] += 1
                    continue

                comic_id = str(comic.get("id") or "").strip()
                if not self._is_local_import_comic_id(comic_id):
                    continue

                stats["total_local_candidates"] += 1

                if bool(comic.get("local_metadata_enriched", False)):
                    stats["skipped_already_enriched"] += 1
                    continue

                clean_title, chapter_key = self._build_dedupe_key(comic.get("title", ""))
                if not clean_title:
                    stats["skipped_invalid_title"] += 1
                    continue

                stats["processed_candidates"] += 1
                matched = {}
                cache_key = (clean_title, chapter_key)
                if cache_key in match_cache:
                    cached = match_cache.get(cache_key)
                    matched = dict(cached) if isinstance(cached, dict) else {}
                else:
                    jm_error = None
                    pk_error = None
                    try:
                        matched = self._match_first_search_result(platform_service, Platform.JM, clean_title, chapter_key)
                    except Exception as match_error:
                        jm_error = match_error
                        error_logger.error(f"Match on JM failed: comic_id={comic_id}, error={match_error}")

                    if not matched:
                        try:
                            matched = self._match_first_search_result(platform_service, Platform.PK, clean_title, chapter_key)
                        except Exception as match_error:
                            pk_error = match_error
                            error_logger.error(f"Match on PK failed: comic_id={comic_id}, error={match_error}")

                    if not matched and (jm_error is not None or pk_error is not None):
                        stats["failed_records"] += 1

                    match_cache[cache_key] = dict(matched) if isinstance(matched, dict) and matched else None

                if not matched:
                    stats["skipped_no_match"] += 1
                    continue

                matched_platform = str(matched.get("platform") or "").strip().upper()
                if matched_platform == Platform.JM.value:
                    stats["matched_on_jm"] += 1
                elif matched_platform == Platform.PK.value:
                    stats["matched_on_pk"] += 1

                detail = matched.get("detail") if isinstance(matched.get("detail"), dict) else {}
                updated = False

                remote_author = str(detail.get("author") or "").strip()
                if remote_author and remote_author != str(comic.get("author") or "").strip():
                    comic["author"] = remote_author
                    stats["updated_authors"] += 1
                    updated = True

                remote_tags = detail.get("tags") if isinstance(detail.get("tags"), list) else []
                created_count, bound_count = self._ensure_comic_tags_for_record(
                    comic,
                    remote_tags,
                    tags_data,
                    tag_name_to_id,
                    max_tag_num_holder,
                )
                if created_count > 0:
                    stats["created_tags"] += created_count
                    tag_changed = True
                    updated = True
                if bound_count > 0:
                    stats["updated_tag_bindings"] += bound_count
                    updated = True

                comic["local_metadata_enriched"] = True
                if updated:
                    stats["updated_records"] += 1
                    if comic_id:
                        stats["updated_ids"].append(comic_id)

            if tag_changed:
                if not tag_storage.write(tags_data):
                    return ServiceResult.error("Failed to write tags database")

            if not home_storage.write(home_data):
                return ServiceResult.error("Failed to write home database")

            summary = (
                f"LOCAL 补全完成：成功 {stats['updated_records']}，"
                f"无匹配 {stats['skipped_no_match']}，"
                f"已补全跳过 {stats['skipped_already_enriched']}，"
                f"新增标签 {stats['created_tags']}"
            )
            stats["summary"] = summary

            return ServiceResult.ok(stats, "Local metadata enrich completed")
        except Exception as e:
            error_logger.error(f"Organize enrich local metadata failed: {e}")
            return ServiceResult.error("Local metadata enrich failed")

    def _normalize_comic_remote_tags(self, raw_tags: Any) -> List[str]:
        if not isinstance(raw_tags, list):
            return []
        normalized: List[str] = []
        seen = set()
        for item in raw_tags:
            if isinstance(item, dict):
                name = self._normalize_tag_name(item.get("name") or item.get("tag") or "")
            else:
                name = self._normalize_tag_name(item)
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        return normalized

    def _ensure_comic_tags_for_entity(
        self,
        comic: Comic,
        remote_tags: Any,
        tag_name_to_id: Dict[str, str],
    ) -> Tuple[int, int]:
        remote_tag_names = self._normalize_comic_remote_tags(remote_tags)
        if not remote_tag_names:
            return 0, 0

        current_tag_ids = list(comic.tag_ids or [])
        created_count = 0
        bound_count = 0

        for tag_name in remote_tag_names:
            key = tag_name.lower()
            tag_id = tag_name_to_id.get(key, "")
            if not tag_id:
                created_tag = self._tag_repo.create(tag_name, ContentType.COMIC)
                if created_tag:
                    tag_id = created_tag.id
                    tag_name_to_id[key] = tag_id
                    created_count += 1
                else:
                    comic_tags = self._tag_repo.get_all(ContentType.COMIC)
                    for tag in comic_tags:
                        if self._normalize_tag_name(tag.name).lower() == key:
                            tag_id = tag.id
                            tag_name_to_id[key] = tag_id
                            break

            if not tag_id:
                continue
            if tag_id in current_tag_ids:
                continue
            current_tag_ids.append(tag_id)
            bound_count += 1

        if bound_count > 0:
            comic.tag_ids = current_tag_ids
        return created_count, bound_count

    def refresh_local_comic_metadata(self, comic_id: str) -> ServiceResult:
        try:
            from core.platform import Platform
            from core.runtime_profile import is_third_party_enabled

            target_comic_id = str(comic_id or "").strip()
            if not target_comic_id:
                return ServiceResult.error("missing parameter: comic_id")

            comic = self._comic_repo.get_by_id(target_comic_id)
            if not comic:
                return ServiceResult.error("comic not found")
            if bool(comic.is_deleted):
                return ServiceResult.error("comic is deleted")
            if not self._is_local_import_comic_id(comic.id):
                return ServiceResult.error("only LOCAL comics support metadata refresh")

            if not is_third_party_enabled():
                return ServiceResult.error("third-party integration is disabled in current runtime profile")

            clean_title, chapter_key = self._build_dedupe_key(comic.title or "")
            if not clean_title:
                return ServiceResult.error("comic title is invalid for metadata matching")

            from third_party.platform_service import get_platform_service
            platform_service = get_platform_service()

            matched = {}
            matched_platform = ""
            try:
                matched = self._match_first_search_result(platform_service, Platform.JM, clean_title, chapter_key)
                if matched:
                    matched_platform = Platform.JM.value
            except Exception as match_error:
                error_logger.error(f"refresh local comic metadata match on JM failed: comic_id={target_comic_id}, error={match_error}")

            if not matched:
                try:
                    matched = self._match_first_search_result(platform_service, Platform.PK, clean_title, chapter_key)
                    if matched:
                        matched_platform = Platform.PK.value
                except Exception as match_error:
                    error_logger.error(f"refresh local comic metadata match on PK failed: comic_id={target_comic_id}, error={match_error}")

            if not matched:
                return ServiceResult.error("no remote match found for current comic")

            detail = matched.get("detail") if isinstance(matched.get("detail"), dict) else {}

            updated_fields = 0
            remote_author = str(detail.get("author") or "").strip()
            if remote_author and remote_author != str(comic.author or "").strip():
                comic.author = remote_author
                updated_fields += 1

            comic_tags = self._tag_repo.get_all(ContentType.COMIC)
            tag_name_to_id = {
                self._normalize_tag_name(tag.name).lower(): tag.id
                for tag in comic_tags
                if self._normalize_tag_name(tag.name)
            }
            created_tags, bound_tags = self._ensure_comic_tags_for_entity(comic, detail.get("tags"), tag_name_to_id)
            if bound_tags > 0:
                updated_fields += 1

            if not bool(getattr(comic, "local_metadata_enriched", False)):
                comic.local_metadata_enriched = True
                updated_fields += 1

            if not self._comic_repo.save(comic):
                return ServiceResult.error("save comic metadata failed")

            detail_result = self.get_comic_detail(comic.id)
            detail_payload = detail_result.data if detail_result.success else (comic.to_dict() if hasattr(comic, "to_dict") else {})
            if isinstance(detail_payload, dict):
                detail_payload["metadata_refresh"] = {
                    "matched_platform": matched_platform,
                    "updated_fields": updated_fields,
                    "created_tags": created_tags,
                    "bound_tags": bound_tags,
                }
            return ServiceResult.ok(detail_payload, "local comic metadata refreshed")
        except Exception as e:
            error_logger.error(f"refresh local comic metadata failed: {comic_id}, {e}")
            return ServiceResult.error("refresh local comic metadata failed")

    def check_comic_update(self, comic_id: str) -> ServiceResult:
        """Check whether remote comic has more pages than local files."""
        try:
            from core.platform import Platform, get_platform_from_id, get_original_id
            from third_party.platform_service import get_platform_service

            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("Comic not found")

            platform = get_platform_from_id(comic_id)
            if platform not in (Platform.JM, Platform.PK):
                return ServiceResult.error("Current platform does not support update check")

            local_page_count = self._get_local_page_count(comic_id)
            db_total_page = normalize_total_page(comic.total_page, default=0)

            platform_service = get_platform_service()
            remote_meta = platform_service.get_album_by_id(platform, get_original_id(comic_id))
            remote_total_page = self._extract_remote_total_page(remote_meta)
            if remote_total_page <= 0:
                return ServiceResult.error("Failed to get remote page count")

            has_update = remote_total_page > local_page_count
            return ServiceResult.ok({
                "comic_id": comic_id,
                "db_total_page": db_total_page,
                "local_page_count": local_page_count,
                "remote_total_page": remote_total_page,
                "has_update": has_update,
                "can_update": True
            }, "Update check completed")
        except Exception as e:
            error_logger.error(f"Check comic update failed: {comic_id}, {e}")
            return ServiceResult.error("Update check failed")

    def download_comic_update(self, comic_id: str, force: bool = False) -> ServiceResult:
        """Download update and sync total_page with local file count."""
        try:
            from core.platform import Platform, get_platform_from_id, get_original_id
            from third_party.platform_service import get_platform_service

            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("Comic not found")

            check_result = self.check_comic_update(comic_id)
            if not check_result.success:
                return check_result

            check_data = check_result.data or {}
            has_update = bool(check_data.get("has_update"))
            if not has_update and not force:
                return ServiceResult.error("No downloadable update found")

            platform = get_platform_from_id(comic_id)
            if platform not in (Platform.JM, Platform.PK):
                return ServiceResult.error("Current platform does not support update download")

            download_dir = self._get_download_dir(platform)
            if not download_dir:
                return ServiceResult.error("Download directory not found")

            platform_service = get_platform_service()
            kwargs = {}
            if platform == Platform.JM:
                kwargs["decode_images"] = True

            _, success = platform_service.download_album(
                platform,
                get_original_id(comic_id),
                download_dir=download_dir,
                show_progress=False,
                **kwargs
            )
            if not success:
                return ServiceResult.error("Update download failed")

            local_page_count = self._get_local_page_count(comic_id)
            if local_page_count <= 0:
                return ServiceResult.error("No local pages found after download")

            old_total_page = normalize_total_page(comic.total_page, default=0)
            old_current_page = normalize_total_page(comic.current_page, default=1)
            comic.total_page = local_page_count
            comic.current_page = max(1, min(old_current_page, local_page_count))

            if not self._comic_repo.save(comic):
                return ServiceResult.error("Failed to persist updated page count")

            try:
                self._ensure_cover(comic)
            except Exception as cover_error:
                error_logger.error(f"Ensure cover after update failed: {comic_id}, {cover_error}")

            return ServiceResult.ok({
                "comic_id": comic_id,
                "had_update": has_update,
                "old_total_page": old_total_page,
                "local_page_count": local_page_count,
                "current_page": comic.current_page
            }, "Update download completed")
        except Exception as e:
            error_logger.error(f"Download comic update failed: {comic_id}, {e}")
            return ServiceResult.error("Update download failed")

    def organize_database_v2(self) -> ServiceResult:
        """
        New organize flow:
        1) Repair missing covers for home/recommendation DB.
        2) Rewrite home comics total_page from local downloaded image count.
        3) Clamp current_page into [1, total_page] when local pages exist.
        """
        try:
            from infrastructure.persistence.json_storage import JsonStorage
            from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE
            from third_party.platform_service import get_platform_service

            platform_service = get_platform_service()

            # Home DB
            home_storage = JsonStorage(JSON_FILE)
            home_data = home_storage.read()
            home_comics = home_data.get("comics", [])

            home_stats = {
                "total_comics": len(home_comics),
                "downloaded_covers": 0,
                "updated_cover_paths": 0,
                "soft_ref_generated_covers": 0,
                "soft_ref_fallback_covers": 0,
                "rewritten_total_pages": 0,
                "corrected_current_pages": 0,
                "skipped_empty_local_pages": 0,
                "failed_comics": 0,
                # keep legacy field for compatibility
                "re_downloaded_comics": 0
            }

            for comic in home_comics:
                comic_id = comic.get("id", "")
                try:
                    soft_ref_updated, generated_static_cover, fallback_cover = self._repair_soft_ref_cover_for_record(comic)
                    if soft_ref_updated:
                        home_stats["updated_cover_paths"] += 1
                    if generated_static_cover:
                        home_stats["downloaded_covers"] += 1
                        home_stats["soft_ref_generated_covers"] += 1
                    if fallback_cover:
                        home_stats["soft_ref_fallback_covers"] += 1

                    if self._is_soft_ref_storage_mode(comic.get("storage_mode", "")):
                        continue

                    downloaded, cover_updated = self._sync_cover_for_record(comic, platform_service)
                    if downloaded:
                        home_stats["downloaded_covers"] += 1
                    if cover_updated:
                        home_stats["updated_cover_paths"] += 1

                    local_page_count = self._get_local_page_count(comic_id)
                    db_total_page = normalize_total_page(comic.get("total_page", 0), default=0)
                    db_current_page = normalize_total_page(comic.get("current_page", 1), default=1)

                    if local_page_count > 0:
                        if db_total_page != local_page_count:
                            comic["total_page"] = local_page_count
                            home_stats["rewritten_total_pages"] += 1

                        corrected_current = max(1, min(db_current_page, local_page_count))
                        if corrected_current != db_current_page:
                            comic["current_page"] = corrected_current
                            home_stats["corrected_current_pages"] += 1
                    else:
                        # Do not overwrite total_page to 0 when local files are not found.
                        home_stats["skipped_empty_local_pages"] += 1
                except Exception as item_error:
                    home_stats["failed_comics"] += 1
                    error_logger.error(f"Organize home comic failed: {comic_id}, {item_error}")

            if not home_storage.write(home_data):
                return ServiceResult.error("Failed to write home database")

            # Recommendation DB (cover repair only)
            rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            rec_comics = rec_data.get("recommendations", [])

            rec_stats = {
                "total_comics": len(rec_comics),
                "downloaded_covers": 0,
                "updated_cover_paths": 0,
                "failed_comics": 0
            }

            for comic in rec_comics:
                comic_id = comic.get("id", "")
                try:
                    downloaded, cover_updated = self._sync_cover_for_record(comic, platform_service)
                    if downloaded:
                        rec_stats["downloaded_covers"] += 1
                    if cover_updated:
                        rec_stats["updated_cover_paths"] += 1
                except Exception as item_error:
                    rec_stats["failed_comics"] += 1
                    error_logger.error(f"Organize recommendation comic failed: {comic_id}, {item_error}")

            if not rec_storage.write(rec_data):
                return ServiceResult.error("Failed to write recommendation database")

            return ServiceResult.ok({
                "home": home_stats,
                "recommendation": rec_stats
            }, "Database organize completed")
        except Exception as e:
            error_logger.error(f"Organize database v2 failed: {e}")
            return ServiceResult.error("Database organize failed")
    
    def organize_database(self) -> ServiceResult:
        """整理数据库"""
        try:
            from infrastructure.persistence.json_storage import JsonStorage
            from core.platform import remove_platform_prefix, get_platform_from_id
            from core.constants import JSON_FILE
            from third_party.platform_service import get_platform_service
            
            app_logger.info("开始整理数据库...")
            platform_service = get_platform_service()
            
            # 整理主页数据库
            storage = JsonStorage(JSON_FILE)
            db_data = storage.read()
            comics = db_data.get('comics', [])
            
            total_comics = len(comics)
            processed_comics = 0
            downloaded_covers = 0
            re_downloaded_comics = 0
            
            app_logger.info(f"主页数据库中共有 {total_comics} 个漫画")
            
            # 遍历所有漫画
            for comic in comics:
                comic_id = comic['id']
                processed_comics += 1
                
                if processed_comics % 10 == 0:
                    app_logger.info(f"已处理 {processed_comics}/{total_comics} 个漫画")
                
                platform = get_platform_from_id(comic_id)
                
                # 检查封面
                cover_path = comic.get('cover_path', '')
                if not cover_path or cover_path.startswith('http'):
                    try:
                        # 尝试使用 PlatformService 下载封面
                        # 注意：这里需要计算正确的保存路径
                        from core.constants import JM_COVER_DIR, PK_COVER_DIR
                        from core.platform import Platform
                        
                        save_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
                        save_path = os.path.join(save_dir, f"{remove_platform_prefix(comic_id)[1]}.jpg")
                        
                        # 如果文件已存在，直接更新路径
                        if os.path.exists(save_path):
                            pass # 下面统一处理
                        else:
                            # 下载
                            detail, success = platform_service.download_cover(
                                platform, 
                                remove_platform_prefix(comic_id)[1],
                                save_path=save_path
                            )
                            if success:
                                downloaded_covers += 1
                                app_logger.info(f"下载封面成功: {comic_id}")
                        
                        # 更新数据库路径
                        if os.path.exists(save_path):
                            prefix = "JM" if platform == Platform.JM else "PK"
                            new_path = f"/static/cover/{prefix}/{remove_platform_prefix(comic_id)[1]}.jpg"
                            if comic.get('cover_path') != new_path:
                                comic['cover_path'] = new_path
                                app_logger.info(f"更新封面路径: {comic_id} -> {new_path}")
                                
                    except Exception as e:
                        error_logger.error(f"处理封面失败 {comic_id}: {e}")
                
                # 检查漫画页数 (JM Only)
                # 这里的逻辑比较特定，暂时保留 platform 判断，或者可以抽象到 PlatformService 的 verify_album 接口
                if platform == Platform.JM:
                    total_page = comic.get('total_page', 0)
                    if total_page > 0:
                        try:
                            from utils.file_parser import file_parser
                            from core.constants import JM_PICTURES_DIR
                            
                            image_paths = file_parser.parse_comic_images(comic_id)
                            if len(image_paths) < total_page:
                                # 重新下载漫画
                                original_id = remove_platform_prefix(comic_id)[1]
                                detail, success = platform_service.download_album(
                                    platform,
                                    original_id,
                                    download_dir=JM_PICTURES_DIR,
                                    show_progress=False,
                                    decode_images=True
                                )
                                
                                if success:
                                    re_downloaded_comics += 1
                                    app_logger.info(f"重新下载漫画成功: {comic_id} (累计: {re_downloaded_comics})")
                        except Exception as e:
                            error_logger.error(f"重新下载漫画失败 {comic_id}: {e}")
            
            # 保存主页数据库
            storage.write(db_data)
            
            # 整理推荐页数据库
            app_logger.info("开始整理推荐页数据库...")
            from core.constants import RECOMMENDATION_JSON_FILE
            
            rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            recommendations = rec_data.get('recommendations', [])
            
            total_recommendations = len(recommendations)
            processed_recommendations = 0
            rec_downloaded_covers = 0
            
            app_logger.info(f"推荐页数据库中共有 {total_recommendations} 个漫画")
            
            # 遍历所有推荐漫画
            for comic in recommendations:
                comic_id = comic['id']
                processed_recommendations += 1
                
                if processed_recommendations % 10 == 0:
                    app_logger.info(f"已处理 {processed_recommendations}/{total_recommendations} 个推荐漫画")
                
                platform = get_platform_from_id(comic_id)
                
                # 检查封面
                cover_path = comic.get('cover_path', '')
                if not cover_path or cover_path.startswith('http'):
                    try:
                        from core.constants import JM_COVER_DIR, PK_COVER_DIR
                        from core.platform import Platform
                        
                        save_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
                        save_path = os.path.join(save_dir, f"{remove_platform_prefix(comic_id)[1]}.jpg")
                        
                        if not os.path.exists(save_path):
                            detail, success = platform_service.download_cover(
                                platform,
                                remove_platform_prefix(comic_id)[1],
                                save_path=save_path
                            )
                            if success:
                                rec_downloaded_covers += 1
                                app_logger.info(f"下载推荐页封面成功: {comic_id}")
                        
                        if os.path.exists(save_path):
                            prefix = "JM" if platform == Platform.JM else "PK"
                            new_path = f"/static/cover/{prefix}/{remove_platform_prefix(comic_id)[1]}.jpg"
                            if comic.get('cover_path') != new_path:
                                comic['cover_path'] = new_path
                                app_logger.info(f"更新推荐页封面路径: {comic_id} -> {new_path}")
                                
                    except Exception as e:
                        error_logger.error(f"处理推荐页封面失败 {comic_id}: {e}")
            
            # 保存推荐页数据库
            rec_storage.write(rec_data)
            
            app_logger.info(f"数据库整理完成！")
            app_logger.info(f"主页 - 处理漫画总数: {total_comics}")
            app_logger.info(f"主页 - 下载封面数量: {downloaded_covers}")
            app_logger.info(f"主页 - 重新下载漫画数量: {re_downloaded_comics}")
            app_logger.info(f"推荐页 - 处理漫画总数: {total_recommendations}")
            app_logger.info(f"推荐页 - 下载封面数量: {rec_downloaded_covers}")
            
            return ServiceResult.ok({
                "home": {
                    "total_comics": total_comics,
                    "downloaded_covers": downloaded_covers,
                    "re_downloaded_comics": re_downloaded_comics
                },
                "recommendation": {
                    "total_comics": total_recommendations,
                    "downloaded_covers": rec_downloaded_covers
                }
            }, "数据库整理完成")
        except Exception as e:
            error_logger.error(f"整理数据库失败: {e}")
            return ServiceResult.error("整理数据库失败")
