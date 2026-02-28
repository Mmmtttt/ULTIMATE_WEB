import os
import re
from core.constants import PICTURES_DIR, SUPPORTED_FORMATS
from infrastructure.logger import app_logger, error_logger


class FileParser:
    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS
    
    def parse_comic_images(self, comic_id):
        try:
            comic_dir = os.path.join(PICTURES_DIR, comic_id)
            if not os.path.exists(comic_dir):
                app_logger.warning(f"漫画目录不存在: {comic_dir}")
                return []
            
            image_files = []
            for file in os.listdir(comic_dir):
                file_path = os.path.join(comic_dir, file)
                if os.path.isfile(file_path) and self.validate_image_format(file):
                    image_files.append(file)
            
            image_files = self.natural_sort(image_files)
            
            image_paths = [os.path.join(comic_dir, file) for file in image_files]
            app_logger.info(f"解析漫画图片成功: {comic_id}, 共 {len(image_paths)} 张图片")
            return image_paths
        except Exception as e:
            error_logger.error(f"解析漫画图片失败: {e}")
            return []
    
    def validate_image_format(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_formats
    
    def natural_sort(self, filenames):
        def alphanum_key(s):
            return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', s)]
        
        return sorted(filenames, key=alphanum_key)


file_parser = FileParser()
