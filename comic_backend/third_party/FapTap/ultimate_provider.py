"""FapTap.net 协议化适配器（公开 JSON API 模式）。

FapTap 是基于自托管后端的视频聚合站，提供无需鉴权的公开 REST API：
  - GET /api/videos?page=&limit=&q=    视频列表/搜索
  - GET /api/videos/{id}              视频详情
  - GET /api/tags                     标签体系

视频资源托管在 Bunny CDN（vz-*.b-cdn.net），封面/预览图均为完整 URL。
"""
from __future__ import annotations

import base64
import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode

import requests

from protocol.base import ProtocolProvider


FAPTAP_CONFIG_KEY = "faptap"
FAPTAP_PLUGIN_ID = "video.faptap"
FAPTAP_PLATFORM = "FapTap"
FAPTAP_HOST_ID_PREFIX = "FAPTAP"

DEFAULT_DOMAIN = "https://faptap.net"
# Bunny Stream CDN 默认主机（FapTap 所有视频共用同一 library）
DEFAULT_CDN_HOST = "https://vz-3d77bc0a-a87.b-cdn.net"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# FapTap API 固定每页返回 42 条（limit 参数被忽略）
FAPTAP_API_PAGE_SIZE = 42


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, default: int, minimum: int = 1, maximum: int = 10000) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    if parsed < minimum:
        return minimum
    if parsed > maximum:
        return maximum
    return parsed


