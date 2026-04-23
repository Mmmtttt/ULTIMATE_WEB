from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from core.enums import ContentType
from core.utils import normalize_total_page


class MetaDataAdapter:
    """Host-side metadata normalizer used by protocol-backed import flows."""

    def __init__(
        self,
        is_recommendation: bool = False,
        existing_tags: Optional[List[Dict[str, Any]]] = None,
        platform: Optional[Any] = None,
        platform_prefix: str = "",
        cover_path_prefix: str = "",
        prefer_remote_cover: bool = False,
    ):
        self.is_recommendation = bool(is_recommendation)
        self.existing_tags = list(existing_tags or [])
        self.platform = platform
        self.platform_prefix = str(platform_prefix or "").strip().upper()
        self.cover_path_prefix = str(cover_path_prefix or "").strip().upper()
        self.prefer_remote_cover = bool(prefer_remote_cover)

    def _resolve_platform_prefix(self) -> str:
        if self.platform_prefix:
            return self.platform_prefix
        return str(getattr(self.platform, "value", self.platform) or "").strip().upper()

    def _resolve_cover_prefix(self) -> str:
        if self.cover_path_prefix:
            return self.cover_path_prefix
        return self._resolve_platform_prefix()

    def _build_prefixed_id(self, original_id: str) -> str:
        normalized_original_id = str(original_id or "").strip()
        if not normalized_original_id:
            return normalized_original_id

        prefix = self._resolve_platform_prefix()
        if not prefix:
            return normalized_original_id

        if normalized_original_id.upper().startswith(prefix):
            return normalized_original_id
        return f"{prefix}{normalized_original_id}"

    def _should_prefer_remote_cover(self) -> bool:
        return self.prefer_remote_cover

    def parse_meta_data(self, meta_json: Dict[str, Any]) -> Dict[str, Any]:
        albums = meta_json.get("albums", [])

        comics_key = "recommendations" if self.is_recommendation else "comics"
        total_key = "total_recommendations" if self.is_recommendation else "total_comics"

        result = {
            "collection_name": meta_json.get("collection_name", "我的收藏集"),
            "user": meta_json.get("user", "用户名"),
            total_key: len(albums),
            "last_updated": meta_json.get("last_updated", time.strftime("%Y-%m-%d")),
            "tags": [],
            "lists": [],
            comics_key: [],
            "user_config": {
                "default_page_mode": "up_down",
                "default_background": "dark",
                "auto_hide_toolbar": False,
                "show_page_number": False,
            },
        }

        tag_name_to_id: Dict[str, str] = {}
        existing_tag_ids = set()
        max_tag_num = 0

        for tag in self.existing_tags:
            tag_content_type = str(tag.get("content_type", ContentType.COMIC.value) or "").strip().lower()
            if tag_content_type not in {ContentType.COMIC.value, ContentType.VIDEO.value}:
                tag_content_type = ContentType.COMIC.value
            if tag_content_type != ContentType.COMIC.value:
                continue
            tag_name = str(tag.get("name") or "").strip()
            tag_id = str(tag.get("id") or "").strip()
            if not tag_name or not tag_id:
                continue
            tag_name_to_id[tag_name] = tag_id
            existing_tag_ids.add(tag_id)
            if tag_id.startswith("tag_"):
                try:
                    max_tag_num = max(max_tag_num, int(tag_id[4:]))
                except ValueError:
                    pass

        all_new_tags = set()
        for album in albums:
            for tag_name in album.get("tags", []) or []:
                normalized_name = str(tag_name or "").strip()
                if normalized_name:
                    all_new_tags.add(normalized_name)

        for tag_name in sorted(all_new_tags):
            if tag_name not in tag_name_to_id:
                max_tag_num += 1
                new_id = f"tag_{max_tag_num:03d}"
                while new_id in existing_tag_ids:
                    max_tag_num += 1
                    new_id = f"tag_{max_tag_num:03d}"

                tag_name_to_id[tag_name] = new_id
                existing_tag_ids.add(new_id)
                result["tags"].append(
                    {
                        "id": new_id,
                        "name": tag_name,
                        "content_type": ContentType.COMIC.value,
                        "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                )

        for album in albums:
            result[comics_key].append(self._convert_album_to_comic(album, tag_name_to_id))

        return result

    def _convert_album_to_comic(self, album: Dict[str, Any], tag_id_map: Dict[str, str]) -> Dict[str, Any]:
        original_id = str(album.get("album_id", ""))
        comic_id = self._build_prefixed_id(original_id)
        cover_prefix = self._resolve_cover_prefix()

        if self._should_prefer_remote_cover():
            cover_path = album.get("cover_url") or f"/static/cover/{cover_prefix}/{original_id}.jpg"
        else:
            cover_path = f"/static/cover/{cover_prefix}/{original_id}.jpg"

        tag_ids: List[str] = []
        seen_tag_ids = set()
        for tag_name in album.get("tags", []) or []:
            normalized_name = str(tag_name or "").strip()
            if normalized_name in tag_id_map:
                tag_id = tag_id_map[normalized_name]
                if tag_id not in seen_tag_ids:
                    seen_tag_ids.add(tag_id)
                    tag_ids.append(tag_id)

        return {
            "id": comic_id,
            "title": album.get("title", f"漫画_{original_id}"),
            "title_jp": album.get("title_jp", ""),
            "author": album.get("author", ""),
            "desc": "",
            "cover_path": cover_path,
            "total_page": normalize_total_page(album.get("pages", 0)),
            "current_page": 1,
            "score": None,
            "tag_ids": tag_ids,
            "list_ids": [],
            "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_read_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def merge_to_existing(
        self,
        existing_data: Dict[str, Any],
        new_comics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        existing_copy = json.loads(json.dumps(existing_data))
        existing_copy["comics"].extend(new_comics)
        existing_copy["total_comics"] = len(existing_copy["comics"])
        existing_copy["last_updated"] = time.strftime("%Y-%m-%d")
        return existing_copy


class DuplicateChecker:
    """Fast duplicate checker for host-side import normalization."""

    def __init__(self, existing_ids: List[str]):
        self.existing_ids_set = set(existing_ids)

    def is_duplicate(self, comic_id: str) -> bool:
        return comic_id in self.existing_ids_set

    def filter_duplicates(self, comics: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        new_comics: List[Dict[str, Any]] = []
        existing_ids: List[str] = []

        for comic in comics:
            comic_id = str(comic.get("id") or "").strip()
            if comic_id in self.existing_ids_set:
                existing_ids.append(comic_id)
                continue
            new_comics.append(comic)
            self.existing_ids_set.add(comic_id)

        return new_comics, existing_ids


def create_adapter(is_recommendation: bool = False, platform: Optional[Any] = None) -> MetaDataAdapter:
    return MetaDataAdapter(is_recommendation=is_recommendation, platform=platform)


def create_duplicate_checker(existing_ids: List[str]) -> DuplicateChecker:
    return DuplicateChecker(existing_ids)
