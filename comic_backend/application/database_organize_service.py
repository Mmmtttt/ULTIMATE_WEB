from __future__ import annotations

from typing import Any, Dict, List

from infrastructure.common.result import ServiceResult

from .comic_app_service import ComicAppService
from .video_app_service import VideoAppService


class DatabaseOrganizeService:
    """Unified database organize actions dispatcher by mode/action."""

    def __init__(self, comic_service: ComicAppService = None, video_service: VideoAppService = None):
        self._comic_service = comic_service or ComicAppService()
        self._video_service = video_service or VideoAppService()

    @staticmethod
    def _normalize_mode(raw_mode: str) -> str:
        mode = str(raw_mode or "").strip().lower()
        return "video" if mode == "video" else "comic"

    def get_options(self, mode: str) -> ServiceResult:
        normalized_mode = self._normalize_mode(mode)
        if normalized_mode == "comic":
            options: List[Dict[str, Any]] = [
                {
                    "action": "repair_cover",
                    "name": "修复封面",
                    "description": "修复封面路径并回写本地实际页数。",
                    "confirm_message": "将修复封面并同步页数，是否继续？",
                    "implemented": True,
                },
                {
                    "action": "deduplicate_by_title",
                    "name": "查重并移入回收站",
                    "description": "按清洗标题+章节信息查重，重复项移入回收站。",
                    "confirm_message": "将执行查重并把重复内容移入回收站，是否继续？",
                    "implemented": True,
                },
                {
                    "action": "enrich_local_metadata",
                    "name": "LOCAL补全信息",
                    "description": "为 LOCAL 漫画补全作者与标签（JM优先，JM不命中再尝试PK）。",
                    "confirm_message": "将联网补全 LOCAL 漫画信息，是否继续？",
                    "implemented": True,
                },
            ]
        else:
            options = [
                {
                    "action": "deduplicate_by_code",
                    "name": "查重并移入回收站",
                    "description": "按视频 code 查重，重复项移入回收站。",
                    "confirm_message": "将执行视频 code 查重并把重复内容移入回收站，是否继续？",
                    "implemented": True,
                },
                {
                    "action": "enrich_local_metadata",
                    "name": "LOCAL补全信息",
                    "description": "为 LOCAL 视频补全标题、作者、标签与预览资源（JAVDB优先，失败回退JAVBUS）。",
                    "confirm_message": "将联网补全 LOCAL 视频信息，是否继续？",
                    "implemented": True,
                },
            ]

        return ServiceResult.ok(
            {
                "mode": normalized_mode,
                "options": options,
            },
            "Organize options fetched",
        )

    @staticmethod
    def _summary_for_repair_cover(data: Dict[str, Any]) -> str:
        home = (data or {}).get("home") or {}
        rec = (data or {}).get("recommendation") or {}
        updated_cover_paths = int(home.get("updated_cover_paths", 0)) + int(rec.get("updated_cover_paths", 0))
        rewritten_pages = int(home.get("rewritten_total_pages", 0))
        return f"修复封面完成：修复封面 {updated_cover_paths}，回写页数 {rewritten_pages}"

    def run(self, mode: str, action: str) -> ServiceResult:
        normalized_mode = self._normalize_mode(mode)
        normalized_action = str(action or "").strip().lower()

        if normalized_mode == "video":
            if normalized_action == "deduplicate_by_code":
                return self._video_service.organize_deduplicate_by_code()
            if normalized_action == "enrich_local_metadata":
                return self._video_service.organize_enrich_local_metadata()
            return ServiceResult.error(f"不支持的视频整理动作: {normalized_action}")

        if normalized_action == "repair_cover":
            result = self._comic_service.organize_database_v2()
            if result.success:
                data = result.data if isinstance(result.data, dict) else {}
                if "summary" not in data:
                    data["summary"] = self._summary_for_repair_cover(data)
                result.data = data
            return result

        if normalized_action == "deduplicate_by_title":
            return self._comic_service.organize_deduplicate_by_title()

        if normalized_action == "enrich_local_metadata":
            return self._comic_service.organize_enrich_local_metadata()

        return ServiceResult.error(f"不支持的整理动作: {normalized_action}")
