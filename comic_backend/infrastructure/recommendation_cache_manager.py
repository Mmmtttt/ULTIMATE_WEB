"""
推荐页漫画缓存管理器
使用LRU算法管理磁盘缓存
"""
import os
import json
import time
import threading
import re
from typing import Dict, List, Optional, Tuple
from collections import OrderedDict
from infrastructure.logger import app_logger, error_logger
from core.platform import get_platform_from_id, get_original_id, Platform
from core.constants import JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR, RECOMMENDATION_JSON_FILE
from infrastructure.persistence.json_storage import JsonStorage


class RecommendationCacheManager:
    """推荐页漫画缓存管理器
    
    使用LRU算法管理磁盘缓存，自动淘汰最久未访问的漫画
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        cache_dir: str = "data/recommendation_cache",
        max_size_mb: int = 5120,
        cache_index_file: str = "data/meta_data/recommendation_cache_index.json"
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_index_file = cache_index_file
        
        self._cache_lock = threading.Lock()
        self._cache_index: OrderedDict = OrderedDict()
        
        self._ensure_dirs()
        self._load_cache_index()
        self._initialized = True
        
        app_logger.info(f"推荐页缓存管理器初始化完成，最大容量: {max_size_mb}MB")
    
    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(JM_RECOMMENDATION_CACHE_DIR, exist_ok=True)
        os.makedirs(PK_RECOMMENDATION_CACHE_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(self.cache_index_file), exist_ok=True)
    
    def _get_comic_cache_dir(self, comic_id: str) -> str:
        """获取漫画缓存目录"""
        platform = get_platform_from_id(comic_id)
        original_id = get_original_id(comic_id)
        
        if platform == Platform.JM:
            return os.path.join(JM_RECOMMENDATION_CACHE_DIR, original_id)
        elif platform == Platform.PK:
            return self._get_pk_comic_dir(comic_id)
        else:
            error_logger.warning(f"未知的平台类型，漫画ID: {comic_id}，将使用JM作为默认平台")
            return os.path.join(JM_RECOMMENDATION_CACHE_DIR, comic_id)
    
    def _get_pk_comic_dir(self, comic_id: str) -> str:
        """获取PK平台漫画的实际目录"""
        original_id = get_original_id(comic_id)
        
        try:
            storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            db_data = storage.read()
            recommendations = db_data.get("recommendations", [])
            
            author = "unknown"
            title = "unknown"
            
            for rec in recommendations:
                if rec.get("id") == comic_id:
                    author = rec.get("author") or "unknown"
                    title = rec.get("title") or f"漫画_{original_id}"
                    break
            
            comic_dir = os.path.join(PK_RECOMMENDATION_CACHE_DIR, "comics", str(author), str(title))
            
            if os.path.exists(comic_dir):
                return comic_dir
            
            fallback_dir = os.path.join(PK_RECOMMENDATION_CACHE_DIR, original_id)
            return fallback_dir
        except Exception as e:
            error_logger.error(f"解析 PK 推荐页漫画目录失败，使用默认目录结构: {e}")
            return os.path.join(PK_RECOMMENDATION_CACHE_DIR, original_id)
    
    def _load_cache_index(self):
        """加载缓存索引"""
        if os.path.exists(self.cache_index_file):
            try:
                with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("cache_items", []):
                        comic_id = item["comic_id"]
                        self._cache_index[comic_id] = {
                            "size": item["size"],
                            "last_access": item["last_access"],
                            "page_count": item.get("page_count", 0)
                        }
                app_logger.info(f"加载缓存索引完成，共 {len(self._cache_index)} 个缓存项")
            except Exception as e:
                error_logger.error(f"加载缓存索引失败: {e}")
                self._cache_index = OrderedDict()
    
    def _save_cache_index(self):
        """保存缓存索引"""
        try:
            data = {
                "cache_items": [
                    {
                        "comic_id": comic_id,
                        "size": info["size"],
                        "last_access": info["last_access"],
                        "page_count": info.get("page_count", 0)
                    }
                    for comic_id, info in self._cache_index.items()
                ],
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            with open(self.cache_index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            error_logger.error(f"保存缓存索引失败: {e}")
    
    def _calculate_dir_size(self, dir_path: str) -> int:
        """计算目录大小（递归）"""
        if not os.path.exists(dir_path):
            return 0
        total_size = 0
        try:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
        except Exception as e:
            error_logger.error(f"计算目录大小失败: {e}")
        return total_size
    
    def _get_current_cache_size(self) -> int:
        """获取当前缓存总大小"""
        return sum(info["size"] for info in self._cache_index.values())
    
    def _evict_lru(self, required_size: int) -> bool:
        """淘汰最久未使用的缓存
        
        Args:
            required_size: 需要释放的空间大小
            
        Returns:
            是否成功释放足够空间
        """
        freed_size = 0
        
        while freed_size < required_size and self._cache_index:
            oldest_id = next(iter(self._cache_index))
            oldest_info = self._cache_index[oldest_id]
            
            comic_dir = self._get_comic_cache_dir(oldest_id)
            try:
                if os.path.exists(comic_dir):
                    import shutil
                    shutil.rmtree(comic_dir)
                    freed_size += oldest_info["size"]
                    app_logger.info(f"LRU淘汰漫画缓存: {oldest_id}, 释放 {oldest_info['size']} 字节")
            except Exception as e:
                error_logger.error(f"删除缓存目录失败 {oldest_id}: {e}")
            
            del self._cache_index[oldest_id]
        
        self._save_cache_index()
        return freed_size >= required_size
    
    def is_cached(self, comic_id: str) -> bool:
        """检查漫画是否已缓存"""
        with self._cache_lock:
            if comic_id in self._cache_index:
                comic_dir = self._get_comic_cache_dir(comic_id)
                if not os.path.exists(comic_dir):
                    return False
                image_paths = self._get_all_image_paths(comic_dir)
                return len(image_paths) > 0
            return False
    
    def get_cache_info(self, comic_id: str) -> Optional[Dict]:
        """获取漫画缓存信息"""
        with self._cache_lock:
            if comic_id in self._cache_index:
                info = self._cache_index[comic_id].copy()
                info["comic_id"] = comic_id
                return info
            return None
    
    def get_cache_status(self, comic_id: str) -> Dict:
        """获取漫画缓存状态
        
        Args:
            comic_id: 漫画ID
            
        Returns:
            缓存状态字典，包含 is_cached 和 cached_pages
        """
        with self._cache_lock:
            is_cached = comic_id in self._cache_index
            cached_pages = []
            
            if is_cached:
                cached_pages = self.get_cached_pages(comic_id)
            
            return {
                "is_cached": is_cached,
                "cached_pages": cached_pages
            }
    
    def update_access_time(self, comic_id: str):
        """更新访问时间（移到队列末尾）"""
        with self._cache_lock:
            if comic_id in self._cache_index:
                self._cache_index.move_to_end(comic_id)
                self._cache_index[comic_id]["last_access"] = time.time()
                self._save_cache_index()
    
    def add_to_cache(self, comic_id: str, page_count: int = 0) -> bool:
        """将漫画添加到缓存索引
        
        Args:
            comic_id: 漫画ID
            page_count: 页数
            
        Returns:
            是否成功
        """
        with self._cache_lock:
            comic_dir = self._get_comic_cache_dir(comic_id)
            
            if not os.path.exists(comic_dir):
                return False
            
            dir_size = self._calculate_dir_size(comic_dir)
            
            if dir_size == 0:
                return False
            
            current_size = self._get_current_cache_size()
            
            if comic_id in self._cache_index:
                current_size -= self._cache_index[comic_id]["size"]
            
            if current_size + dir_size > self.max_size_bytes:
                required_size = (current_size + dir_size) - self.max_size_bytes
                if not self._evict_lru(required_size):
                    error_logger.warning(f"无法释放足够空间缓存漫画 {comic_id}")
                    return False
            
            if comic_id in self._cache_index:
                del self._cache_index[comic_id]
            
            self._cache_index[comic_id] = {
                "size": dir_size,
                "last_access": time.time(),
                "page_count": page_count
            }
            
            self._save_cache_index()
            app_logger.info(f"添加漫画到缓存: {comic_id}, 大小: {dir_size} 字节, 页数: {page_count}")
            return True
    
    def remove_from_cache(self, comic_id: str) -> bool:
        """从缓存中移除漫画
        
        Args:
            comic_id: 漫画ID
            
        Returns:
            是否成功
        """
        with self._cache_lock:
            comic_dir = self._get_comic_cache_dir(comic_id)
            
            try:
                if os.path.exists(comic_dir):
                    import shutil
                    shutil.rmtree(comic_dir)
                
                if comic_id in self._cache_index:
                    del self._cache_index[comic_id]
                
                self._save_cache_index()
                app_logger.info(f"从缓存移除漫画: {comic_id}")
                return True
            except Exception as e:
                error_logger.error(f"移除缓存失败 {comic_id}: {e}")
                return False
    
    def _natural_sort_paths(self, paths: List[str], base_dir: str) -> List[str]:
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
    
    def _get_all_image_paths(self, comic_dir: str) -> List[str]:
        """获取漫画目录下所有图片路径（递归查找）"""
        if not os.path.exists(comic_dir):
            return []
        
        image_paths = []
        
        for root, _, files in os.walk(comic_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.jpg', '.webp', '.png']:
                    image_paths.append(os.path.join(root, file))
        
        return self._natural_sort_paths(image_paths, comic_dir)
    
    def get_cached_page_path(self, comic_id: str, page_num: int) -> Optional[str]:
        """获取缓存中指定页的路径
        
        Args:
            comic_id: 漫画ID
            page_num: 页码（从1开始）
            
        Returns:
            图片路径或None
        """
        comic_dir = self._get_comic_cache_dir(comic_id)
        image_paths = self._get_all_image_paths(comic_dir)
        
        if 1 <= page_num <= len(image_paths):
            self.update_access_time(comic_id)
            return image_paths[page_num - 1]
        
        return None
    
    def get_cached_pages(self, comic_id: str) -> List[int]:
        """获取缓存中漫画的所有页码
        
        Args:
            comic_id: 漫画ID
            
        Returns:
            页码列表
        """
        comic_dir = self._get_comic_cache_dir(comic_id)
        image_paths = self._get_all_image_paths(comic_dir)
        
        return list(range(1, len(image_paths) + 1))
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        with self._cache_lock:
            total_size = self._get_current_cache_size()
            max_size_mb = self.max_size_bytes / (1024 * 1024)
            used_size_mb = total_size / (1024 * 1024)
            
            return {
                "total_items": len(self._cache_index),
                "total_size_bytes": total_size,
                "total_size_mb": round(used_size_mb, 2),
                "max_size_mb": max_size_mb,
                "usage_percent": round((used_size_mb / max_size_mb) * 100, 2) if max_size_mb > 0 else 0,
                "cache_dir": self.cache_dir
            }
    
    def clear_cache(self) -> Tuple[int, int]:
        """清空所有缓存
        
        Returns:
            (清理的漫画数量, 释放的空间大小)
        """
        with self._cache_lock:
            count = 0
            freed_size = 0
            
            for comic_id, info in self._cache_index.items():
                comic_dir = self._get_comic_cache_dir(comic_id)
                try:
                    if os.path.exists(comic_dir):
                        import shutil
                        shutil.rmtree(comic_dir)
                        count += 1
                        freed_size += info["size"]
                except Exception as e:
                    error_logger.error(f"清理缓存目录失败 {comic_id}: {e}")
            
            self._cache_index.clear()
            self._save_cache_index()
            
            app_logger.info(f"清空缓存完成: 清理 {count} 个漫画, 释放 {freed_size} 字节")
            return count, freed_size
    
    def cleanup_orphaned_files(self) -> int:
        """清理孤立文件（目录存在但索引中没有记录）
        
        Returns:
            清理的文件数量
        """
        with self._cache_lock:
            count = 0
            
            cache_dirs = [JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR]
            
            for cache_dir in cache_dirs:
                if not os.path.exists(cache_dir):
                    continue
                
                for entry in os.scandir(cache_dir):
                    if entry.is_dir():
                        original_id = entry.name
                        if cache_dir == JM_RECOMMENDATION_CACHE_DIR:
                            comic_id_with_prefix = f"JM{original_id}"
                        elif cache_dir == PK_RECOMMENDATION_CACHE_DIR:
                            comic_id_with_prefix = f"PK{original_id}"
                        else:
                            continue
                        
                        if comic_id_with_prefix not in self._cache_index and original_id not in self._cache_index:
                            try:
                                import shutil
                                shutil.rmtree(entry.path)
                                count += 1
                                app_logger.info(f"清理孤立缓存目录: {comic_id_with_prefix}")
                            except Exception as e:
                                error_logger.error(f"清理孤立目录失败 {comic_id_with_prefix}: {e}")
            
            return count
    
    def update_max_size(self, max_size_mb: int):
        """更新最大缓存容量"""
        with self._cache_lock:
            old_size_mb = self.max_size_bytes / (1024 * 1024)
            self.max_size_bytes = max_size_mb * 1024 * 1024
            app_logger.info(f"更新缓存最大容量: {old_size_mb:.0f}MB -> {max_size_mb}MB")
    
    def clean_orphan_cache(self) -> int:
        """清理孤立缓存（外部调用方法）"""
        return self.cleanup_orphaned_files()


recommendation_cache_manager = RecommendationCacheManager()
