import os
import re
from core.constants import (
    COMIC_DIR,
    LOCAL_PICTURES_DIR,
    SUPPORTED_FORMATS,
    JSON_FILE,
    RECOMMENDATION_JSON_FILE,
)
from infrastructure.logger import app_logger, error_logger
from protocol.platform_meta import (
    build_platform_root_dir,
    resolve_manifest_host_prefix,
    split_prefixed_id,
)


class FileParser:
    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS

    @staticmethod
    def _find_comic_record(comic_id):
        try:
            from infrastructure.persistence.json_storage import JsonStorage

            for json_file, data_key in (
                (JSON_FILE, "comics"),
                (RECOMMENDATION_JSON_FILE, "recommendations"),
            ):
                storage = JsonStorage(json_file)
                db_data = storage.read()
                for item in db_data.get(data_key, []) or []:
                    if str(item.get("id", "")).strip() == str(comic_id or "").strip():
                        return item
        except Exception as e:
            error_logger.error(f"查找漫画记录失败: {e}")
        return None
    
    def _get_comic_dir(self, comic_id):
        """
        根据漫画 ID 推断其在本地的根目录。
        优先走插件协议声明的 `storage.comic_dir.resolve`，让目录规则由插件自己决定。
        """
        platform_key, original_id, manifest = split_prefixed_id(comic_id, media_type="comic")
        if not original_id:
            raise ValueError(f"未知的平台类型，漫画ID: {comic_id}")

        local_dir = os.path.join(LOCAL_PICTURES_DIR, original_id)
        if str(original_id or "").upper().startswith("LOCAL"):
            comic_record = self._find_comic_record(comic_id)
            stored_dir_name = str((comic_record or {}).get("local_asset_dir_name", "")).strip()
            if stored_dir_name:
                named_local_dir = os.path.join(LOCAL_PICTURES_DIR, stored_dir_name)
                if os.path.exists(named_local_dir):
                    return named_local_dir
            if os.path.exists(local_dir):
                return local_dir
            if stored_dir_name:
                return os.path.join(LOCAL_PICTURES_DIR, stored_dir_name)
            return local_dir

        host_prefix = resolve_manifest_host_prefix(manifest, fallback=platform_key)
        base_dir = build_platform_root_dir(COMIC_DIR, manifest=manifest, platform_name=platform_key or host_prefix)
        comic_record = self._find_comic_record(comic_id) or {}
        author = comic_record.get("author") or comic_record.get("creator") or "unknown"
        title = comic_record.get("title") or f"漫画_{original_id}"

        try:
            from protocol.platform_service import get_platform_service

            comic_dir = get_platform_service().get_comic_dir(
                platform_key or host_prefix,
                original_id,
                author=author,
                title=title,
                base_dir=base_dir,
            )
            if comic_dir:
                return comic_dir
        except Exception as e:
            error_logger.error(f"解析协议漫画目录失败，使用默认目录结构: comic_id={comic_id}, error={e}")

        return os.path.join(base_dir, original_id)
    
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
    
    def parse_comic_images(self, comic_id):
        try:
            comic_dir = self._get_comic_dir(comic_id)
            if not os.path.exists(comic_dir):
                app_logger.warning(f"漫画目录不存在: {comic_dir}")
                return []
            
            image_paths = []
            
            # 使用递归遍历，兼容部分平台按章节分级的目录结构
            for root, _, files in os.walk(comic_dir):
                for file in files:
                    if self.validate_image_format(file):
                        image_paths.append(os.path.join(root, file))
            
            if not image_paths:
                app_logger.warning(f"漫画目录下未找到图片文件: {comic_dir}")
                return []
            
            image_paths = self.natural_sort_paths(image_paths, comic_dir)
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


file_parser = FileParser()
