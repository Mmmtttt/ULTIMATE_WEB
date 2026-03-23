"""
JAVDB API Scraper 包装器
"""

import sys
import os
import re
import json
import importlib.util
from typing import List
import requests
from html import unescape
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from core.constants import THIRD_PARTY_CONFIG_PATH

_javdb_path = os.path.join(os.path.dirname(__file__), 'javdb-api-scraper')
_javdb_utils_path = os.path.abspath(os.path.join(_javdb_path, "utils.py"))

# 确保 javdb-api-scraper 路径在最前面，优先于 comic_backend/utils
if _javdb_path in sys.path:
    sys.path.remove(_javdb_path)
sys.path.insert(0, _javdb_path)

# 确保 `import utils` 始终命中 javdb-api-scraper/utils.py
cached_utils = sys.modules.get('utils')
if cached_utils is not None:
    cached_file = os.path.abspath(str(getattr(cached_utils, '__file__', '') or ''))
    if cached_file != _javdb_utils_path:
        del sys.modules['utils']

if os.path.exists(_javdb_utils_path) and 'utils' not in sys.modules:
    spec = importlib.util.spec_from_file_location('utils', _javdb_utils_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules['utils'] = module

# 现在导入 javdb_api，它会使用 javdb-api-scraper/utils.py
import javdb_api

from lib.javdb_adapter import JavdbAdapter as _JavdbAdapter
from lib.javbus_adapter import JavbusAdapter as _JavbusAdapter
from lib.platform import Platform, add_platform_prefix, remove_platform_prefix


_PREVIEW_VIDEO_EXTENSIONS = (".mp4", ".m3u8", ".webm", ".mov", ".m4v")

_PREVIEW_VIDEO_KEY_PATTERNS = [
    r'["\']?(?:preview_video|previewVideo|preview_url|previewUrl|trailer|trailerUrl|video_url|videoUrl|sampleVideo|sample_url|hlsUrl|hls_url)["\']?\s*[:=]\s*["\']([^"\']+?(?:\.mp4|\.m3u8|\.webm|\.mov|\.m4v)[^"\']*)["\']',
    r'["\']?(?:preview_video|previewVideo|preview_url|previewUrl|trailer|trailerUrl|video_url|videoUrl|sampleVideo|sample_url|hlsUrl|hls_url)["\']?\s*[:=]\s*([^,"\'}\]\s]+?(?:\.mp4|\.m3u8|\.webm|\.mov|\.m4v)[^,"\'}\]\s]*)',
]

_PREVIEW_VIDEO_DIRECT_URL_PATTERNS = [
    r'(https?:\/\/[^"\'\s<>]+?\.(?:mp4|m3u8|webm|mov)(?:\?[^"\'\s<>]*)?)',
    r'(\/\/[^"\'\s<>]+?\.(?:mp4|m3u8|webm|mov)(?:\?[^"\'\s<>]*)?)',
]

_PREVIEW_VIDEO_SELECTORS = [
    'video source',
    'video',
    '.preview-video source',
    '.preview-video video',
    '.video-preview source',
    '.video-preview video',
]

_PREVIEW_VIDEO_ATTRS = ['src', 'data-src', 'data-url', 'data-video', 'data-preview', 'data-hls', 'data-mp4']


def _looks_like_preview_media_url(raw_url: str) -> bool:
    if not raw_url:
        return False

    url = str(raw_url).strip().lower()
    if not url or url.startswith("blob:"):
        return False

    if url.startswith("/api/v1/video/proxy2") or url.startswith("/v1/video/proxy2"):
        return True
    if url.startswith("/proxy2?") or url.startswith("/proxy/"):
        return True

    return any(ext in url for ext in _PREVIEW_VIDEO_EXTENSIONS)


def _load_javdb_cookies_from_third_party_config() -> dict:
    """从 comic_backend/third_party_config.json 读取 JAVDB cookies。"""
    try:
        config_path = THIRD_PARTY_CONFIG_PATH
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


def _normalize_preview_video_url(raw_url: str, base_url: str = "", allow_blob: bool = False) -> str:
    if not raw_url:
        return ""

    url = str(raw_url).strip().strip('"\'')
    if not url:
        return ""

    url = unescape(url).replace("\\/", "/")

    if url.startswith("//"):
        url = f"https:{url}"
    elif base_url and url.startswith("/"):
        url = urljoin(base_url, url)

    if url.lower().startswith("blob:") and not allow_blob:
        return ""

    if not allow_blob and not _looks_like_preview_media_url(url):
        return ""

    return url


def _extract_preview_video_candidates_from_text(text: str) -> List[str]:
    candidates = []
    if not text:
        return candidates

    normalized_text = unescape(text).replace("\\/", "/")
    for pattern in _PREVIEW_VIDEO_KEY_PATTERNS:
        for match in re.finditer(pattern, normalized_text, re.IGNORECASE):
            value = (match.group(1) or "").strip()
            if value:
                candidates.append(value)

    for pattern in _PREVIEW_VIDEO_DIRECT_URL_PATTERNS:
        for match in re.finditer(pattern, normalized_text, re.IGNORECASE):
            value = (match.group(1) or "").strip()
            if value:
                candidates.append(value)

    return candidates


def _extract_preview_video_from_html(html: str, base_url: str = "") -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")
    seen = set()

    def pick(raw_url: str) -> str:
        normalized = _normalize_preview_video_url(raw_url, base_url=base_url)
        if normalized:
            if normalized in seen:
                return ""
            seen.add(normalized)
            return normalized
        return ""

    for selector in _PREVIEW_VIDEO_SELECTORS:
        for node in soup.select(selector):
            for attr in _PREVIEW_VIDEO_ATTRS:
                found = pick(node.get(attr))
                if found:
                    return found

    for node in soup.select("[data-video],[data-src],[data-url],[data-preview],[data-hls],[data-mp4]"):
        for attr in _PREVIEW_VIDEO_ATTRS:
            found = pick(node.get(attr))
            if found:
                return found

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text() or ""
        for candidate in _extract_preview_video_candidates_from_text(script_text):
            found = pick(candidate)
            if found:
                return found

    for candidate in _extract_preview_video_candidates_from_text(html):
        found = pick(candidate)
        if found:
            return found

    return ""


class JavdbAdapter(_JavdbAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            _apply_javdb_cookies(self.api.session)
        except Exception:
            pass

    def _extract_preview_video(self, detail: dict, video_id_hint: str = "") -> str:
        base_url = ""
        try:
            base_url = self.api.base_url
        except Exception:
            base_url = ""

        preview_video = _normalize_preview_video_url(detail.get("preview_video", ""), base_url=base_url)
        if preview_video:
            return preview_video

        video_id = str(detail.get("video_id") or video_id_hint or "").strip()
        if not video_id:
            return ""

        try:
            response = self.api.get(f"/v/{video_id}")
            preview_video = _extract_preview_video_from_html(response.text or "", base_url=base_url)
            return preview_video or ""
        except Exception:
            return ""

    def get_video_detail(self, video_id: str):
        detail = super().get_video_detail(video_id)
        if not detail:
            return detail
        detail["preview_video"] = self._extract_preview_video(detail, video_id)
        return detail

    def get_video_by_code(self, code: str):
        detail = super().get_video_by_code(code)
        if not detail:
            return detail
        detail["preview_video"] = self._extract_preview_video(detail, detail.get("video_id") or code)
        return detail


class JavbusAdapter(_JavbusAdapter):
    BASE_URL = "https://www.javbus.com"

    """鍦ㄥ寘瑁呭眰淇 JavBus 缂╃暐鍥炬贩鏉傞棶棰樸€?"""

    def _extract_preview_video(self, detail: dict, video_id: str, movie_type: str = None) -> str:
        preview_video = _normalize_preview_video_url(
            detail.get("preview_video", ""),
            base_url=self.BASE_URL
        )
        if preview_video:
            return preview_video

        try:
            if movie_type == getattr(self, "TYPE_UNCENSORED", None):
                detail_url = f"{self.BASE_URL}/uncensored/{video_id}"
            else:
                detail_url = f"{self.BASE_URL}/{video_id}"

            response = self._get(detail_url)
            if getattr(response, "status_code", 0) == 200:
                return _extract_preview_video_from_html(response.text or "", base_url=self.BASE_URL) or ""
        except Exception:
            return ""

        return ""

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

        detail["preview_video"] = self._extract_preview_video(detail, video_id, movie_type)
        return detail


__all__ = ['JavdbAdapter', 'JavbusAdapter', 'Platform', 'add_platform_prefix', 'remove_platform_prefix', 'javdb_api']
