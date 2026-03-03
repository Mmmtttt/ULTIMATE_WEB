"""
JAVDB API Scraper 包装器
"""

import sys
import os

_javdb_path = os.path.join(os.path.dirname(__file__), 'javdb-api-scraper')

# 确保 javdb-api-scraper 路径在最前面，优先于 comic_backend/utils
if _javdb_path in sys.path:
    sys.path.remove(_javdb_path)
sys.path.insert(0, _javdb_path)

# 清除可能已缓存的错误 utils 模块
if 'utils' in sys.modules:
    # 检查是否是错误的 utils 模块
    cached_utils = sys.modules['utils']
    if hasattr(cached_utils, '__file__') and cached_utils.__file__:
        if 'comic_backend\\utils' in cached_utils.__file__ or 'comic_backend/utils' in cached_utils.__file__:
            del sys.modules['utils']

# 现在导入 javdb_api，它会使用 javdb-api-scraper/utils.py
import javdb_api

from lib.javdb_adapter import JavdbAdapter
from lib.platform import Platform, add_platform_prefix, remove_platform_prefix

__all__ = ['JavdbAdapter', 'Platform', 'add_platform_prefix', 'remove_platform_prefix', 'javdb_api']
