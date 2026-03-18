from typing import List, Optional
import os
import shutil
from domain.comic import Comic, ComicRepository
from domain.recommendation import Recommendation, RecommendationRepository
from domain.tag import TagRepository
from infrastructure.persistence.repositories import RecommendationJsonRepository, TagJsonRepository, ComicJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.recommendation_cache_manager import recommendation_cache_manager
from core.utils import get_current_time, get_preview_pages, normalize_total_page
from core.platform import get_platform_from_id, get_original_id, Platform, get_platform_image_url
from core.constants import (
    JM_PICTURES_DIR,
    PK_PICTURES_DIR,
    JM_RECOMMENDATION_CACHE_DIR,
    PK_RECOMMENDATION_CACHE_DIR,
)
from core.runtime_profile import is_third_party_enabled, get_runtime_profile
from utils.file_parser import file_parser

FAVORITES_LIST_ID = "list_favorites_comic"


class RecommendationAppService:
    THIRD_PARTY_DISABLED_MESSAGE = "third-party integration is disabled in current runtime profile"
    """推荐漫画应用服务 - 与 ComicAppService 功能一致，但操作 Recommendation"""
    
    def __init__(
        self,
        recommendation_repo: RecommendationRepository = None,
        tag_repo: TagRepository = None,
        comic_repo: ComicRepository = None
    ):
        self._recommendation_repo = recommendation_repo or RecommendationJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._platform_service = None

    def _get_platform_service(self):
        if self._platform_service is not None:
            return self._platform_service

        if not is_third_party_enabled():
            raise RuntimeError(
                f"{self.THIRD_PARTY_DISABLED_MESSAGE}: {get_runtime_profile()}"
            )

        from third_party.platform_service import get_platform_service
        self._platform_service = get_platform_service()
        return self._platform_service
    
    def get_recommendation_list(
        self,
        sort_type: str = None,
        min_score: float = None,
        max_score: float = None
    ) -> ServiceResult:
        """获取推荐漫画列表 - 支持排序和评分筛选"""
        try:
            app_logger.info(f"[get_recommendation_list] sort_type={sort_type}, min_score={min_score}, max_score={max_score}")
            recommendations = self._recommendation_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 过滤掉已删除的漫画
            recommendations = [r for r in recommendations if not r.is_deleted]
            
            # 评分筛选
            if min_score is not None:
                recommendations = [r for r in recommendations if r.score is not None and r.score >= min_score]
            if max_score is not None:
                recommendations = [r for r in recommendations if r.score is not None and r.score <= max_score]
            
            app_logger.info(f"[get_recommendation_list] 排序前数量: {len(recommendations)}")
            
            # 排序
            if sort_type == "create_time":
                recommendations = sorted(recommendations, key=lambda r: r.create_time or "", reverse=True)
            elif sort_type == "score":
                recommendations = sorted(recommendations, key=lambda r: r.score or 0, reverse=True)
            elif sort_type == "read_time":
                recommendations = sorted(recommendations, key=lambda r: r.last_read_time or "", reverse=True)
            elif sort_type == "read_status":
                def read_status_sort_key(r):
                    is_read = r.current_page >= r.total_page if r.total_page > 0 else False
                    return (is_read, -(r.score or 0))
                recommendations = sorted(recommendations, key=read_status_sort_key)
            
            app_logger.info(f"[get_recommendation_list] 排序后数量: {len(recommendations)}")
            
            # 构建返回数据
            recommendation_list = []
            for r in recommendations:
                rec_info = {
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "desc": r.desc,
                    "cover_path": r.cover_path,  # 图床 URL
                    "total_page": normalize_total_page(r.total_page),
                    "current_page": r.current_page,
                    "score": r.score,
                    "tag_ids": r.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "last_read_time": r.last_read_time,
                    "create_time": r.create_time,
                    "list_ids": r.list_ids
                }
                recommendation_list.append(rec_info)
            
            app_logger.info(f"获取推荐列表成功，共 {len(recommendation_list)} 个")
            return ServiceResult.ok(recommendation_list)
        except Exception as e:
            error_logger.error(f"获取推荐列表失败: {e}")
            return ServiceResult.error("获取推荐列表失败")
    
    def get_recommendation_detail(self, recommendation_id: str) -> ServiceResult:
        """获取推荐漫画详情"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")

            normalized_total_page = normalize_total_page(recommendation.total_page)
            if normalized_total_page != recommendation.total_page:
                recommendation.total_page = normalized_total_page
                if normalized_total_page > 0:
                    recommendation.current_page = min(max(1, recommendation.current_page), normalized_total_page)
                self._recommendation_repo.save(recommendation)

            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}

            preview_pages = get_preview_pages(normalized_total_page)
            is_favorited = FAVORITES_LIST_ID in recommendation.list_ids

            cache_status = recommendation_cache_manager.get_cache_status(recommendation_id)
            is_cached = cache_status.get("is_cached", False)

            platform = get_platform_from_id(recommendation_id)
            original_id = get_original_id(recommendation_id)

            preview_image_urls = []
            if is_cached:
                for page in preview_pages:
                    image_url = f"/api/v1/recommendation/cache/image?recommendation_id={recommendation_id}&page_num={page}"
                    preview_image_urls.append(image_url)
            else:
                if platform == Platform.PK:
                    # 对于 PK 平台，优先使用预存预览图，缺失时动态补取。
                    preview_image_urls = recommendation.preview_image_urls or []
                    preview_pages = recommendation.preview_pages or preview_pages

                    if not preview_image_urls and preview_pages:
                        try:
                            platform_service = self._get_platform_service()
                            preview_image_urls = platform_service.get_preview_image_urls(
                                platform,
                                original_id,
                                preview_pages
                            )
                            if preview_image_urls:
                                recommendation.preview_image_urls = preview_image_urls
                                recommendation.preview_pages = preview_pages
                                self._recommendation_repo.save(recommendation)
                        except Exception as e:
                            error_logger.warning(f"获取 PK 预览图片失败: {recommendation_id}, {e}")
                else:
                    # 对于 JM 平台，使用原有逻辑
                    for page in preview_pages:
                        image_url = get_platform_image_url(platform, original_id, page)
                        if not image_url:
                            image_url = f"https://cdn-msp.jmapinodeudzn.net/media/photos/{original_id}/{page:05d}.webp"
                        if image_url:
                            preview_image_urls.append(image_url)

            detail = {
                "id": recommendation.id,
                "title": recommendation.title,
                "title_jp": recommendation.title_jp,
                "author": recommendation.author,
                "desc": recommendation.desc,
                "cover_path": recommendation.cover_path,
                "total_page": normalized_total_page,
                "current_page": recommendation.current_page,
                "score": recommendation.score,
                "tag_ids": recommendation.tag_ids,
                "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in recommendation.tag_ids],
                "list_ids": recommendation.list_ids,
                "preview_pages": preview_pages,
                "preview_image_urls": preview_image_urls,
                "is_cached": is_cached,
                "last_read_time": recommendation.last_read_time,
                "create_time": recommendation.create_time,
                "is_favorited": is_favorited,
                "source": "preview"
            }

            app_logger.info(f"获取推荐详情成功: {recommendation_id}, 平台: {platform}, 缓存状态: {is_cached}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取推荐详情失败: {e}")
            return ServiceResult.error("获取推荐详情失败")

    def update_progress(self, recommendation_id: str, current_page: int) -> ServiceResult:
        """更新阅读进度"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")

            total_page = normalize_total_page(recommendation.total_page)
            if total_page != recommendation.total_page:
                recommendation.total_page = total_page

            if total_page <= 0:
                return ServiceResult.error("页数信息无效，请先下载缓存后重试")

            if not (1 <= current_page <= total_page):
                return ServiceResult.error(f"页码超出范围: 1-{total_page}")

            recommendation.current_page = current_page
            recommendation.last_read_time = get_current_time()

            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"更新阅读进度成功: {recommendation_id}, 第{current_page}页")
                return ServiceResult.ok({"current_page": current_page})
            else:
                return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"更新阅读进度失败: {e}")
            return ServiceResult.error("更新阅读进度失败")

    def update_total_page(self, recommendation_id: str, total_page: int) -> ServiceResult:
        """更新推荐漫画总页数"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")

            fallback_total = normalize_total_page(recommendation.total_page)
            normalized_total = normalize_total_page(total_page, default=fallback_total)
            if normalized_total <= 0:
                return ServiceResult.error("总页数无效")

            recommendation.total_page = normalized_total
            recommendation.current_page = min(max(1, recommendation.current_page), normalized_total)

            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"更新推荐总页数成功: {recommendation_id}, total_page={normalized_total}")
                return ServiceResult.ok({"id": recommendation_id, "total_page": normalized_total})
            return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"更新推荐总页数失败: {e}")
            return ServiceResult.error("更新推荐总页数失败")

    def _get_local_comic_dir(self, recommendation: Recommendation) -> Optional[str]:
        platform = get_platform_from_id(recommendation.id)
        if platform not in (Platform.JM, Platform.PK):
            return None

        base_dir = JM_PICTURES_DIR if platform == Platform.JM else PK_PICTURES_DIR
        original_id = get_original_id(recommendation.id)
        try:
            platform_service = self._get_platform_service()
        except RuntimeError:
            return None

        return platform_service.get_comic_dir(
            platform,
            original_id,
            recommendation.author or None,
            recommendation.title or None,
            base_dir=base_dir
        )

    def _get_local_total_page(self, comic_id: str) -> int:
        image_paths = file_parser.parse_comic_images(comic_id)
        return len(image_paths)

    def _migrate_cached_content_to_local(self, recommendation: Recommendation) -> dict:
        cache_dir = recommendation_cache_manager.get_cache_dir(recommendation.id)
        if not cache_dir:
            return {"success": False, "reason": "cache_not_found"}

        platform = get_platform_from_id(recommendation.id)
        local_dir = None
        try:
            if platform == Platform.JM:
                relative_path = os.path.relpath(cache_dir, JM_RECOMMENDATION_CACHE_DIR)
                local_dir = os.path.join(JM_PICTURES_DIR, relative_path)
            elif platform == Platform.PK:
                relative_path = os.path.relpath(cache_dir, PK_RECOMMENDATION_CACHE_DIR)
                local_dir = os.path.join(PK_PICTURES_DIR, relative_path)
        except Exception:
            local_dir = None

        if not local_dir:
            local_dir = self._get_local_comic_dir(recommendation)
        if not local_dir:
            return {"success": False, "reason": "unsupported_platform"}

        os.makedirs(os.path.dirname(local_dir), exist_ok=True)
        shutil.copytree(cache_dir, local_dir, dirs_exist_ok=True)

        total_page = self._get_local_total_page(recommendation.id)
        if total_page <= 0:
            total_page = len(recommendation_cache_manager.get_cached_pages(recommendation.id))

        return {
            "success": total_page > 0,
            "source": "cache",
            "total_page": total_page
        }

    def _download_content_to_local(self, recommendation: Recommendation) -> dict:
        platform = get_platform_from_id(recommendation.id)
        if platform not in (Platform.JM, Platform.PK):
            return {"success": False, "reason": "unsupported_platform"}

        original_id = get_original_id(recommendation.id)
        download_dir = JM_PICTURES_DIR if platform == Platform.JM else PK_PICTURES_DIR
        download_kwargs = {"decode_images": True} if platform == Platform.JM else {}

        try:
            platform_service = self._get_platform_service()
        except RuntimeError:
            return {"success": False, "reason": "third_party_disabled"}

        detail, success = platform_service.download_album(
            platform,
            original_id,
            download_dir=download_dir,
            show_progress=False,
            **download_kwargs
        )
        if not success:
            return {"success": False, "reason": "download_failed"}

        total_page = normalize_total_page(
            detail.get("local_pages", detail.get("pages_count", 0)),
            default=0
        )
        if total_page <= 0:
            total_page = self._get_local_total_page(recommendation.id)

        return {
            "success": total_page > 0,
            "source": "download",
            "total_page": total_page
        }

    def migrate_to_local(self, recommendation_ids: List[str]) -> ServiceResult:
        """Migrate preview recommendations into local comic library."""
        try:
            if not recommendation_ids:
                return ServiceResult.error("recommendation_ids is required")

            imported_count = 0
            skipped_count = 0
            failed_count = 0
            imported_ids = []
            skipped_ids = []
            failed_items = []

            for recommendation_id in recommendation_ids:
                try:
                    recommendation = self._recommendation_repo.get_by_id(recommendation_id)
                    if not recommendation or recommendation.is_deleted:
                        skipped_count += 1
                        skipped_ids.append(recommendation_id)
                        continue

                    if self._comic_repo.get_by_id(recommendation_id):
                        skipped_count += 1
                        skipped_ids.append(recommendation_id)
                        continue

                    if recommendation_cache_manager.is_cached(recommendation_id):
                        content_result = self._migrate_cached_content_to_local(recommendation)
                    else:
                        content_result = self._download_content_to_local(recommendation)

                    if not content_result.get("success"):
                        failed_count += 1
                        failed_items.append({
                            "id": recommendation_id,
                            "reason": content_result.get("reason", "content_migrate_failed")
                        })
                        continue

                    total_page = normalize_total_page(
                        content_result.get("total_page", 0),
                        default=normalize_total_page(recommendation.total_page, default=0)
                    )
                    if total_page <= 0:
                        total_page = 1

                    current_page = normalize_total_page(recommendation.current_page, default=1)
                    current_page = min(max(1, current_page), total_page)

                    create_time = recommendation.create_time or get_current_time()
                    last_read_time = recommendation.last_read_time or create_time

                    local_comic = Comic(
                        id=recommendation.id,
                        title=recommendation.title or "",
                        title_jp=recommendation.title_jp or "",
                        creator=recommendation.author or "",
                        desc=recommendation.desc or "",
                        cover_path=recommendation.cover_path or "",
                        total_units=total_page,
                        current_unit=current_page,
                        score=recommendation.score,
                        tag_ids=list(recommendation.tag_ids or []),
                        list_ids=list(recommendation.list_ids or []),
                        create_time=create_time,
                        last_access_time=last_read_time,
                        is_deleted=False
                    )

                    if not self._comic_repo.save(local_comic):
                        failed_count += 1
                        failed_items.append({
                            "id": recommendation_id,
                            "reason": "save_local_failed"
                        })
                        continue

                    imported_count += 1
                    imported_ids.append(recommendation_id)
                except Exception as item_error:
                    failed_count += 1
                    failed_items.append({
                        "id": recommendation_id,
                        "reason": str(item_error)
                    })
                    error_logger.error(f"migrate recommendation failed: {recommendation_id}, {item_error}")

            app_logger.info(
                f"migrate recommendations to local finished: imported={imported_count}, "
                f"skipped={skipped_count}, failed={failed_count}"
            )
            return ServiceResult.ok(
                {
                    "imported_count": imported_count,
                    "skipped_count": skipped_count,
                    "failed_count": failed_count,
                    "imported_ids": imported_ids,
                    "skipped_ids": skipped_ids,
                    "failed_items": failed_items
                },
                f"导入完成：成功 {imported_count}，跳过 {skipped_count}，失败 {failed_count}"
            )
        except Exception as e:
            error_logger.error(f"migrate recommendations to local failed: {e}")
            return ServiceResult.error("导入本地库失败")

    def update_score(self, recommendation_id: str, score: float) -> ServiceResult:
        """更新评分"""
        try:
            from core.constants import MIN_SCORE, MAX_SCORE, SCORE_PRECISION
            
            if not (MIN_SCORE <= score <= MAX_SCORE):
                return ServiceResult.error(f"评分必须在 {MIN_SCORE}-{MAX_SCORE} 之间")
            
            # 检查评分精度
            if score % SCORE_PRECISION != 0:
                return ServiceResult.error(f"评分必须是 {SCORE_PRECISION} 的倍数")
            
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")
            
            recommendation.score = score
            
            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"更新评分成功: {recommendation_id}, 评分: {score}")
                return ServiceResult.ok({"score": score})
            else:
                return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"更新评分失败: {e}")
            return ServiceResult.error("更新评分失败")
    
    def bind_tags(self, recommendation_id: str, tag_id_list: List[str]) -> ServiceResult:
        """绑定标签"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")
            
            recommendation.tag_ids = tag_id_list
            
            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"绑定标签成功: {recommendation_id}, 标签: {tag_id_list}")
                return ServiceResult.ok({"tag_ids": tag_id_list})
            else:
                return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"绑定标签失败: {e}")
            return ServiceResult.error("绑定标签失败")
    
    def update_meta(self, recommendation_id: str, meta: dict) -> ServiceResult:
        """更新元数据"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")
            
            if "title" in meta:
                recommendation.title = meta["title"]
            if "author" in meta:
                recommendation.author = meta["author"]
            if "desc" in meta:
                recommendation.desc = meta["desc"]
            if "cover_path" in meta:
                recommendation.cover_path = meta["cover_path"]
            
            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"更新元数据成功: {recommendation_id}")
                return ServiceResult.ok({"id": recommendation_id})
            else:
                return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"更新元数据失败: {e}")
            return ServiceResult.error("更新元数据失败")
    
    def search(self, keyword: str) -> ServiceResult:
        """搜索"""
        try:
            results = self._recommendation_repo.search(keyword)
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            recommendation_list = []
            for r in results:
                recommendation_list.append({
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": normalize_total_page(r.total_page),
                    "current_page": r.current_page,
                    "score": r.score,
                    "tag_ids": r.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "list_ids": r.list_ids
                })
            
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(recommendation_list)}")
            return ServiceResult.ok(recommendation_list)
        except Exception as e:
            error_logger.error(f"搜索失败: {e}")
            return ServiceResult.error("搜索失败")
    
    def filter_by_tags(self, include_tag_ids: List[str], exclude_tag_ids: List[str]) -> ServiceResult:
        """根据标签筛选"""
        try:
            results = self._recommendation_repo.filter_by_tags(include_tag_ids, exclude_tag_ids)
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            recommendation_list = []
            for r in results:
                recommendation_list.append({
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": normalize_total_page(r.total_page),
                    "current_page": r.current_page,
                    "score": r.score,
                    "tag_ids": r.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "list_ids": r.list_ids
                })
            
            app_logger.info(f"筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}, 结果数量: {len(recommendation_list)}")
            return ServiceResult.ok(recommendation_list)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def filter_multi(self, include_tags: List[str] = None, exclude_tags: List[str] = None,
                     authors: List[str] = None, list_ids: List[str] = None) -> ServiceResult:
        """多条件筛选：标签、作者、清单"""
        try:
            results = self._recommendation_repo.filter_multi(include_tags, exclude_tags, authors, list_ids)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            recommendation_list = []
            for r in results:
                recommendation_list.append({
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": normalize_total_page(r.total_page),
                    "current_page": r.current_page,
                    "score": r.score,
                    "tag_ids": r.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "last_read_time": r.last_read_time,
                    "create_time": r.create_time,
                    "list_ids": r.list_ids
                })
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(recommendation_list)}")
            return ServiceResult.ok(recommendation_list)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def batch_add_tags(self, recommendation_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        """批量添加标签"""
        try:
            success_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    for tag_id in tag_ids:
                        if tag_id not in recommendation.tag_ids:
                            recommendation.tag_ids.append(tag_id)
                    if self._recommendation_repo.save(recommendation):
                        success_count += 1
            
            app_logger.info(f"批量添加标签成功: {success_count}个推荐漫画")
            return ServiceResult.ok({"success_count": success_count})
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, recommendation_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        """批量移除标签"""
        try:
            success_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    for tag_id in tag_ids:
                        if tag_id in recommendation.tag_ids:
                            recommendation.tag_ids.remove(tag_id)
                    if self._recommendation_repo.save(recommendation):
                        success_count += 1
            
            app_logger.info(f"批量移除标签成功: {success_count}个推荐漫画")
            return ServiceResult.ok({"success_count": success_count})
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
    
    def add_recommendation(self, data: dict) -> ServiceResult:
        """添加新的推荐漫画"""
        try:
            from core.utils import generate_id
            
            recommendation_id = data.get("id") or generate_id("rec_")
            
            # 检查是否已存在
            existing = self._recommendation_repo.get_by_id(recommendation_id)
            if existing:
                return ServiceResult.error("推荐漫画已存在")
            
            recommendation = Recommendation(
                id=recommendation_id,
                title=data.get("title", ""),
                title_jp=data.get("title_jp", ""),
                author=data.get("author", ""),
                desc=data.get("desc", ""),
                cover_path=data.get("cover_path", ""),  # 图床 URL
                total_page=normalize_total_page(data.get("total_page", 0)),
                current_page=data.get("current_page", 1),
                score=data.get("score", 8.0),
                tag_ids=data.get("tag_ids", []),
                list_ids=data.get("list_ids", []),
                create_time=get_current_time(),
                last_read_time=get_current_time(),
                preview_image_urls=data.get("preview_image_urls", []),
                preview_pages=data.get("preview_pages", [])
            )
            
            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"添加推荐漫画成功: {recommendation_id}")
                return ServiceResult.ok({"id": recommendation_id})
            else:
                return ServiceResult.error("保存失败")
        except Exception as e:
            error_logger.error(f"添加推荐漫画失败: {e}")
            return ServiceResult.error("添加推荐漫画失败")
    
    def delete_recommendation(self, recommendation_id: str) -> ServiceResult:
        """删除推荐漫画"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")
            
            if self._recommendation_repo.delete(recommendation_id):
                app_logger.info(f"删除推荐漫画成功: {recommendation_id}")
                return ServiceResult.ok({"id": recommendation_id})
            else:
                return ServiceResult.error("删除失败")
        except Exception as e:
            error_logger.error(f"删除推荐漫画失败: {e}")
            return ServiceResult.error("删除推荐漫画失败")
    
    def get_trash_list(self) -> ServiceResult:
        """获取回收站漫画列表"""
        try:
            recommendations = self._recommendation_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 只获取已删除的漫画
            trash_list = [r for r in recommendations if r.is_deleted]
            
            result = []
            for r in trash_list:
                result.append({
                    "id": r.id,
                    "title": r.title,
                    "author": r.author,
                    "cover_path": r.cover_path,
                    "total_page": normalize_total_page(r.total_page),
                    "score": r.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in r.tag_ids],
                    "create_time": r.create_time
                })
            
            app_logger.info(f"获取回收站列表成功，共 {len(result)} 个漫画")
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取回收站列表失败: {e}")
            return ServiceResult.error("获取回收站列表失败")
    
    def move_to_trash(self, recommendation_id: str) -> ServiceResult:
        """移动漫画到回收站"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("漫画不存在")
            
            recommendation.move_to_trash()
            
            if not self._recommendation_repo.save(recommendation):
                return ServiceResult.error("移入回收站失败")
            
            app_logger.info(f"漫画移入回收站: {recommendation_id}")
            return ServiceResult.ok({"id": recommendation_id}, "已移入回收站")
        except Exception as e:
            error_logger.error(f"移入回收站失败: {e}")
            return ServiceResult.error("移入回收站失败")
    
    def restore_from_trash(self, recommendation_id: str) -> ServiceResult:
        """从回收站恢复漫画"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("漫画不存在")
            
            recommendation.restore_from_trash()
            
            if not self._recommendation_repo.save(recommendation):
                return ServiceResult.error("恢复失败")
            
            app_logger.info(f"漫画从回收站恢复: {recommendation_id}")
            return ServiceResult.ok({"id": recommendation_id}, "已从回收站恢复")
        except Exception as e:
            error_logger.error(f"从回收站恢复失败: {e}")
            return ServiceResult.error("从回收站恢复失败")
    
    def batch_move_to_trash(self, recommendation_ids: List[str]) -> ServiceResult:
        """批量移动漫画到回收站"""
        try:
            updated_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    recommendation.move_to_trash()
                    if self._recommendation_repo.save(recommendation):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移入回收站成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已将{updated_count}个漫画移入回收站")
        except Exception as e:
            error_logger.error(f"批量移入回收站失败: {e}")
            return ServiceResult.error("批量移入回收站失败")
    
    def batch_restore_from_trash(self, recommendation_ids: List[str]) -> ServiceResult:
        """批量从回收站恢复漫画"""
        try:
            updated_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    recommendation.restore_from_trash()
                    if self._recommendation_repo.save(recommendation):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量从回收站恢复成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已恢复{updated_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量从回收站恢复失败: {e}")
            return ServiceResult.error("批量从回收站恢复失败")
    
    def delete_permanently(self, recommendation_id: str) -> ServiceResult:
        """永久删除漫画"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("漫画不存在")
            
            self._cleanup_recommendation_files(recommendation)
            
            if not self._recommendation_repo.delete(recommendation_id):
                return ServiceResult.error("永久删除失败")
            
            app_logger.info(f"漫画已永久删除: {recommendation_id}")
            return ServiceResult.ok({"id": recommendation_id}, "已永久删除")
        except Exception as e:
            error_logger.error(f"永久删除失败: {e}")
            return ServiceResult.error("永久删除失败")
    
    def _cleanup_recommendation_files(self, recommendation):
        """清理推荐漫画相关的缓存文件"""
        import shutil
        from core.constants import JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR
        
        platform = get_platform_from_id(recommendation.id)
        original_id = get_original_id(recommendation.id)
        
        cache_dir = None
        if platform == Platform.JM:
            cache_dir = os.path.join(JM_RECOMMENDATION_CACHE_DIR, original_id)
        elif platform == Platform.PK:
            cache_dir = os.path.join(PK_RECOMMENDATION_CACHE_DIR, original_id)
        
        if cache_dir and os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                app_logger.info(f"已删除推荐漫画缓存目录: {cache_dir}")
            except Exception as e:
                error_logger.error(f"删除推荐漫画缓存目录失败: {e}")
    
    def batch_delete_permanently(self, recommendation_ids: List[str]) -> ServiceResult:
        """批量永久删除漫画"""
        try:
            deleted_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    self._cleanup_recommendation_files(recommendation)
                if self._recommendation_repo.delete(rec_id):
                    deleted_count += 1
            
            if deleted_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量永久删除成功: {deleted_count}个漫画")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"已永久删除{deleted_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量永久删除失败: {e}")
            return ServiceResult.error("批量永久删除失败")
