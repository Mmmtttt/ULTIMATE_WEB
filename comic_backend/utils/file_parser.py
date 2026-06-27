import os
import re
import threading
import time
from typing import Any, Dict, List, Optional
from application.persisted_content_metadata import resolve_data_relative_path
from core.host_platform_fallback import infer_existing_host_comic_dir
from core.constants import (
    COMIC_DIR,
    LOCAL_PICTURES_DIR,
    SUPPORTED_FORMATS,
    JSON_FILE,
    RECOMMENDATION_JSON_FILE,
)
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories import JsonDocumentRepository


class FileParser:
    IMAGE_CACHE_TTL_SECONDS = 60

    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS
        self._image_cache = {}
        self._image_cache_lock = threading.Lock()

    _chapter_numeric_pattern = re.compile(
        r"^(?:第)?(?:\d{1,4}|[a-z]{1,2}|[ivxlcdm]{1,6}|[一二三四五六七八九十百千零〇两]{1,6})(?:话|章|回|节|卷|集|部)?$",
        re.IGNORECASE,
    )
    _chapter_english_pattern = re.compile(
        r"^(?:ch|chap|chapter|ep|episode|vol|volume)[\s._-]*[\divxlcdm一二三四五六七八九十百千零〇两-]{1,12}$",
        re.IGNORECASE,
    )

    @staticmethod
    def _find_comic_record(comic_id):
        try:
            for json_file, data_key in (
                (JSON_FILE, "comics"),
                (RECOMMENDATION_JSON_FILE, "recommendations"),
            ):
                storage = JsonDocumentRepository(json_file, data_key)
                db_data = storage.read_document()
                for item in db_data.get(data_key, []) or []:
                    if str(item.get("id", "")).strip() == str(comic_id or "").strip():
                        return item
        except Exception as e:
            error_logger.error(f"查找漫画记录失败: {e}")
        return None
    
    def _get_comic_dir(self, comic_id):
        """
        根据漫画 ID 推断其在本地的根目录。
        优先使用数据库和宿主内建规则推断真实目录，兼容移动端无第三方库场景。
        """
        comic_record = self._find_comic_record(comic_id) or {}
        stored_relative = str((comic_record or {}).get("storage_path_relative", "")).strip()
        if stored_relative:
            stored_abs = resolve_data_relative_path(stored_relative)
            if stored_abs and os.path.isdir(stored_abs):
                return stored_abs

        host_resolved_dir = infer_existing_host_comic_dir(
            comic_id,
            comic_record,
            comic_root=COMIC_DIR,
            local_root=LOCAL_PICTURES_DIR,
        )
        if host_resolved_dir:
            return host_resolved_dir

        raise ValueError(f"未知或不存在的漫画目录，漫画ID: {comic_id}")
    
    def _generate_name_variants(self, name):
        """生成名称的变体，用于目录匹配"""
        name = (name or "").strip().rstrip(".")
        variants = set()
        variants.add(name)
        variants.add(self._normalize_fs_name(name))
        
        # 替换常见分隔符
        if " | " in name:
            variants.add(name.replace(" | ", " _ "))
            variants.add(name.replace(" | ", "_"))
        if "|" in name:
            variants.add(name.replace("|", " _ "))
            variants.add(name.replace("|", "_"))
        
        # 处理空格变化
        variants.add(name.replace(" ", ""))
        variants.add(name.replace("  ", " "))
        
        # 处理全角/半角空格
        variants.add(name.replace("\u3000", " "))
        
        return list(variants)

    def _normalize_fs_name(self, name: str) -> str:
        """按下载器规则对目录名做规范化，提升命中率"""
        normalized = (name or "").strip().rstrip(".")
        normalized = re.sub(r'[\\/:*?"<>|]', '_', normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
    
    def _fuzzy_match_dir(self, dir_list, target_name):
        """在目录列表中模糊匹配目标名称"""
        target_lower = target_name.lower()
        
        # 首先尝试精确匹配（忽略大小写）
        for dir_name in dir_list:
            if dir_name.lower() == target_lower:
                return dir_name
        
        # 尝试替换分隔符后的匹配
        target_variants = self._generate_name_variants(target_name)
        for dir_name in dir_list:
            dir_lower = dir_name.lower()
            for variant in target_variants:
                if variant.lower() == dir_lower:
                    return dir_name
        
        # 尝试部分匹配
        for dir_name in dir_list:
            dir_lower = dir_name.lower()
            # 检查目标名称是否包含在目录名中，或者反过来
            if target_lower in dir_lower or dir_lower in target_lower:
                # 进一步验证相似度
                if len(target_lower) > 0 and len(dir_lower) > 0:
                    # 计算共同字符比例
                    common_chars = set(target_lower) & set(dir_lower)
                    ratio = len(common_chars) / max(len(set(target_lower)), len(set(dir_lower)))
                    if ratio > 0.8:  # 80% 以上的相似度
                        return dir_name
        
        return None
    
    def clear_image_cache(self, comic_id: str = ""):
        normalized_id = str(comic_id or "").strip()
        with self._image_cache_lock:
            if normalized_id:
                self._image_cache.pop(normalized_id, None)
            else:
                self._image_cache.clear()

    @staticmethod
    def _safe_dir_mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except Exception:
            return 0.0

    def _get_cached_image_paths(self, comic_id: str, comic_dir: str) -> Optional[List[str]]:
        normalized_id = str(comic_id or "").strip()
        if not normalized_id or not comic_dir:
            return None

        dir_mtime = self._safe_dir_mtime(comic_dir)
        now = time.monotonic()
        with self._image_cache_lock:
            entry = self._image_cache.get(normalized_id)
            if not entry:
                return None
            if entry.get("comic_dir") != comic_dir:
                return None
            if float(entry.get("expires_at", 0) or 0) < now:
                self._image_cache.pop(normalized_id, None)
                return None
            if float(entry.get("dir_mtime", 0) or 0) != dir_mtime:
                self._image_cache.pop(normalized_id, None)
                return None
            return list(entry.get("paths") or [])

    def _set_cached_image_paths(self, comic_id: str, comic_dir: str, image_paths: List[str]):
        normalized_id = str(comic_id or "").strip()
        if not normalized_id or not comic_dir:
            return

        with self._image_cache_lock:
            self._image_cache[normalized_id] = {
                "comic_dir": comic_dir,
                "dir_mtime": self._safe_dir_mtime(comic_dir),
                "paths": list(image_paths or []),
                "expires_at": time.monotonic() + self.IMAGE_CACHE_TTL_SECONDS,
            }

    def parse_comic_images(self, comic_id):
        try:
            comic_dir = self._get_comic_dir(comic_id)
            if not os.path.exists(comic_dir):
                app_logger.warning(f"漫画目录不存在: {comic_dir}")
                return []

            cached_paths = self._get_cached_image_paths(comic_id, comic_dir)
            if cached_paths is not None:
                return cached_paths
            
            image_paths = []
            
            # 使用递归遍历，兼容部分平台按章节分级的目录结构
            for root, _, files in os.walk(comic_dir):
                for file in files:
                    if self.validate_image_format(file):
                        image_paths.append(os.path.join(root, file))
            
            if not image_paths:
                app_logger.warning(f"漫画目录下未找到图片文件: {comic_dir}")
                self._set_cached_image_paths(comic_id, comic_dir, [])
                return []
            
            image_paths = self.natural_sort_paths(image_paths, comic_dir)
            self._set_cached_image_paths(comic_id, comic_dir, image_paths)
            app_logger.info(f"解析漫画图片成功: {comic_id}, 共 {len(image_paths)} 张图片")
            return image_paths
        except Exception as e:
            error_logger.error(f"解析漫画图片失败: {e}")
            return []
    
    def validate_image_format(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_formats
    
    def natural_sort_paths(self, paths, base_dir):
        """
        对图片路径进行自然排序：
        - 优先按照相对路径排序，保证章节顺序
        - 再在每一层中使用数字感知的自然排序
        """
        def alphanum_key(s):
            return [int(c) if c.isdigit() else c for c in re.split(r'([0-9]+)', s)]
        
        def sort_key(path):
            rel = os.path.relpath(path, base_dir)
            return alphanum_key(rel)
        
        return sorted(paths, key=sort_key)

    @classmethod
    def _normalize_sort_path(cls, path: str) -> str:
        normalized = str(path or "").replace("\\", "/").strip()
        return normalized.lstrip("./")

    @classmethod
    def _split_parent_segments(cls, sort_path: str) -> List[str]:
        normalized = cls._normalize_sort_path(sort_path)
        if not normalized:
            return []
        parts = normalized.split("/")
        if len(parts) <= 1:
            return []
        return [segment.strip() for segment in parts[:-1] if str(segment or "").strip()]

    @classmethod
    def _score_chapter_label(cls, label: str) -> int:
        compact = re.sub(r"\s+", "", str(label or "")).strip()
        if not compact:
            return 0
        if cls._chapter_numeric_pattern.fullmatch(compact):
            return 5
        if cls._chapter_english_pattern.fullmatch(compact):
            return 5
        if any(char.isdigit() for char in compact):
            return 3
        return 1

    @classmethod
    def _choose_chapter_level(cls, parent_segments_list: List[List[str]]) -> Optional[int]:
        if not parent_segments_list:
            return None

        max_depth = max((len(segments) for segments in parent_segments_list), default=0)
        best_level: Optional[int] = None
        best_score: Optional[tuple] = None

        for level in range(max_depth):
            if not all(len(segments) > level for segments in parent_segments_list):
                continue

            prefixes = ["/".join(segments[: level + 1]) for segments in parent_segments_list]
            unique_prefixes = list(dict.fromkeys(prefixes))
            if len(unique_prefixes) < 2:
                continue

            labels = [segments[level] for segments in parent_segments_list]
            label_scores = [cls._score_chapter_label(label) for label in labels]
            chapter_like_ratio = (
                sum(1 for score in label_scores if score >= 4) / len(label_scores)
                if label_scores
                else 0
            )
            average_label_score = sum(label_scores) / len(label_scores) if label_scores else 0
            candidate_score = (
                chapter_like_ratio,
                average_label_score,
                level,
                len(unique_prefixes),
            )
            if best_score is None or candidate_score > best_score:
                best_level = level
                best_score = candidate_score

        return best_level

    @classmethod
    def _format_chapter_title(cls, raw_label: str, fallback_index: int) -> str:
        label = str(raw_label or "").strip()
        if not label:
            return f"第{fallback_index}章"

        compact = re.sub(r"\s+", "", label)
        if re.fullmatch(r"\d{1,4}", compact):
            return f"第{int(compact)}章"
        if re.fullmatch(r"[ivxlcdm]{1,6}", compact, re.IGNORECASE):
            return f"第{compact.upper()}章"
        if re.fullmatch(r"[一二三四五六七八九十百千零〇两]{1,6}", compact):
            return f"第{compact}章"
        return label

    @classmethod
    def _format_prefixed_title(cls, prefix_segments: List[str], fallback_index: int) -> str:
        cleaned = [str(segment or "").strip() for segment in prefix_segments if str(segment or "").strip()]
        if not cleaned:
            return f"第{fallback_index}章"
        if len(cleaned) == 1:
            return cls._format_chapter_title(cleaned[0], fallback_index)
        head = cleaned[:-1]
        tail = cls._format_chapter_title(cleaned[-1], fallback_index)
        return " / ".join([*head, tail])

    @classmethod
    def build_chapter_outline(cls, sort_paths: List[str]) -> List[Dict[str, Any]]:
        normalized_paths = [cls._normalize_sort_path(path) for path in (sort_paths or []) if cls._normalize_sort_path(path)]
        if len(normalized_paths) < 2:
            return []

        parent_segments_list = [cls._split_parent_segments(path) for path in normalized_paths]
        if not any(parent_segments_list):
            return []

        level = cls._choose_chapter_level(parent_segments_list)
        if level is None:
            return []

        groups: List[Dict[str, Any]] = []
        current_group: Optional[Dict[str, Any]] = None

        for page_num, segments in enumerate(parent_segments_list, start=1):
            prefix_segments = segments[: level + 1]
            group_key = "/".join(prefix_segments)
            if current_group is None or current_group["key"] != group_key:
                current_group = {
                    "key": group_key,
                    "prefix_segments": prefix_segments,
                    "start_page": page_num,
                    "end_page": page_num,
                    "page_count": 1,
                }
                groups.append(current_group)
                continue

            current_group["end_page"] = page_num
            current_group["page_count"] += 1

        if len(groups) <= 1:
            return []

        provisional_titles = [
            cls._format_chapter_title(group["prefix_segments"][-1], index)
            for index, group in enumerate(groups, start=1)
        ]
        title_counts: Dict[str, int] = {}
        for title in provisional_titles:
            title_counts[title] = title_counts.get(title, 0) + 1

        chapters: List[Dict[str, Any]] = []
        for index, group in enumerate(groups, start=1):
            title = provisional_titles[index - 1]
            if title_counts.get(title, 0) > 1:
                title = cls._format_prefixed_title(group["prefix_segments"], index)
            chapters.append(
                {
                    "key": group["key"],
                    "title": title,
                    "start_page": group["start_page"],
                    "end_page": group["end_page"],
                    "page_count": group["page_count"],
                }
            )

        return chapters

    def parse_comic_chapters(self, comic_id) -> List[Dict[str, Any]]:
        try:
            comic_dir = self._get_comic_dir(comic_id)
            image_paths = self.parse_comic_images(comic_id)
            if not comic_dir or not image_paths:
                return []
            relative_paths = [os.path.relpath(path, comic_dir).replace("\\", "/") for path in image_paths]
            return self.build_chapter_outline(relative_paths)
        except Exception as e:
            error_logger.error(f"解析漫画章节失败: {e}")
            return []


file_parser = FileParser()
