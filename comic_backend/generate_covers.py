#!/usr/bin/env python3
"""
为现有漫画生成封面
支持多平台（JM、PK等）
"""
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infrastructure.logger import app_logger, error_logger
from utils.file_parser import file_parser
from utils.image_handler import image_handler


def generate_cover(comic_id, first_image_path):
    """生成封面缩略图"""
    try:
        cover_url = image_handler.generate_cover(comic_id, first_image_path)
        if cover_url and cover_url != "/static/default/default_cover.jpg":
            app_logger.info(f"封面生成成功: comic_id={comic_id}, cover_url={cover_url}")
        return cover_url
    except Exception as e:
        error_logger.error(f"生成封面失败: {e}")
        return None


def get_comic_image_dir(comic_id):
    """获取漫画图片目录"""
    return file_parser._get_comic_dir(comic_id)


def process_database(json_file, data_key):
    """处理指定数据库文件"""
    if not os.path.exists(json_file):
        app_logger.warning(f"数据库文件不存在: {json_file}")
        return 0
    
    app_logger.info(f"处理数据库: {json_file}")
    
    # 读取数据库
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    comics = data.get(data_key, [])
    if not comics:
        app_logger.info(f"没有漫画需要生成封面: {json_file}")
        return 0
    
    app_logger.info(f"找到 {len(comics)} 个漫画")
    
    updated_count = 0
    
    # 为每个漫画生成封面
    for comic in comics:
        comic_id = comic['id']
        
        try:
            # 查找漫画图片目录
            comic_dir = get_comic_image_dir(comic_id)
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
                updated_count += 1
        except Exception as e:
            error_logger.error(f"处理漫画 {comic_id} 失败: {e}")
            continue
    
    # 保存更新后的数据
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    app_logger.info(f"封面生成完成，已更新 {updated_count} 个漫画")
    return updated_count


def main():
    """主函数"""
    app_logger.info("=" * 60)
    app_logger.info("开始为现有漫画生成封面")
    app_logger.info("=" * 60)
    
    total_updated = 0
    
    # 处理主页漫画
    from core.constants import JSON_FILE
    count = process_database(JSON_FILE, 'comics')
    total_updated += count
    
    # 处理推荐页漫画
    from core.constants import RECOMMENDATION_JSON_FILE
    count = process_database(RECOMMENDATION_JSON_FILE, 'recommendations')
    total_updated += count
    
    app_logger.info("=" * 60)
    app_logger.info(f"全部完成！共更新 {total_updated} 个漫画的封面")
    app_logger.info("=" * 60)


if __name__ == '__main__':
    main()
