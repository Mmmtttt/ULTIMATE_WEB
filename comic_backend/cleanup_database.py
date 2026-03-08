#!/usr/bin/env python3
"""
数据库清理脚本
从主数据库中移除旧的 tags 和 lists 字段
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE, VIDEO_JSON_FILE, VIDEO_RECOMMENDATION_JSON_FILE
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger


def cleanup_database(json_file, description):
    """清理指定数据库文件"""
    try:
        storage = JsonStorage(json_file)
        data = storage.read()
        
        tags_removed = False
        if 'tags' in data:
            del data['tags']
            tags_removed = True
            app_logger.info(f"从 {description} 中移除 tags 字段")
        
        lists_removed = False
        if 'lists' in data:
            del data['lists']
            lists_removed = True
            app_logger.info(f"从 {description} 中移除 lists 字段")
        
        if tags_removed or lists_removed:
            storage.write(data)
            app_logger.info(f"{description} 数据库清理完成")
            return True
        else:
            app_logger.info(f"{description} 数据库不需要清理")
            return True
    except Exception as e:
        error_logger.error(f"清理 {description} 数据库失败: {e}")
        return False


def main():
    app_logger.info("开始数据库清理...")
    
    success = True
    
    # 清理各个数据库
    if not cleanup_database(JSON_FILE, "漫画主数据库"):
        success = False
    
    if not cleanup_database(RECOMMENDATION_JSON_FILE, "漫画推荐数据库"):
        success = False
    
    if not cleanup_database(VIDEO_JSON_FILE, "视频主数据库"):
        success = False
    
    if not cleanup_database(VIDEO_RECOMMENDATION_JSON_FILE, "视频推荐数据库"):
        success = False
    
    if success:
        app_logger.info("数据库清理完成！")
        return 0
    else:
        app_logger.error("数据库清理部分失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
