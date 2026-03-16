"""
JAVDB API Scraper 包装器
"""

import sys
import os
import re
import json
from typing import List
import requests

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

from lib.javdb_adapter import JavdbAdapter as _JavdbAdapter
from lib.javbus_adapter import JavbusAdapter as _JavbusAdapter
from lib.platform import Platform, add_platform_prefix, remove_platform_prefix


def _load_javdb_cookies_from_third_party_config() -> dict:
    """从 comic_backend/third_party_config.json 读取 JAVDB cookies。"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'third_party_config.json')
        if not os.path.exists(config_path):
            return {}

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        cookies = (
            config_data.get('adapters', {})
            .get('javdb', {})
            .get('cookies', {})
        )

        if not isinstance(cookies, dict):
            return {}

        normalized = {}
        for key, value in cookies.items():
            key_str = str(key or '').strip()
            if not key_str:
                continue
            normalized[key_str] = str(value or '')

        return normalized
    except Exception:
        return {}


def _apply_javdb_cookies(session) -> int:
    """将 third_party_config.json 中的 JAVDB cookies 写入当前 session。"""
    cookies = _load_javdb_cookies_from_third_party_config()
    if not cookies:
        return 0

    for key, value in cookies.items():
        session.cookies.set(key, value)

    return len(cookies)


def _sanitize_javbus_thumbnails(urls: List[str]) -> List[str]:
    valid_urls = [url for url in (urls or []) if url]
    if not valid_urls:
        return []

    # 优先保留高清图（通常不是 javbus sample 域名路径）
    high_quality = [url for url in valid_urls if "javbus.com/pics/sample/" not in url.lower()]
    selected = high_quality if high_quality else valid_urls

    deduplicated = []
    seen = set()
    for url in selected:
        if url in seen:
            continue
        seen.add(url)
        deduplicated.append(url)
    return deduplicated


def _is_valid_dmm_image(url: str) -> bool:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8
        )
        if response.status_code != 200:
            return False
        content_type = (response.headers.get("content-type", "") or "").lower()
        if "image" not in content_type:
            return False
        # DMM 的占位图通常很小，避免误判
        if len(response.content) < 10_000:
            return False
        return True
    except Exception:
        return False


def _guess_dmm_thumbnails_from_code(code: str, count: int) -> List[str]:
    normalized_code = (code or "").strip().upper()
    matched = re.match(r"^([A-Z]+)-?(\d+)$", normalized_code)
    if not matched or count <= 0:
        return []

    prefix = matched.group(1).lower()
    number = matched.group(2).zfill(5)
    stems = [
        f"{prefix}{number}",
        f"1{prefix}{number}",
    ]

    for stem in stems:
        first_url = f"https://pics.dmm.co.jp/digital/video/{stem}/{stem}jp-1.jpg"
        if _is_valid_dmm_image(first_url):
            return [
                f"https://pics.dmm.co.jp/digital/video/{stem}/{stem}jp-{idx}.jpg"
                for idx in range(1, count + 1)
            ]

    return []


class JavdbAdapter(_JavdbAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            _apply_javdb_cookies(self.api.session)
        except Exception:
            pass


class JavbusAdapter(_JavbusAdapter):
    """在包装层修正 JavBus 缩略图混杂问题。"""

    def get_video_detail(self, video_id: str, movie_type: str = None):
        detail = super().get_video_detail(video_id, movie_type=movie_type)
        if not detail:
            return detail

        detail["thumbnail_images"] = _sanitize_javbus_thumbnails(detail.get("thumbnail_images", []))
        thumbnails = detail.get("thumbnail_images", [])
        if thumbnails and all("javbus.com/pics/sample/" in thumb.lower() for thumb in thumbnails):
            guessed_dmm = _guess_dmm_thumbnails_from_code(detail.get("code") or video_id, len(thumbnails))
            if guessed_dmm:
                detail["thumbnail_images"] = guessed_dmm
                if (not detail.get("cover_url")) or ("javbus.com/pics/" in str(detail.get("cover_url", "")).lower()):
                    detail["cover_url"] = guessed_dmm[0]

        if not detail.get("cover_url") and detail["thumbnail_images"]:
            detail["cover_url"] = detail["thumbnail_images"][0]
        return detail


__all__ = ['JavdbAdapter', 'JavbusAdapter', 'Platform', 'add_platform_prefix', 'remove_platform_prefix', 'javdb_api']