def _normalize_domain(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    return text or DEFAULT_DOMAIN


def _strip_html(text: Any) -> str:
    """去除 HTML 标签并反转义实体，用于 description 字段清洗。"""
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(cleaned).strip()


def _abs_url(url: str, domain: str) -> str:
    """将相对路径转为绝对 URL。"""
    if not url:
        return url
    url = url.strip()
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://") or url.startswith("//"):
        return url
    if url.startswith("/"):
        return f"{domain.rstrip('/')}{url}"
    return f"{domain.rstrip('/')}/{url}"


class FapTapProvider(ProtocolProvider):
    """FapTap.net 协议化适配器（公开 JSON API）。

    FapTap 后端暴露了无需鉴权的 REST API，可直接通过 HTTP 请求获取
    视频列表、详情和标签体系。视频封面/预览托管在 Bunny CDN。
    """

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(payload or {})
        normalized: Dict[str, Any] = {}
        normalized["enabled"] = _as_bool(raw.get("enabled"), True)
        normalized["domain"] = _normalize_domain(raw.get("domain"))
        cdn_host_raw = str(raw.get("cdn_host") or "").strip().rstrip("/")
        normalized["cdn_host"] = cdn_host_raw or DEFAULT_CDN_HOST
        normalized["timeout_seconds"] = _as_int(
            raw.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600
        )
        normalized["proxy"] = str(raw.get("proxy") or "").strip()
        normalized["user_agent"] = (
            str(raw.get("user_agent") or "").strip() or DEFAULT_USER_AGENT
        )
        return normalized

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        public = dict(normalized)
        public["proxy_configured"] = bool(
            str((config or {}).get("proxy") or "").strip()
        )
        return public

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_config(config)
        enabled = _as_bool(normalized.get("enabled"), True)
        domain = str(normalized.get("domain") or "").strip()
        configured = bool(enabled and domain)
        return {
            "configured": configured,
            "message": "" if configured else "FapTap 未启用或站点域名未配置。",
            "missing_fields": [] if domain else ["domain"],
        }

    # ---------- 内部工具 ----------

    def _build_session(self, config: Dict[str, Any]) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": str(config.get("user_agent") or DEFAULT_USER_AGENT),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": str(config.get("domain") or DEFAULT_DOMAIN).rstrip("/") + "/",
            "DNT": "1",
        })
        proxy = str(config.get("proxy") or "").strip()
        if proxy:
            session.proxies.update({"http": proxy, "https": proxy})
        return session

    def _domain(self, config: Dict[str, Any]) -> str:
        return str(config.get("domain") or DEFAULT_DOMAIN).rstrip("/")

    def _api_get(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """发送 GET 请求并返回 JSON。

        返回顶层 JSON 对象（含 ci_environment/data 字段）。
        404 返回 None；鉴权失败或其它错误抛 RuntimeError。
        """
        base_url = self._domain(config)
        url = f"{base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        timeout = _as_int(
            config.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600
        )
        response = session.get(url, timeout=timeout, allow_redirects=True)
        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise RuntimeError(
                f"faptap 鉴权失败 ({response.status_code})，公开 API 通常无需凭据，"
                f"请检查代理或域名配置。"
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"faptap 请求失败: {response.status_code} {response.reason}"
            )
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"faptap 响应解析失败: {exc}") from exc

    # ---------- 协议入口 ----------

    def execute(
        self,
        capability: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Any:
        normalized = self.normalize_config(config)
        if not _as_bool(normalized.get("enabled"), True):
            raise RuntimeError("FapTap 插件未启用。")

        if capability == "health.query.status":
            return self.get_query_status(config)

        session = self._build_session(normalized)

        if capability == "catalog.search":
            return self._handle_search(session, normalized, params)
        if capability == "catalog.detail":
            return self._handle_detail(session, normalized, params)
        if capability == "taxonomy.tags":
            return self._handle_tags(session, normalized, params)
        if capability == "playback.sources.build":
            return self._handle_build_sources(session, normalized, params)
        if capability == "playback.proxy.url":
            return self._handle_proxy_url(session, normalized, params)

        raise ValueError(f"不支持的能力: {capability}")

    # ---------- 能力实现 ----------

    def _handle_search(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 catalog.search — 调用 /api/videos 获取视频列表。

        FapTap API 的 limit 参数被忽略，固定每页返回 FAPTAP_API_PAGE_SIZE 条。
        关键词搜索通过 q 参数实现，分页通过 page 参数实现。
        """
        keyword = str(
            params.get("keyword") or params.get("query") or ""
        ).strip()
        page = _as_int(params.get("page"), 1, 1, 10000)

        # limit 参数被 API 忽略，但仍传递给宿主用于返回结构对齐
        requested_limit = _as_int(
            params.get("limit") or params.get("per_page"),
            FAPTAP_API_PAGE_SIZE, 1, 100,
        )

        api_params: Dict[str, Any] = {"page": page}
        if keyword:
            api_params["q"] = keyword

        payload = self._api_get(session, config, "/api/videos", params=api_params)
        if payload is None:
            return {
                "page": page,
                "has_next": False,
                "total": 0,
                "videos": [],
                "keyword": keyword,
            }

        data = dict(payload.get("data") or {})
        total = _as_int(data.get("total"), 0, 0, 10**9)
        raw_videos = data.get("videos") or []
        if not isinstance(raw_videos, list):
            raw_videos = []

        domain = self._domain(config)
        videos = [
            self._to_video_summary(dict(item), domain)
            for item in raw_videos
            if isinstance(item, dict)
        ]

        # API 固定页大小为 FAPTAP_API_PAGE_SIZE，has_next 基于此计算
        has_next = len(videos) > 0 and (page * FAPTAP_API_PAGE_SIZE) < total
        total_pages = (
            (total + FAPTAP_API_PAGE_SIZE - 1) // FAPTAP_API_PAGE_SIZE
            if FAPTAP_API_PAGE_SIZE > 0 else 0
        )

        return {
            "page": page,
            "per_page": requested_limit,
            "has_next": has_next,
            "total": total,
            "total_pages": total_pages,
            "videos": videos,
            "keyword": keyword,
        }

    def _handle_detail(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 catalog.detail — 调用 /api/videos/{id} 获取视频详情。

        兼容 host_id 前缀（FAPTAP1234 -> 1234）。
        """
        video_id = str(
            params.get("video_id") or params.get("id") or ""
        ).strip()
        if not video_id:
            raise RuntimeError("catalog.detail 缺少 video_id 参数。")

        # 移除 host_id 前缀
        raw_id = video_id
        prefix_upper = FAPTAP_HOST_ID_PREFIX.upper()
        if raw_id.upper().startswith(prefix_upper):
            raw_id = raw_id[len(prefix_upper):]

        payload = self._api_get(session, config, f"/api/videos/{raw_id}")
        if payload is None:
            return {"videos": [], "found": False, "video_id": video_id}

        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            return {"videos": [], "found": False, "video_id": video_id}

        domain = self._domain(config)
        detail = self._to_video_detail(data, domain)
        return {"videos": [detail]}

    def _handle_tags(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 taxonomy.tags — 调用 /api/tags 获取标签体系。

        FapTap 的标签是扁平结构（无 type 分类），统一归入 "tag" 分类。
        支持 keyword 前缀过滤和 category 过滤（client 端过滤）。
        """
        keyword = str(params.get("keyword") or "").strip().lower()
        category = str(params.get("category") or "").strip().lower()

        payload = self._api_get(session, config, "/api/tags")
        if payload is None:
            return {"tags": [], "categories": []}

        data = dict(payload.get("data") or {})
        raw_tags = data.get("tags") or []
        if not isinstance(raw_tags, list):
            raw_tags = []

        normalized: List[Dict[str, Any]] = []
        for item in raw_tags:
            if not isinstance(item, dict):
                continue
            tag_name = str(item.get("name") or "").strip()
            if not tag_name:
                continue
            tag_category = "tag"
            # 关键词过滤（前缀或包含匹配）
            if keyword and keyword not in tag_name.lower():
                continue
            # 分类过滤：FapTap 标签均属 "tag" 分类
            if category and tag_category != category:
                continue
            normalized.append({
                "id": str(item.get("id") or ""),
                "name": tag_name,
                "slug": str(item.get("slug") or "").strip(),
                "count": 0,
                "category": tag_category,
            })

        categories = [
            {
                "key": "tag",
                "name": "Tag",
                "count": len(normalized),
            }
        ]

        return {"tags": normalized, "categories": categories}

    # ---------- 播放源构建 ----------

    def _cdn_host(self, config: Dict[str, Any]) -> str:
        return str(config.get("cdn_host") or DEFAULT_CDN_HOST).rstrip("/")

    def _extract_stream_uuid(self, stream_url: str) -> str:
        """从 stream_url_selfhosted 提取 Bunny CDN 视频 UUID。

        支持两种格式：
        - 完整 iframe URL: https://iframe.mediadelivery.net/play/337385/{uuid}
        - 裸 UUID: f0578e23-8159-41bc-a0ff-b91138f018ac
        """
        text = str(stream_url or "").strip()
        if not text:
            return ""
        # 裸 UUID 格式（8-4-4-4-12）
        uuid_match = re.search(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            text, re.IGNORECASE
        )
        if uuid_match:
            return uuid_match.group()
        return ""

    def _fetch_iframe_sources(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        iframe_url: str,
    ) -> Dict[str, str]:
        """抓取 iframe /play/ 页面 HTML，提取 HLS 和 MP4 直链。

        iframe 页面的 meta 标签和 <source> 标签包含真实的 CDN 流地址：
        - og:video:url → MP4 直链
        - <source type="application/vnd.apple.mpegURL"> → HLS playlist
        """
        if not iframe_url:
            return {}
        timeout = _as_int(
            config.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600
        )
        try:
            resp = session.get(iframe_url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200 or not resp.text:
                return {}
        except Exception:
            return {}

        html_text = resp.text
        sources: Dict[str, str] = {}

        # 提取 HLS playlist URL（来自 <source> 标签的 src 属性）
        # 同时匹配 src 在 type 前或后的两种顺序
        hls_match = re.search(
            r'<source[^>]*type=["\']application/vnd\.apple\.mpegURL["\'][^>]*src=["\']([^"\']+)["\']',
            html_text, re.IGNORECASE
        )
        if not hls_match:
            hls_match = re.search(
                r'<source[^>]*src=["\']([^"\']+playlist\.m3u8)["\']',
                html_text, re.IGNORECASE
            )
        if hls_match:
            sources["hls"] = hls_match.group(1).strip()
        else:
            # 回退：从任意 CDN URL 提取主机，构造 HLS URL
            cdn_url_match = re.search(
                r'(https?://vz-[a-z0-9-]+\.b-cdn\.net/[0-9a-f-]+/)',
                html_text, re.IGNORECASE
            )
            if cdn_url_match:
                sources["hls"] = f"{cdn_url_match.group(1)}playlist.m3u8"

        # 提取 MP4 直链（来自 og:video:url meta 标签）
        # HTML 中 content 属性可能在 property 之前或之后，两种顺序都匹配
        mp4_match = re.search(
            r'property=["\']og:video(?:\:url|\:secure_url)?["\'][^>]*content=["\']([^"\']+\.mp4)["\']',
            html_text, re.IGNORECASE
        )
        if not mp4_match:
            mp4_match = re.search(
                r'content=["\']([^"\']+play_\d+p\.mp4)["\'][^>]*property=["\']og:video',
                html_text, re.IGNORECASE
            )
        if not mp4_match:
            # 最终回退：匹配任意 play_Np.mp4 URL
            mp4_match = re.search(
                r'content=["\']([^"\']+play_\d+p\.mp4)["\']',
                html_text, re.IGNORECASE
            )
        if mp4_match:
            sources["mp4"] = mp4_match.group(1).strip()

        # 提取缩略图 URL（来自 og:image meta 标签）
        # 同时匹配 property 在前或在后的两种顺序
        thumb_match = re.search(
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            html_text, re.IGNORECASE
        )
        if not thumb_match:
            thumb_match = re.search(
                r'content=["\']([^"\']+thumbnail\.jpg)["\'][^>]*property=["\']og:image',
                html_text, re.IGNORECASE
            )
        if not thumb_match:
            # 最终回退：匹配任意含 thumbnail.jpg 的 content
            thumb_match = re.search(
                r'content=["\']([^"\']+thumbnail\.jpg)["\']',
                html_text, re.IGNORECASE
            )
        if thumb_match:
            sources["thumbnail"] = thumb_match.group(1).strip()

        return sources

    def _handle_build_sources(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """处理 playback.sources.build — 构建视频播放源列表。

        流程：
        1. 调用详情 API 获取 stream_url_selfhosted（iframe 地址）
        2. 从 iframe 地址提取 Bunny CDN 视频 UUID
        3. 抓取 iframe /play/ 页面 HTML，提取 HLS 和 MP4 直链
        4. 若 iframe 抓取失败，用 cdn_host 配置直接构造 URL 作为回退
        5. 返回标准化的播放源列表（HLS 主源 + MP4 回退源）
        """
        video_id = str(
            params.get("code") or params.get("video_id") or params.get("id") or ""
        ).strip()
        if not video_id:
            return []

        # 移除 host_id 前缀
        raw_id = video_id
        prefix_upper = FAPTAP_HOST_ID_PREFIX.upper()
        if raw_id.upper().startswith(prefix_upper):
            raw_id = raw_id[len(prefix_upper):]

        # 调用详情 API 获取 iframe URL
        payload = self._api_get(session, config, f"/api/videos/{raw_id}")
        if payload is None:
            return []

        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            return []

        stream_url = str(data.get("stream_url_selfhosted") or "").strip()
        video_uuid = self._extract_stream_uuid(stream_url)
        if not video_uuid:
            return []

        cdn_host = self._cdn_host(config)

        # 抓取 iframe HTML 提取真实流地址（best-effort）
        iframe_sources = self._fetch_iframe_sources(session, config, stream_url)

        # HLS 直链：优先从 iframe HTML 提取，回退到构造 URL
        hls_url = iframe_sources.get("hls") or f"{cdn_host}/{video_uuid}/playlist.m3u8"

        # MP4 直链：优先从 iframe HTML 提取，回退到 play_240p.mp4
        mp4_url = iframe_sources.get("mp4") or f"{cdn_host}/{video_uuid}/play_240p.mp4"

        # 缩略图：优先从 iframe HTML 提取，回退到构造 URL
        poster_url = (
            iframe_sources.get("thumbnail")
            or f"{cdn_host}/{video_uuid}/thumbnail.jpg"
        )

        # 从 MP4 文件名提取质量标签（如 play_240p.mp4 → 240p）
        mp4_quality = "240p"
        quality_match = re.search(r'play_(\d+p)\.mp4', mp4_url, re.IGNORECASE)
        if quality_match:
            mp4_quality = quality_match.group(1)

        sources: List[Dict[str, Any]] = []

        # 主源：MP4 渐进式下载（通过后端代理，浏览器可直接播放）
        # Bunny CDN 虽有 CORS 头，但 hls.js 加载 HLS 直链时仍可能因
        # 浏览器安全策略失败；MP4 代理流更可靠，且支持 Range 寻址。
        proxy_mp4_url = self._to_proxy_video_url(mp4_url)
        sources.append({
            "key": "faptap_mp4",
            "name": f"FapTap MP4 {mp4_quality}",
            "available": True,
            "type": "direct",
            "source": FAPTAP_PLATFORM,
            "poster": poster_url,
            "streams": [
                {
                    "resolution": mp4_quality,
                    "url": proxy_mp4_url,
                    "type": "direct",
                    "source": FAPTAP_PLATFORM,
                }
            ],
        })

        # 备用源：HLS 自适应流（直连 CDN，部分浏览器可原生播放）
        # 注意：此源会被 _build_play_sources 按 source 去重，
        # 仅在 MP4 源被排除时作为回退。
        sources.append({
            "key": "faptap_hls",
            "name": f"FapTap HLS",
            "available": True,
            "type": "hls",
            "source": FAPTAP_PLATFORM,
            "poster": poster_url,
            "streams": [
                {
                    "resolution": "auto",
                    "url": hls_url,
                    "type": "hls",
                    "source": FAPTAP_PLATFORM,
                }
            ],
        })

        return sources

    def _to_proxy_video_url(self, url: str) -> str:
        """将 Bunny CDN 视频 URL 包装为后端代理 URL。

        浏览器直接加载 b-cdn.net 的 MP4 时可能因安全策略失败，
        通过后端 /api/v1/video/proxy2 代理转发可确保可靠播放，
        并支持 Range 请求（视频寻址）。
        """
        if not url:
            return ""
        # 只对 Bunny CDN 和 mediadelivery.net 域名包装
        lowered = url.lower()
        if "b-cdn.net" not in lowered and "mediadelivery.net" not in lowered:
            return url
        try:
            encoded = base64.b64encode(url.encode("utf-8")).decode("utf-8")
            return f"/api/v1/video/proxy2?url={encoded}"
        except Exception:
            return url

    # ---------- 资源代理 ----------

    def _handle_proxy_url(
        self,
        session: requests.Session,
        config: Dict[str, Any],
        params: Dict[str, Any],
    ):
        """处理 playback.proxy.url — 代理 faptap.net / b-cdn.net 图片与资源请求。

        代理端点 /api/v1/video/proxy2 会以流式方式读取响应体，
        因此必须用 stream=True 发起请求，否则 iter_content 会抛
        "stream mode is not enabled"。
        """
        method = str(params.get("method") or "GET").upper()
        query_string = str(params.get("query_string") or "").strip()
        body_url = str(params.get("body_url") or "").strip()
        incoming_headers = dict(params.get("incoming_headers") or {})

        # 优先取 body_url，其次从 query_string 中解码 base64 编码的 url 参数
        target_url = body_url
        if not target_url and query_string:
            parsed = parse_qs(query_string)
            url_param = parsed.get("url", [])
            if url_param:
                encoded = url_param[0]
                try:
                    target_url = base64.b64decode(encoded).decode("utf-8")
                except Exception:
                    target_url = encoded

        if not target_url:
            raise ValueError("proxy.url: missing target URL")

        timeout = _as_int(config.get("timeout_seconds"), DEFAULT_TIMEOUT_SECONDS, 1, 600)

        # 透传 Range 头以支持分段请求（视频/图片渐进加载）
        req_headers = {}
        if incoming_headers.get("Range"):
            req_headers["Range"] = incoming_headers["Range"]

        # faptap.net 与 Bunny CDN 均校验 Referer，统一带上站点根地址
        req_headers["Referer"] = self._domain(config) + "/"

        response = session.get(
            target_url,
            headers=req_headers,
            timeout=timeout,
            stream=True,
        )
        return response

    # ---------- 数据转换 ----------

    def _to_video_summary(
        self,
        item: Dict[str, Any],
        domain: str,
    ) -> Dict[str, Any]:
        """将 API 视频对象转为宿主统一视频摘要格式。"""
        video_id = str(item.get("id") or "").strip()
        user = dict(item.get("user") or {})
        username = str(user.get("username") or "").strip()
        tags_raw = item.get("tags") or []
        tag_names: List[str] = []
        if isinstance(tags_raw, list):
            for tag in tags_raw:
                if isinstance(tag, dict):
                    name = str(tag.get("name") or "").strip()
                    if name and name not in tag_names:
                        tag_names.append(name)

        cover_url = _abs_url(str(item.get("thumbnail_url") or "").strip(), domain)
        preview_url = _abs_url(str(item.get("preview_url") or "").strip(), domain)

        return {
            "video_id": video_id,
            "title": str(item.get("name") or "").strip(),
            "code": video_id,
            "cover_url": cover_url,
            "thumbnail_url": cover_url,
            "preview_url": preview_url,
            "duration": _as_int(item.get("duration"), 0, 0, 10**6),
            "views": _as_int(item.get("views"), 0, 0, 10**9),
            "likes": _as_int(
                (item.get("rating") or {}).get("likes") if isinstance(item.get("rating"), dict)
                else 0, 0, 0, 10**9
            ),
            "author": username or "Unknown",
            "tags": tag_names,
            "date": str(item.get("created_at") or "").strip(),
            "platform": FAPTAP_PLATFORM,
            "host_id": f"{FAPTAP_HOST_ID_PREFIX}{video_id}",
            "source_url": f"{domain}/v/{video_id}",
        }

    def _to_video_detail(
        self,
        item: Dict[str, Any],
        domain: str,
    ) -> Dict[str, Any]:
        """将 API 视频对象转为宿主统一视频详情格式。"""
        summary = self._to_video_summary(item, domain)

        user = dict(item.get("user") or {})
        avatar_url = str(user.get("avatar_url") or "").strip()
        if avatar_url:
            avatar_url = _abs_url(avatar_url, domain)

        tags_raw = item.get("tags") or []
        tag_objects: List[Dict[str, Any]] = []
        if isinstance(tags_raw, list):
            for tag in tags_raw:
                if isinstance(tag, dict):
                    tag_objects.append({
                        "id": str(tag.get("id") or ""),
                        "name": str(tag.get("name") or "").strip(),
                        "slug": str(tag.get("slug") or "").strip(),
                    })

        preview_url = _abs_url(str(item.get("preview_url") or "").strip(), domain)
        thumbnail_images: List[str] = []
        if preview_url and preview_url != summary["cover_url"]:
            thumbnail_images.append(preview_url)

        detail = dict(summary)
        detail.update({
            "description": _strip_html(item.get("description")),
            "author": str(user.get("username") or "").strip() or "Unknown",
            "author_id": str(user.get("id") or "").strip(),
            "author_avatar": avatar_url,
            "author_verified": bool(user.get("verified")),
            "author_subscribers": _as_int(user.get("subscribers"), 0, 0, 10**9),
            "tag_objects": tag_objects,
            "thumbnail_images": thumbnail_images,
            "stream_url": str(item.get("stream_url_selfhosted") or "").strip(),
            "stream_url_selfhosted": str(item.get("stream_url_selfhosted") or "").strip(),
            "downloadable": _as_bool(item.get("downloadable"), False),
            "vr": _as_bool(item.get("vr"), False),
            "projection": str(item.get("projection") or "MONO_FLAT").strip(),
            "updated_at": str(item.get("updated_at") or "").strip(),
            "raw": item,
        })
        return detail
