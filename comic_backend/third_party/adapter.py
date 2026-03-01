import json
import time
from typing import Dict, List, Any, Optional, Tuple


class MetaDataAdapter:
    """元数据适配器：将第三方 API 格式转换为应用格式"""

    def __init__(self, is_recommendation: bool = False, existing_tags: List[Dict] = None):
        self.is_recommendation = is_recommendation
        self.existing_tags = existing_tags or []

    def parse_meta_data(self, meta_json: Dict[str, Any]) -> Dict[str, Any]:
        """解析元数据并转换为应用格式
        
        Args:
            meta_json: 第三方 API 返回的元数据
            
        Returns:
            转换后的应用格式数据
        """
        albums = meta_json.get("albums", [])
        
        # 根据是否为推荐页选择正确的字段名
        comics_key = "recommendations" if self.is_recommendation else "comics"
        total_key = "total_recommendations" if self.is_recommendation else "total_comics"
        
        result = {
            "collection_name": meta_json.get("collection_name", "我的收藏集"),
            "user": meta_json.get("user", "用户名"),
            total_key: len(albums),
            "last_updated": meta_json.get("last_updated", time.strftime("%Y-%m-%d")),
            "tags": [],
            "lists": [],
            comics_key: [],
            "user_config": {
                "default_page_mode": "left_right",
                "default_background": "dark",
                "auto_hide_toolbar": False,
                "show_page_number": False
            }
        }
        
        # 构建标签映射：名称 -> ID
        # 首先从现有标签构建映射
        tag_name_to_id = {}
        for tag in self.existing_tags:
            tag_name_to_id[tag["name"]] = tag["id"]
        
        # 找出所有新标签
        all_new_tags = set()
        for album in albums:
            tags = album.get("tags", [])
            all_new_tags.update(tags)
        
        # 为新标签分配ID
        existing_ids = {tag["id"] for tag in self.existing_tags}
        new_tag_counter = 1
        
        for tag_name in sorted(all_new_tags):
            if tag_name not in tag_name_to_id:
                # 找一个未使用的ID
                while True:
                    new_id = f"tag_{new_tag_counter:03d}"
                    new_tag_counter += 1
                    if new_id not in existing_ids:
                        break
                
                tag_name_to_id[tag_name] = new_id
                existing_ids.add(new_id)
                result["tags"].append({
                    "id": new_id,
                    "name": tag_name,
                    "create_time": time.strftime("%Y-%m-%dT%H:%M:%S")
                })
        
        # 转换漫画数据
        for album in albums:
            comic = self._convert_album_to_comic(album, tag_name_to_id)
            result[comics_key].append(comic)
        
        return result

    def _convert_album_to_comic(
        self, 
        album: Dict[str, Any], 
        tag_id_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """将单个专辑转换为漫画格式
        
        Args:
            album: 原始专辑数据
            tag_id_map: 标签名到 ID 的映射
            
        Returns:
            漫画对象
        """
        album_id = str(album.get("album_id", ""))
        
        if self.is_recommendation:
            cover_path = album.get("cover_url", "")
        else:
            cover_path = f"/static/cover/{album_id}.jpg"
        
        tag_names = album.get("tags", [])
        tag_ids = [tag_id_map.get(tag) for tag in tag_names if tag in tag_id_map]
        
        return {
            "id": album_id,
            "title": album.get("title", f"漫画_{album_id}"),
            "title_jp": album.get("title_jp", ""),
            "author": album.get("author", ""),
            "desc": "",
            "cover_path": cover_path,
            "total_page": album.get("pages", 0),
            "current_page": 1,
            "score": None,
            "tag_ids": tag_ids,
            "list_ids": [],
            "create_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_read_time": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

    def merge_to_existing(
        self,
        existing_data: Dict[str, Any],
        new_comics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """将新漫画合并到现有数据中
        
        Args:
            existing_data: 现有的数据库数据
            new_comics: 要添加的新漫画列表
            
        Returns:
            合并后的数据
        """
        existing_data = json.loads(json.dumps(existing_data))
        
        existing_data["comics"].extend(new_comics)
        existing_data["total_comics"] = len(existing_data["comics"])
        existing_data["last_updated"] = time.strftime("%Y-%m-%d")
        
        return existing_data


class DuplicateChecker:
    """去重检查器 - 使用 Set 实现 O(1) 时间复杂度查询"""
    
    def __init__(self, existing_ids: List[str]):
        self.existing_ids_set = set(existing_ids)
    
    def is_duplicate(self, comic_id: str) -> bool:
        """检查漫画 ID 是否已存在
        
        Args:
            comic_id: 漫画 ID
            
        Returns:
            是否已存在
        """
        return comic_id in self.existing_ids_set
    
    def filter_duplicates(
        self, 
        comics: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """过滤掉已存在的漫画
        
        Args:
            comics: 漫画列表
            
        Returns:
            (新漫画列表, 已存在的 ID 列表)
        """
        new_comics = []
        existing_ids = []
        
        for comic in comics:
            if comic["id"] in self.existing_ids_set:
                existing_ids.append(comic["id"])
            else:
                new_comics.append(comic)
                self.existing_ids_set.add(comic["id"])
        
        return new_comics, existing_ids


def create_adapter(is_recommendation: bool = False) -> MetaDataAdapter:
    """创建适配器实例
    
    Args:
        is_recommendation: 是否为推荐页
        
    Returns:
        适配器实例
    """
    return MetaDataAdapter(is_recommendation)


def create_duplicate_checker(existing_ids: List[str]) -> DuplicateChecker:
    """创建去重检查器实例
    
    Args:
        existing_ids: 现有的漫画 ID 列表
        
    Returns:
        去重检查器实例
    """
    return DuplicateChecker(existing_ids)
