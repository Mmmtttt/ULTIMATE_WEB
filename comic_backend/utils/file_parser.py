import os
import re
from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR, SUPPORTED_FORMATS, JSON_FILE
from core.platform import get_platform_from_id, get_original_id, Platform
from infrastructure.logger import app_logger, error_logger


class FileParser:
    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS
    
    def _get_comic_dir(self, comic_id):
        """
        根据漫画 ID 推断其在本地的根目录。
        对于不同平台，目录结构可能不同：
        - JM: data/pictures/JM/{original_id}
        - PK: 默认使用 Picacomic-Crawler 的目录规则：comics/{author}/{title}
        """
        platform = get_platform_from_id(comic_id)
        original_id = get_original_id(comic_id)
        
        if platform == Platform.JM:
            return os.path.join(JM_PICTURES_DIR, original_id)
        elif platform == Platform.PK:
            # 优先按 Picacomic-Crawler 默认规则推导目录:
            # base_dir = PK_PICTURES_DIR
            # dir_rule = 'comics/{author}/{title}'
            try:
                from infrastructure.persistence.json_storage import JsonStorage
                from core.constants import RECOMMENDATION_JSON_FILE
                
                author = "unknown"
                title = "unknown"
                
                # 首先从主页数据库查找
                storage = JsonStorage(JSON_FILE)
                db_data = storage.read()
                comics = db_data.get("comics", [])
                
                found = False
                for c in comics:
                    if c.get("id") == comic_id:
                        author = c.get("author") or "unknown"
                        title = c.get("title") or f"漫画_{original_id}"
                        found = True
                        break
                
                # 如果主页没找到，从推荐页数据库查找
                if not found:
                    rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
                    rec_db_data = rec_storage.read()
                    recommendations = rec_db_data.get("recommendations", [])
                    
                    for r in recommendations:
                        if r.get("id") == comic_id:
                            author = r.get("author") or "unknown"
                            title = r.get("title") or f"漫画_{original_id}"
                            found = True
                            break
                
                comic_dir = os.path.join(PK_PICTURES_DIR, "comics", str(author), str(title))
                
                # 如果该目录存在，则使用该目录
                if os.path.exists(comic_dir):
                    return comic_dir
                
                # 回退到按 original_id 命名的目录，兼容未来可能的目录规则调整
                fallback_dir = os.path.join(PK_PICTURES_DIR, original_id)
                return fallback_dir
            except Exception as e:
                error_logger.error(f"解析 PK 漫画目录失败，使用默认目录结构: {e}")
                return os.path.join(PK_PICTURES_DIR, original_id)
        else:
            raise ValueError(f"未知的平台类型，漫画ID: {comic_id}")
    
    def parse_comic_images(self, comic_id):
        try:
            comic_dir = self._get_comic_dir(comic_id)
            if not os.path.exists(comic_dir):
                app_logger.warning(f"漫画目录不存在: {comic_dir}")
                return []
            
            image_paths = []
            
            # 使用递归遍历，兼容 PK 平台按章节分级的目录结构
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
