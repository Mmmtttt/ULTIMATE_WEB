"""
适配器基类
定义所有适配器必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from .platform import Platform


class BaseAdapter(ABC):
    """
    适配器基类
    
    所有第三方平台适配器必须继承此类并实现所有抽象方法
    """
    
    def __init__(self, existing_tags: List[Dict] = None):
        """
        初始化适配器
        
        Args:
            existing_tags: 已有的标签列表，用于标签去重
        """
        self.existing_tags = existing_tags or []
        self.platform: Platform = None  # 子类必须设置
    
    @abstractmethod
    def get_platform(self) -> Platform:
        """
        返回平台类型
        
        Returns:
            平台枚举
        """
        pass
    
    @abstractmethod
    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        搜索视频
        
        Args:
            keyword: 搜索关键词（番号、标题、演员等）
            page: 起始页码（从1开始）
            max_pages: 最大搜索页数
            
        Returns:
            {
                'page': 当前页码,
                'has_next': 是否有下一页,
                'total_pages': 总页数（如果知道）,
                'videos': 视频列表，每个视频包含以下字段：
                    - video_id: 原始平台ID（字符串）
                    - code: 番号
                    - title: 标题
                    - date: 发布日期
                    - tags: 标签名称列表
                    - actors: 演员列表
                    - cover_url: 封面图片URL
                    - rating: 评分
            }
        """
        pass
    
    @abstractmethod
    def get_video_detail(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        获取视频详情
        
        Args:
            video_id: 视频原始ID
            
        Returns:
            视频详情字典，包含：
            - video_id: 原始ID
            - code: 番号
            - title: 标题
            - date: 发布日期
            - tags: 标签名称列表
            - actors: 演员列表
            - series: 系列
            - magnets: 磁力链接列表
            - thumbnail_images: 缩略图URL列表
            - preview_video: 预览视频URL
            - cover_url: 封面URL
        """
        pass
    
    @abstractmethod
    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        """
        搜索演员
        
        Args:
            actor_name: 演员名字
            
        Returns:
            演员列表，每个演员包含：
            - actor_name: 演员名
            - actor_id: 演员ID
            - actor_url: 演员页面URL
        """
        pass
    
    @abstractmethod
    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取演员作品
        
        Args:
            actor_id: 演员ID
            page: 起始页码（从1开始）
            max_pages: 最大页数
            
        Returns:
            {
                'page': 当前页码,
                'has_next': 是否有下一页,
                'works': 作品列表
            }
        """
        pass
    
    @abstractmethod
    def get_tag_works(self, tag_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取标签作品
        
        Args:
            tag_id: 标签ID
            page: 起始页码（从1开始）
            max_pages: 最大页数
            
        Returns:
            {
                'page': 当前页码,
                'has_next': 是否有下一页,
                'works': 作品列表
            }
        """
        pass
    
    @abstractmethod
    def download_video_images(self, video_id: str, download_dir: str) -> Tuple[int, int]:
        """
        下载视频缩略图到本地
        
        Args:
            video_id: 视频ID
            download_dir: 下载目录
            
        Returns:
            (成功下载数, 总数)
        """
        pass
    
    @abstractmethod
    def convert_to_standard_format(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        将平台数据转换为系统标准格式
        
        这是核心转换方法，必须正确实现！
        
        Args:
            videos: 平台原始数据列表
            
        Returns:
            {
                "videos": [...],  # 视频列表
                "tags": [...]     # 标签列表
            }
        """
        pass
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    def _convert_videos_to_standard(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        通用视频数据转换方法
        
        Args:
            videos: 视频数据列表
            
        Returns:
            标准格式的视频和标签数据
        """
        # 标签去重和ID生成
        tag_name_to_id = {}
        tag_id_counter = 1
        
        # 处理已有标签
        for tag in self.existing_tags:
            tag_name_to_id[tag["name"]] = tag["id"]
        
        new_tags = []
        standard_videos = []
        
        for video in videos:
            # 处理标签
            video_tag_ids = []
            for tag_name in video.get("tags", []):
                if tag_name not in tag_name_to_id:
                    # 新标签
                    tag_id = f"tag_{tag_id_counter:03d}"
                    tag_name_to_id[tag_name] = tag_id
                    new_tags.append({
                        "id": tag_id,
                        "name": tag_name,
                        "create_time": self._get_current_time()
                    })
                    tag_id_counter += 1
                video_tag_ids.append(tag_name_to_id[tag_name])
            
            # 处理演员标签
            for actor_name in video.get("actors", []):
                if actor_name not in tag_name_to_id:
                    tag_id = f"actor_{tag_id_counter:03d}"
                    tag_name_to_id[actor_name] = tag_id
                    new_tags.append({
                        "id": tag_id,
                        "name": actor_name,
                        "type": "actor",
                        "create_time": self._get_current_time()
                    })
                    tag_id_counter += 1
                video_tag_ids.append(tag_name_to_id[actor_name])
            
            # 构建标准视频格式
            from .platform import add_platform_prefix
            
            standard_video = {
                "id": add_platform_prefix(self.platform, video["video_id"]),
                "video_id": video["video_id"],
                "code": video.get("code", ""),
                "title": video.get("title", ""),
                "date": video.get("date", ""),
                "cover_path": video.get("cover_url", ""),
                "thumbnail_images": video.get("thumbnail_images", []),
                "magnets": video.get("magnets", []),
                "actors": video.get("actors", []),
                "series": video.get("series", ""),
                "rating": video.get("rating", None),
                "tag_ids": video_tag_ids,
                "create_time": self._get_current_time(),
                "last_read_time": self._get_current_time(),
                "is_deleted": False
            }
            standard_videos.append(standard_video)
        
        return {
            "videos": standard_videos,
            "tags": new_tags
        }
