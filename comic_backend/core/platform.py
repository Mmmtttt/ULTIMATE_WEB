from enum import Enum
from typing import Tuple, Optional
import os


class Platform(Enum):
    JM = "JM"
    PK = "PK"
    JAVDB = "JAVDB"
    JAVBUS = "JAVBUS"


PLATFORM_PREFIXES = {
    Platform.JM: "JM",
    Platform.PK: "PK",
    Platform.JAVDB: "JAVDB",
    Platform.JAVBUS: "JAVBUS",
}

PLATFORM_NAMES = {
    Platform.JM: "JMComic",
    Platform.PK: "PK",
    Platform.JAVDB: "JAVDB",
    Platform.JAVBUS: "JavBus",
}

PLATFORM_DOWNLOAD_DIRS = {
    Platform.JM: "JM",
    Platform.PK: "PK",
    Platform.JAVDB: "JAVDB",
    Platform.JAVBUS: "JAVBUS",
}

PLATFORM_COVER_URLS = {
    Platform.JM: "https://cdn-msp3.18comic.vip/media/albums/{original_id}.jpg",
    Platform.PK: None,
    Platform.JAVDB: None,
    Platform.JAVBUS: None,
}

PLATFORM_IMAGE_URLS = {
    Platform.JM: "https://cdn-msp.jmapinodeudzn.net/media/photos/{original_id}/{page:05d}.webp",
    Platform.PK: None,
    Platform.JAVDB: None,
    Platform.JAVBUS: None,
}

COMIC_PLATFORMS = [Platform.JM, Platform.PK]
VIDEO_PLATFORMS = [Platform.JAVDB, Platform.JAVBUS]


def add_platform_prefix(platform: Platform, original_id: str) -> str:
    if not platform or not original_id:
        return original_id
    
    prefix = PLATFORM_PREFIXES.get(platform, "")
    if not prefix:
        return original_id
    
    if original_id.startswith(prefix):
        return original_id
    
    return f"{prefix}{original_id}"


def remove_platform_prefix(comic_id: str) -> Tuple[Optional[Platform], str]:
    if not comic_id:
        return None, comic_id
    
    for platform, prefix in PLATFORM_PREFIXES.items():
        if comic_id.startswith(prefix):
            original_id = comic_id[len(prefix):]
            return platform, original_id
    
    return None, comic_id


def get_platform_from_id(comic_id: str) -> Optional[Platform]:
    platform, _ = remove_platform_prefix(comic_id)
    return platform


def get_original_id(comic_id: str) -> str:
    _, original_id = remove_platform_prefix(comic_id)
    return original_id


def get_platform_download_dir(platform: Platform, base_dir: str) -> str:
    platform_dir = PLATFORM_DOWNLOAD_DIRS.get(platform, "")
    if platform_dir:
        return os.path.join(base_dir, platform_dir)
    return base_dir


def get_platform_cover_url(platform: Platform, original_id: str) -> Optional[str]:
    url_template = PLATFORM_COVER_URLS.get(platform)
    if url_template:
        return url_template.format(original_id=original_id)
    return None


def get_platform_image_url(platform: Platform, original_id: str, page: int) -> Optional[str]:
    url_template = PLATFORM_IMAGE_URLS.get(platform)
    if url_template:
        return url_template.format(original_id=original_id, page=page)
    return None


def is_platform_supported(platform_name: str) -> bool:
    try:
        Platform(platform_name.upper())
        return True
    except ValueError:
        return False


def get_supported_platforms() -> list:
    return [p.value for p in Platform]


def get_comic_platforms() -> list:
    return [p.value for p in COMIC_PLATFORMS]


def get_video_platforms() -> list:
    return [p.value for p in VIDEO_PLATFORMS]


def is_comic_platform(platform_name: str) -> bool:
    return platform_name.upper() in [p.value for p in COMIC_PLATFORMS]


def is_video_platform(platform_name: str) -> bool:
    return platform_name.upper() in [p.value for p in VIDEO_PLATFORMS]
