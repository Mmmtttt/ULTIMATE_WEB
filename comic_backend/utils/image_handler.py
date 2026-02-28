import os
from io import BytesIO
from PIL import Image
from core.constants import COVER_DIR, COVER_WIDTH, COVER_QUALITY, BACKUP_SUFFIX
from infrastructure.logger import app_logger, error_logger


class ImageHandler:
    def __init__(self):
        self.cover_width = COVER_WIDTH
        self.cover_quality = COVER_QUALITY
    
    def generate_cover(self, comic_id, first_image_path):
        try:
            os.makedirs(COVER_DIR, exist_ok=True)
            
            cover_path = os.path.join(COVER_DIR, f"{comic_id}.jpg")
            
            with Image.open(first_image_path) as img:
                width, height = img.size
                ratio = self.cover_width / width
                new_height = int(height * ratio)
                
                resized_img = img.resize((self.cover_width, new_height), Image.LANCZOS)
                
                resized_img.save(cover_path, 'JPEG', quality=self.cover_quality)
            
            app_logger.info(f"封面生成成功: {cover_path}")
            return f"/static/cover/{comic_id}.jpg"
        except Exception as e:
            error_logger.error(f"生成封面失败: {e}")
            return "/static/default/default_cover.jpg"
    
    def get_image_stream(self, comic_id, page_num):
        try:
            from utils.file_parser import file_parser
            
            image_paths = file_parser.parse_comic_images(comic_id)
            if not image_paths:
                error_logger.warning(f"漫画图片不存在: {comic_id}")
                return None
            
            if page_num < 1 or page_num > len(image_paths):
                error_logger.warning(f"页码超出范围: {page_num}")
                return None
            
            image_path = image_paths[page_num - 1]
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            stream = BytesIO(image_data)
            app_logger.info(f"获取图片流成功: {comic_id}, 第 {page_num} 页")
            return stream
        except Exception as e:
            error_logger.error(f"获取图片流失败: {e}")
            return None
    
    def create_backup(self, source_path):
        try:
            backup_path = source_path + BACKUP_SUFFIX
            import shutil
            shutil.copy2(source_path, backup_path)
            app_logger.info(f"创建备份成功: {backup_path}")
            return True
        except Exception as e:
            error_logger.error(f"创建备份失败: {e}")
            return False
    
    def restore_backup(self, file_path):
        try:
            backup_path = file_path + BACKUP_SUFFIX
            if os.path.exists(backup_path):
                import shutil
                shutil.copy2(backup_path, file_path)
                app_logger.info(f"从备份恢复成功: {file_path}")
                return True
            else:
                error_logger.warning(f"备份文件不存在: {backup_path}")
                return False
        except Exception as e:
            error_logger.error(f"恢复备份失败: {e}")
            return False


image_handler = ImageHandler()
