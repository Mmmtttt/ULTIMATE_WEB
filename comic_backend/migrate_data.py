#!/usr/bin/env python3
"""
数据迁移脚本
将旧数据库中的 tags 和 lists 数据迁移到新的独立数据库文件中
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.constants import JSON_FILE, TAGS_JSON_FILE, LISTS_JSON_FILE
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger


def migrate_tags():
    """迁移标签数据"""
    try:
        # 读取旧数据库
        old_storage = JsonStorage(JSON_FILE)
        old_data = old_storage.read()
        old_tags = old_data.get("tags", [])
        
        if not old_tags:
            app_logger.info("没有需要迁移的标签数据")
            return True
        
        # 写入新的标签数据库
        new_storage = JsonStorage(TAGS_JSON_FILE)
        new_data = new_storage.read()
        
        # 合并旧标签数据
        existing_tag_ids = {t["id"] for t in new_data.get("tags", [])}
        for tag in old_tags:
            if tag["id"] not in existing_tag_ids:
                new_data.setdefault("tags", []).append(tag)
                app_logger.info(f"迁移标签: {tag['id']} - {tag['name']}")
        
        new_storage.write(new_data)
        app_logger.info(f"标签数据迁移完成，共迁移 {len(old_tags)} 个标签")
        return True
    except Exception as e:
        error_logger.error(f"迁移标签数据失败: {e}")
        return False


def migrate_lists():
    """迁移清单数据"""
    try:
        # 读取旧数据库
        old_storage = JsonStorage(JSON_FILE)
        old_data = old_storage.read()
        old_lists = old_data.get("lists", [])
        
        if not old_lists:
            app_logger.info("没有需要迁移的清单数据")
            return True
        
        # 写入新的清单数据库
        new_storage = JsonStorage(LISTS_JSON_FILE)
        new_data = new_storage.read()
        
        # 合并旧清单数据
        existing_list_ids = {l["id"] for l in new_data.get("lists", [])}
        for lst in old_lists:
            if lst["id"] not in existing_list_ids:
                new_data.setdefault("lists", []).append(lst)
                app_logger.info(f"迁移清单: {lst['id']} - {lst['name']}")
        
        new_storage.write(new_data)
        app_logger.info(f"清单数据迁移完成，共迁移 {len(old_lists)} 个清单")
        return True
    except Exception as e:
        error_logger.error(f"迁移清单数据失败: {e}")
        return False


def main():
    app_logger.info("开始数据迁移...")
    
    success = True
    
    # 迁移标签
    if not migrate_tags():
        success = False
    
    # 迁移清单
    if not migrate_lists():
        success = False
    
    if success:
        app_logger.info("数据迁移完成！")
        return 0
    else:
        app_logger.error("数据迁移部分失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
