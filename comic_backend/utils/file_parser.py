import os
import re
from config import Config
from utils.logger import app_logger, error_logger

class FileParser:
    def __init__(self):
        self.supported_formats = Config.SUPPORTED_FORMATS
    
    def parse_comic_images(self, comic_id):
        """解析漫画图片目录，返回有序的图片路径列表"""
        try:
            comic_dir = os.path.join(Config.PICTURES_DIR, comic_id)
            if not os.path.exists(comic_dir):
                app_logger.warning(f"漫画目录不存在: {comic_dir}")
                return []
            
            # 扫描目录中的图片文件
            image_files = []
            for file in os.listdir(comic_dir):
                file_path = os.path.join(comic_dir, file)
                if os.path.isfile(file_path) and self.validate_image_format(file):
                    image_files.append(file)
            
            # 自然排序
            image_files = self.natural_sort(image_files)
            
            # 构建完整路径
            image_paths = [os.path.join(comic_dir, file) for file in image_files]
            app_logger.info(f"解析漫画图片成功: {comic_id}, 共 {len(image_paths)} 张图片")
            return image_paths
        except Exception as e:
            error_logger.error(f"解析漫画图片失败: {e}")
            return []
    
    def validate_image_format(self, filename):
        """验证图片格式是否支持"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_formats
    
    def natural_sort(self, filenames):
        """自然排序算法"""
        def alphanum_key(s):
            """将字符串分解为文本和数字部分"""
            return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', s)]
        
        return sorted(filenames, key=alphanum_key)

# 创建单例实例
file_parser = FileParser()
