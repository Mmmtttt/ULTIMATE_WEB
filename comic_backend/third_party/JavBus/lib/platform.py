"""
平台枚举和ID处理
"""

from enum import Enum
from typing import Optional, Tuple


class Platform(Enum):
    """平台枚举"""
    JAVDB = "JAVDB"      # JAVDB平台
    JAVBUS = "JAVBUS"    # JavBus平台


# 平台前缀映射
PLATFORM_PREFIXES = {
    Platform.JAVDB: "JAVDB",
    Platform.JAVBUS: "JAVBUS",
}

# 平台名称映射（用于显示）
PLATFORM_NAMES = {
    Platform.JAVDB: "JAVDB",
    Platform.JAVBUS: "JavBus",
}


def get_platform_by_name(name: str) -> Optional[Platform]:
    """根据名称获取平台枚举"""
    name = name.upper()
    for platform in Platform:
        if platform.value == name:
            return platform
    return None


def add_platform_prefix(platform: Platform, video_id: str) -> str:
    """
    为视频ID添加平台前缀
    
    Args:
        platform: 平台类型
        video_id: 原始视频ID
        
    Returns:
        带前缀的视频ID，如 JAVDB_YwG8Ve
    """
    prefix = PLATFORM_PREFIXES.get(platform, platform.value)
    return f"{prefix}_{video_id}"


def remove_platform_prefix(prefixed_id: str) -> Tuple[Platform, str]:
    """
    从带前缀的ID中提取平台和原始ID
    
    Args:
        prefixed_id: 带前缀的ID，如 JAVDB_YwG8Ve
        
    Returns:
        (平台枚举, 原始ID)
    """
    parts = prefixed_id.split('_', 1)
    if len(parts) != 2:
        raise ValueError(f"无效的ID格式: {prefixed_id}")
    
    platform_name, video_id = parts
    platform = get_platform_by_name(platform_name)
    
    if platform is None:
        raise ValueError(f"未知的平台: {platform_name}")
    
    return platform, video_id


def get_platform_image_url(platform: Platform, video_id: str, index: int) -> Optional[str]:
    """
    获取指定平台的图片在线URL
    
    Args:
        platform: 平台类型
        video_id: 视频ID
        index: 图片索引
        
    Returns:
        图片URL或None
    """
    if platform == Platform.JAVDB:
        # JAVDB的缩略图URL格式
        return f"https://c0.jdbstatic.com/samples/{video_id[:2].lower()}/{video_id}_l_{index}.jpg"
    return None
