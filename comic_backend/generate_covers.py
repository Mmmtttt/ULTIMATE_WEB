#!/usr/bin/env python3
"""
为现有漫画生成封面
"""
import os
import sys
from PIL import Image
from config import Config
from utils.json_handler import json_handler
from utils.logger import app_logger, error_logger

def generate_cover(comic_id, first_image_path):
    """生成封面缩略图"""
    try:
        # 确保封面目录存在
        os.makedirs(Config.COVER_DIR, exist_ok=True)
        
        # 封面保存路径
        cover_path = os.path.join(Config.COVER_DIR, f"{comic_id}.jpg")
        
        # 如果封面已存在，跳过
        if os.path.exists(cover_path):
            app_logger.info(f"封面已存在: {cover_path}")
            return f"/static/cover/{comic_id}.jpg"
        
        # 读取原始图片
        with Image.open(first_image_path) as img:
            # 计算缩放比例
            width, height = img.size
            cover_width = Config.COVER_WIDTH
            ratio = cover_width / width
            new_height = int(height * ratio)
            
            # 缩放图片
            resized_img = img.resize((cover_width, new_height), Image.LANCZOS)
            
            # 保存为JPEG格式
            resized_img.save(cover_path, 'JPEG', quality=Config.COVER_QUALITY)
        
        app_logger.info(f"封面生成成功: {cover_path}")
        return f"/static/cover/{comic_id}.jpg"
    except Exception as e:
        error_logger.error(f"生成封面失败: {e}")
        return None

def main():
    """主函数"""
    app_logger.info("开始为现有漫画生成封面")
    
    # 读取数据库
    db_data = json_handler.read_json()
    comics = db_data.get('comics', [])
    
    if not comics:
        app_logger.info("没有漫画需要生成封面")
        return
    
    app_logger.info(f"找到 {len(comics)} 个漫画")
    
    # 为每个漫画生成封面
    for comic in comics:
        comic_id = comic['id']
        
        # 查找第一张图片
        comic_dir = os.path.join(Config.PICTURES_DIR, comic_id)
        if not os.path.exists(comic_dir):
            error_logger.warning(f"漫画目录不存在: {comic_dir}")
            continue
        
        # 获取图片列表
        image_files = [f for f in os.listdir(comic_dir) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))]
        
        if not image_files:
            error_logger.warning(f"漫画没有图片: {comic_id}")
            continue
        
        # 排序并获取第一张
        image_files.sort()
        first_image = os.path.join(comic_dir, image_files[0])
        
        # 生成封面
        cover_path = generate_cover(comic_id, first_image)
        
        if cover_path:
            # 更新数据库中的封面路径
            comic['cover_path'] = cover_path
            app_logger.info(f"更新漫画 {comic_id} 的封面路径: {cover_path}")
    
    # 保存更新后的数据
    if json_handler.write_json(db_data):
        app_logger.info("封面生成完成，数据已更新")
    else:
        error_logger.error("保存数据失败")

if __name__ == '__main__':
    main()
