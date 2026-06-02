from typing import Any, Dict, List, Optional
import os
import re
import shutil
from application.content_sorting import (
    normalize_custom_order_records,
    sort_content_items,
)
from application.persisted_content_metadata import (
    build_persisted_annotation,
    normalize_data_relative_path,
)
from domain.comic import Comic, ComicRepository
from domain.recommendation import Recommendation, RecommendationRepository
from domain.tag import TagRepository
from infrastructure.persistence.repositories import RecommendationJsonRepository, TagJsonRepository, ComicJsonRepository
from infrastructure.persistence.repositories.document_repository import JsonDocumentRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.recommendation_cache_manager import recommendation_cache_manager
from core.utils import get_current_time, get_preview_pages, normalize_total_page
from core.constants import COMIC_DIR, COMIC_RECOMMENDATION_CACHE_DIR, RECOMMENDATION_JSON_FILE
from core.runtime_profile import is_third_party_enabled, get_runtime_profile
from utils.file_parser import file_parser
from core.enums import ContentType
from application.tag_content_type_guard import validate_tag_ids_for_content_type
from protocol.platform_meta import (
    build_platform_root_dir,
    get_capability_default_params,
    split_prefixed_id,
)

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
        self._recommendation_document_repo = JsonDocumentRepository(
            RECOMMENDATION_JSON_FILE,
            "recommendations",
            "total_recommendations",
        )

    @staticmethod
    def _recommendation_to_summary_dict(recommendation: Recommendation, tag_map: Dict[str, str]) -> Dict[str, Any]:
        payload = recommendation.to_dict() if hasattr(recommendation, "to_dict") else {}
        payload["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in recommendation.tag_ids]
        return payload

    def _build_recommendation_persisted_metadata(
        self,
        recommendation_payload: Dict[str, Any],
        *,
        storage_path: str = "",
        storage_kind: str = "",
        platform_name: str = "",
        plugin_id: str = "",
    ) -> Dict[str, Any]:
        persisted = build_persisted_annotation(
            recommendation_payload,
            media_type="comic",
            plugin_id=plugin_id or None,
            platform_name=platform_name or None,
        )
        if storage_path:
            relative_path = normalize_data_relative_path(storage_path)
            if relative_path:
                persisted["storage_path_relative"] = relative_path
        if storage_kind:
            persisted["storage_path_kind"] = storage_kind
        return persisted

    def _get_platform_service(self):
        if self._platform_service is not None:
            return self._platform_service

        if not is_third_party_enabled():
            raise RuntimeError(
                f"{self.THIRD_PARTY_DISABLED_MESSAGE}: {get_runtime_profile()}"
            )

        from protocol.platform_service import get_platform_service
        self._platform_service = get_platform_service()
        return self._platform_service

    def _refresh_recommendation_persisted_metadata(self, recommendation: Any) -> bool:
        if not recommendation:
            return False

        payload = recommendation.to_dict() if hasattr(recommendation, "to_dict") else dict(recommendation or {})
        recommendation_id = str(payload.get("id") or "").strip()
        if not recommendation_id:
            return False

        platform_name = str(payload.get("platform") or "").strip()
        plugin_id = str(payload.get("plugin_id") or "").strip()
        storage_kind = str(payload.get("storage_path_kind") or "").strip() or "preview_cache_dir"

        try:
            storage_path = recommendation_cache_manager._get_comic_cache_dir(recommendation_id)
        except Exception:
            storage_path = ""

        updates = self._build_recommendation_persisted_metadata(
            payload,
            storage_path=storage_path,
            storage_kind=storage_kind,
            platform_name=platform_name,
            plugin_id=plugin_id,
        )
        changed = False
        for key, value in updates.items():
            if hasattr(recommendation, key):
                if getattr(recommendation, key, None) != value:
                    setattr(recommendation, key, value)
                    changed = True
            elif isinstance(recommendation, dict):
                if recommendation.get(key) != value:
                    recommendation[key] = value
                    changed = True
        return changed

    @staticmethod
    def _commit_custom_order(document_repo: JsonDocumentRepository, ordered_ids: List[str] = None) -> bool:
        changed = False
        processed = False

        def update_items(items: List[Dict[str, Any]]):
            nonlocal changed, processed
            normalized_items, did_change = normalize_custom_order_records(items, ordered_ids)
            changed = did_change
            processed = True
            return normalized_items if did_change else None

        updated = document_repo.update_items(update_items)
        if updated:
            return True
        return processed and not changed
    
    def get_recommendation_list(
        self,
        sort_type: str = None,
        sort_order: str = "desc",
        min_score: float = None,
        max_score: float = None
    ) -> ServiceResult:
        """获取推荐漫画列表 - 支持排序和评分筛选"""
        try:
            app_logger.info(f"[get_recommendation_list] sort_type={sort_type}, sort_order={sort_order}, min_score={min_score}, max_score={max_score}")
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
            if sort_type:
                if str(sort_type or "").strip().lower() == "custom":
                    self._commit_custom_order(self._recommendation_document_repo)
                recommendations = sort_content_items(recommendations, sort_type, sort_order)
            
            app_logger.info(f"[get_recommendation_list] 排序后数量: {len(recommendations)}")
            
            # 构建返回数据
            recommendation_list = []
            for r in recommendations:
                rec_info = self._recommendation_to_summary_dict(r, tag_map)
                rec_info["total_page"] = normalize_total_page(r.total_page)
                recommendation_list.append(rec_info)
            
            app_logger.info(f"获取推荐列表成功，共 {len(recommendation_list)} 个")
            return ServiceResult.ok(recommendation_list)
        except Exception as e:
            error_logger.error(f"获取推荐列表失败: {e}")
            return ServiceResult.error("获取推荐列表失败")

    def update_custom_order(self, recommendation_ids: List[str]) -> ServiceResult:
        try:
            normalized_ids = [
                str(recommendation_id or "").strip()
                for recommendation_id in (recommendation_ids or [])
                if str(recommendation_id or "").strip()
            ]
            if not normalized_ids:
                return ServiceResult.error("缺少参数: recommendation_ids")

            if not self._commit_custom_order(self._recommendation_document_repo, normalized_ids):
                return ServiceResult.error("保存自定义排序失败")

            return ServiceResult.ok({"updated_count": len(normalized_ids)}, "自定义排序已保存")
        except Exception as e:
            error_logger.error(f"保存推荐漫画自定义排序失败: {e}")
            return ServiceResult.error("保存自定义排序失败")
    
    def get_recommendation_detail(self, recommendation_id: str) -> ServiceResult:
        """获取推荐漫画详情"""
        try:
            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")

            try:
                if (not str(getattr(recommendation, "storage_path_relative", "") or "").strip()) or (not str(getattr(recommendation, "storage_path_kind", "") or "").strip()):
                    if self._refresh_recommendation_persisted_metadata(recommendation):
                        self._recommendation_repo.save(recommendation)
            except Exception as persisted_error:
                error_logger.error(f"回填推荐漫画存储路径失败（详情）: {recommendation_id}, {persisted_error}")

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

            platform_key, original_id, manifest = split_prefixed_id(recommendation_id, media_type="comic")

            preview_image_urls = []
            if is_cached:
                for page in preview_pages:
                    image_url = f"/api/v1/recommendation/cache/image?recommendation_id={recommendation_id}&page_num={page}"
                    preview_image_urls.append(image_url)
            else:
                preview_image_urls = recommendation.preview_image_urls or []
                preview_pages = recommendation.preview_pages or preview_pages

                if not preview_image_urls and preview_pages and platform_key:
                    try:
                        platform_service = self._get_platform_service()
                        preview_image_urls = platform_service.get_preview_image_urls(
                            platform_key,
                            original_id,
                            preview_pages
                        )
                        if preview_image_urls:
                            recommendation.preview_image_urls = preview_image_urls
                            recommendation.preview_pages = preview_pages
                            self._recommendation_repo.save(recommendation)
                    except Exception as e:
                        error_logger.warning(f"获取协议预览图片失败: {recommendation_id}, {e}")

            detail = recommendation.to_dict()
            detail["total_page"] = normalized_total_page
            detail["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in recommendation.tag_ids]
            detail["preview_pages"] = preview_pages
            detail["preview_image_urls"] = preview_image_urls
            detail["is_cached"] = is_cached
            detail["is_favorited"] = is_favorited
            detail["source"] = "preview"

            app_logger.info(f"获取推荐详情成功: {recommendation_id}, 平台: {platform_key}, 缓存状态: {is_cached}")
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
        platform_key, original_id, manifest = split_prefixed_id(recommendation.id, media_type="comic")
        if not platform_key or not original_id:
            return None

        base_dir = build_platform_root_dir(COMIC_DIR, manifest=manifest, platform_name=platform_key)
        try:
            platform_service = self._get_platform_service()
        except RuntimeError:
            return None

        return platform_service.get_comic_dir(
            platform_key,
            original_id,
            recommendation.author or None,
            recommendation.title or None,
            base_dir=base_dir
        )

    def _get_local_total_page(self, comic_id: str) -> int:
        image_paths = file_parser.parse_comic_images(comic_id)
        return len(image_paths)

    @staticmethod
    def _get_teledrive_comic_payload(recommendation: Recommendation) -> Dict[str, Any]:
        display = getattr(recommendation, "display", {}) if recommendation else {}
        if not isinstance(display, dict):
            return {}
        teledrive = display.get("teledrive")
        if not isinstance(teledrive, dict):
            return {}
        if str(teledrive.get("type") or "").strip().lower() != "comic":
            return {}
        pages = teledrive.get("pages")
        if not isinstance(pages, list) or not pages:
            return {}
        return teledrive

    @classmethod
    def _is_teledrive_recommendation(cls, recommendation: Recommendation) -> bool:
        return bool(cls._get_teledrive_comic_payload(recommendation))

    @staticmethod
    def _sanitize_local_fs_name(name: str, fallback: str = "item") -> str:
        normalized = re.sub(r'[\\/:*?"<>|\x00-\x1F]+', "_", str(name or "").strip())
        normalized = re.sub(r"\s+", " ", normalized).rstrip(" .")
        if not normalized:
            normalized = fallback
        reserved = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }
        if normalized.upper() in reserved:
            normalized = f"{normalized}_"
        return normalized[:180]

    @classmethod
    def _safe_teledrive_relative_path(cls, raw_path: str, fallback_name: str) -> str:
        raw = str(raw_path or "").replace("\\", "/").strip("/")
        parts = [
            cls._sanitize_local_fs_name(part, fallback="part")
            for part in raw.split("/")
            if part and part not in {".", ".."}
        ]
        if not parts:
            parts = [cls._sanitize_local_fs_name(fallback_name, fallback="page.jpg")]
        return os.path.join(*parts)

    @classmethod
    def _build_teledrive_local_comic_dir(
        cls,
        recommendation: Recommendation,
        teledrive: Dict[str, Any],
    ) -> str:
        folder_id = str(teledrive.get("folder_id") or recommendation.id or "").strip()
        suffix = cls._sanitize_local_fs_name(folder_id, fallback="folder")[:12]
        label = (
            str(teledrive.get("work_id") or "").strip()
            or str(recommendation.title or "").strip()
            or str(recommendation.id or "").strip()
        )
        dir_name = cls._sanitize_local_fs_name(label, fallback="comic")
        if suffix and suffix.lower() not in dir_name.lower():
            dir_name = f"{dir_name}__{suffix}"

        base_dir = os.path.join(COMIC_DIR, "TeleDrive")
        candidate = os.path.abspath(os.path.join(base_dir, dir_name))
        if not os.path.exists(candidate):
            return candidate

        for index in range(2, 10_000):
            next_candidate = os.path.abspath(os.path.join(base_dir, f"{dir_name}__{index}"))
            if not os.path.exists(next_candidate):
                return next_candidate
        raise RuntimeError(f"failed to allocate TeleDrive comic directory: {candidate}")

    @staticmethod
    def _build_local_teledrive_origin_display(display: Dict[str, Any]) -> Dict[str, Any]:
        local_display = dict(display or {})
        teledrive = local_display.pop("teledrive", None)
        if isinstance(teledrive, dict):
            origin = {
                key: teledrive.get(key)
                for key in ("type", "root", "path", "folder_id", "work_id", "platform_segment")
                if teledrive.get(key) not in (None, "", [], {})
            }
            origin["page_count"] = len(teledrive.get("pages") or [])
            local_display["teledrive_origin"] = origin
        return local_display

    def _migrate_teledrive_content_to_local(self, recommendation: Recommendation) -> dict:
        teledrive = self._get_teledrive_comic_payload(recommendation)
        if not teledrive:
            return {"success": False, "reason": "not_teledrive"}

        local_dir = self._build_teledrive_local_comic_dir(recommendation, teledrive)
        pages = [dict(page or {}) for page in (teledrive.get("pages") or []) if isinstance(page, dict)]
        if not pages:
            return {"success": False, "reason": "teledrive_pages_empty"}

        from application.teledrive_app_service import get_teledrive_app_service

        downloader = get_teledrive_app_service()
        tmp_dir = f"{local_dir}.tmp"
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        downloaded = 0
        try:
            for index, page in enumerate(pages, start=1):
                file_id = str(page.get("file_id") or "").strip()
                if not file_id:
                    raise RuntimeError(f"TeleDrive page has no file id: index={index}")
                page_name = str(page.get("name") or "").strip() or f"{index:05d}.jpg"
                relative = self._safe_teledrive_relative_path(
                    str(page.get("relative_path") or page_name),
                    page_name,
                )
                target_path = os.path.abspath(os.path.join(tmp_dir, relative))
                tmp_root = os.path.abspath(tmp_dir)
                try:
                    if os.path.commonpath([tmp_root, target_path]) != tmp_root:
                        raise RuntimeError("invalid TeleDrive page path")
                except Exception as exc:
                    raise RuntimeError("invalid TeleDrive page path") from exc

                if os.path.exists(target_path):
                    stem, ext = os.path.splitext(target_path)
                    target_path = f"{stem}__{index}{ext or '.jpg'}"

                downloader.download_file_to_path(file_id, target_path, name=page_name)
                downloaded += 1

            if os.path.isdir(local_dir):
                shutil.rmtree(local_dir, ignore_errors=True)
            os.makedirs(os.path.dirname(local_dir), exist_ok=True)
            shutil.move(tmp_dir, local_dir)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        return {
            "success": downloaded > 0,
            "source": "teledrive",
            "total_page": downloaded,
            "local_dir": local_dir,
            "cover_path": f"/api/v1/comic/image?comic_id={recommendation.id}&page_num=1",
            "display": self._build_local_teledrive_origin_display(getattr(recommendation, "display", {}) or {}),
        }

    def _migrate_cached_content_to_local(self, recommendation: Recommendation) -> dict:
        cache_dir = recommendation_cache_manager.get_cache_dir(recommendation.id)
        if not cache_dir:
            return {"success": False, "reason": "cache_not_found"}

        platform_key, _original_id, manifest = split_prefixed_id(recommendation.id, media_type="comic")
        if not platform_key:
            return {"success": False, "reason": "unsupported_platform"}

        local_dir = None
        try:
            cache_root_dir = build_platform_root_dir(
                COMIC_RECOMMENDATION_CACHE_DIR,
                manifest=manifest,
                platform_name=platform_key,
            )
            local_root_dir = build_platform_root_dir(
                COMIC_DIR,
                manifest=manifest,
                platform_name=platform_key,
            )
            relative_path = os.path.relpath(cache_dir, cache_root_dir)
            if not str(relative_path or "").startswith(".."):
                local_dir = os.path.join(local_root_dir, relative_path)
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
        platform_key, original_id, manifest = split_prefixed_id(recommendation.id, media_type="comic")
        if not platform_key or not original_id:
            return {"success": False, "reason": "unsupported_platform"}

        download_dir = build_platform_root_dir(COMIC_DIR, manifest=manifest, platform_name=platform_key)
        download_kwargs = get_capability_default_params(manifest, "asset.bundle.fetch")

        try:
            platform_service = self._get_platform_service()
        except RuntimeError:
            return {"success": False, "reason": "third_party_disabled"}

        detail, success = platform_service.download_album(
            platform_key,
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

                    if self._is_teledrive_recommendation(recommendation):
                        content_result = self._migrate_teledrive_content_to_local(recommendation)
                    elif recommendation_cache_manager.is_cached(recommendation_id):
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

                    local_display = dict(getattr(recommendation, "display", {}) or {})
                    if content_result.get("display") is not None:
                        local_display = dict(content_result.get("display") or {})

                    local_comic = Comic(
                        id=recommendation.id,
                        title=recommendation.title or "",
                        title_jp=recommendation.title_jp or "",
                        creator=recommendation.author or "",
                        desc=recommendation.desc or "",
                        cover_path=content_result.get("cover_path") or recommendation.cover_path or "",
                        total_units=total_page,
                        current_unit=current_page,
                        score=recommendation.score,
                        tag_ids=list(recommendation.tag_ids or []),
                        list_ids=list(recommendation.list_ids or []),
                        create_time=create_time,
                        last_access_time=last_read_time,
                        is_deleted=False,
                        platform=recommendation.platform or "",
                        plugin_id=getattr(recommendation, "plugin_id", "") or "",
                        plugin_name=getattr(recommendation, "plugin_name", "") or "",
                        display=local_display,
                    )

                    local_dir = str(content_result.get("local_dir") or "").strip() or self._get_local_comic_dir(recommendation)
                    platform_key, _original_id, _manifest = split_prefixed_id(recommendation.id, media_type="comic")
                    persisted_updates = self._build_recommendation_persisted_metadata(
                        local_comic.to_dict(),
                        storage_path=local_dir or "",
                        storage_kind="local_dir" if local_dir else "",
                        platform_name=recommendation.platform or platform_key,
                        plugin_id=getattr(recommendation, "plugin_id", "") or "",
                    )
                    for key, value in persisted_updates.items():
                        setattr(local_comic, key, value)

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
            validated_tag_ids, validation_error = validate_tag_ids_for_content_type(
                self._tag_repo,
                tag_id_list,
                ContentType.COMIC,
            )
            if validation_error:
                return ServiceResult.error(validation_error)

            recommendation = self._recommendation_repo.get_by_id(recommendation_id)
            if not recommendation:
                return ServiceResult.error("推荐漫画不存在")
            
            recommendation.tag_ids = validated_tag_ids
            
            if self._recommendation_repo.save(recommendation):
                app_logger.info(f"绑定标签成功: {recommendation_id}, 标签: {validated_tag_ids}")
                return ServiceResult.ok({"tag_ids": validated_tag_ids})
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
            validated_tag_ids, validation_error = validate_tag_ids_for_content_type(
                self._tag_repo,
                tag_ids,
                ContentType.COMIC,
            )
            if validation_error:
                return ServiceResult.error(validation_error)

            success_count = 0
            for rec_id in recommendation_ids:
                recommendation = self._recommendation_repo.get_by_id(rec_id)
                if recommendation:
                    for tag_id in validated_tag_ids:
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
                preview_pages=data.get("preview_pages", []),
                platform=data.get("platform", ""),
                plugin_id=data.get("plugin_id", ""),
                plugin_name=data.get("plugin_name", ""),
                display=dict(data.get("display") or {}),
                storage_path_relative=data.get("storage_path_relative", ""),
                storage_path_kind=data.get("storage_path_kind", ""),
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
                payload = self._recommendation_to_summary_dict(r, tag_map)
                payload["total_page"] = normalize_total_page(r.total_page)
                result.append(payload)
            
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

        cache_dir = recommendation_cache_manager.get_cache_dir(recommendation.id)
        
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
