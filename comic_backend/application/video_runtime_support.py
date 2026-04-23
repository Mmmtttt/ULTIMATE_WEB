from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from application.config_app_service import ConfigAppService
from core.runtime_profile import get_runtime_profile, is_third_party_enabled
from protocol.gateway import get_protocol_gateway
from protocol.platform_meta import (
    build_prefixed_id,
    resolve_manifest_host_prefix,
    resolve_manifest_platform_label,
    resolve_platform_manifest,
    split_prefixed_id,
)


_config_service = ConfigAppService()


def _get_video_service_cls():
    from application.video_app_service import VideoAppService

    return VideoAppService


def _default_query_status() -> Dict[str, Any]:
    return {
        "configured": True,
        "message": "",
        "missing_fields": [],
    }


def _resolve_canonical_platform_name(manifest: Any, fallback: str = "") -> str:
    return str(
        resolve_manifest_platform_label(
            manifest,
            fallback=fallback or getattr(manifest, "config_key", "") or getattr(manifest, "plugin_id", ""),
        )
        or ""
    ).strip().lower()


def _extract_existing_tags(*args, **kwargs) -> List[Dict[str, Any]]:
    if args:
        first_arg = args[0]
        if isinstance(first_arg, list):
            return list(first_arg)
    existing_tags = kwargs.get("existing_tags")
    if isinstance(existing_tags, list):
        return list(existing_tags)
    return []


class ProtocolVideoPlatformClient:
    def __init__(
        self,
        *,
        gateway,
        manifest: Any,
        platform_name: str = "",
        default_params: Optional[Dict[str, Any]] = None,
    ):
        self._gateway = gateway
        self._manifest = manifest
        self.plugin_id = str(getattr(manifest, "plugin_id", "") or "").strip()
        self.platform_name = _resolve_canonical_platform_name(manifest, fallback=platform_name)
        self._default_params = dict(default_params or {})

    @property
    def manifest(self):
        return self._manifest

    def supports(self, capability: str) -> bool:
        return bool(getattr(self._manifest, "has_capability", lambda *_args, **_kwargs: False)(capability))

    def query_status(self) -> Dict[str, Any]:
        try:
            status = self._gateway.get_query_status(self.plugin_id) or {}
            if isinstance(status, dict):
                return dict(status)
        except Exception:
            pass
        return _default_query_status()

    def ensure_ready(self) -> None:
        status = self.query_status()
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or f"{self.platform_name or self.plugin_id} 平台未配置查询凭据"))

    def _merge_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged = dict(self._default_params)
        for key, value in dict(params or {}).items():
            merged[key] = value
        return merged

    def execute(
        self,
        capability: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        require_ready: bool = False,
    ) -> Any:
        normalized_capability = str(capability or "").strip()
        if not normalized_capability:
            raise ValueError("缺少 capability")
        if not self.supports(normalized_capability):
            raise ValueError(
                f"插件 {self.plugin_id or self.platform_name} 未声明能力: {normalized_capability}"
            )
        if require_ready:
            self.ensure_ready()
        return self._gateway.execute_plugin(
            self.plugin_id,
            normalized_capability,
            params=self._merge_params(params),
        )

    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        if not self.supports("catalog.search"):
            return {}
        payload = self.execute(
            "catalog.search",
            {
                "keyword": keyword,
                "page": page,
                "max_pages": max_pages,
            },
            require_ready=True,
        )
        return dict(payload or {})

    def get_video_detail(self, video_id: str, movie_type: Any = None) -> Dict[str, Any]:
        if not self.supports("catalog.detail"):
            return {}
        payload = self.execute(
            "catalog.detail",
            {
                "video_id": video_id,
                "movie_type": movie_type,
            },
            require_ready=True,
        )
        return dict(payload or {})

    def get_video_by_code(self, code: str) -> Dict[str, Any]:
        if not self.supports("catalog.by_code"):
            return {}
        payload = self.execute(
            "catalog.by_code",
            {"code": code},
            require_ready=True,
        )
        return dict(payload or {})

    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        if not self.supports("person.search"):
            return []
        payload = self.execute(
            "person.search",
            {"actor_name": actor_name},
            require_ready=True,
        )
        if isinstance(payload, list):
            return [dict(item or {}) for item in payload if isinstance(item, dict)]
        return []

    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        if not self.supports("person.works"):
            return {}
        payload = self.execute(
            "person.works",
            {
                "actor_id": actor_id,
                "page": page,
                "max_pages": max_pages,
            },
            require_ready=True,
        )
        return dict(payload or {})

    def build_sources(self, code: str):
        return self.execute(
            "playback.sources.build",
            {"code": code},
        )

    def proxy_stream(
        self,
        *,
        domain: str,
        path: str,
        query_string: str = "",
        incoming_referer: str = "",
    ):
        return self.execute(
            "playback.proxy.stream",
            {
                "domain": domain,
                "path": path,
                "query_string": query_string,
                "incoming_referer": incoming_referer,
            },
        )

    def proxy_url(
        self,
        *,
        method: str = "GET",
        query_string: str = "",
        body_url: str = "",
        incoming_referer: str = "",
        incoming_headers: Optional[Dict[str, str]] = None,
    ):
        return self.execute(
            "playback.proxy.url",
            {
                "method": method,
                "query_string": query_string,
                "body_url": body_url,
                "incoming_referer": incoming_referer,
                "incoming_headers": dict(incoming_headers or {}),
            },
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
        timeout: int = 0,
        allow_redirects: bool = True,
    ):
        return self.execute(
            "transport.http.request",
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "stream": bool(stream),
                "timeout": int(timeout or 0),
                "allow_redirects": bool(allow_redirects),
            },
        )

    @staticmethod
    def _payload_field_has_value(payload: Dict[str, Any], field_name: str) -> bool:
        value = payload.get(field_name)
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        return value is not None

    def should_skip_remote_detail(self, first_result: Dict[str, Any]) -> bool:
        search_entry = dict(self._manifest.get_capability_entry("catalog.search") or {})
        detail_policy = dict(search_entry.get("result_detail_policy") or {})
        mode = str(detail_policy.get("mode") or "").strip().lower()
        fields = [
            str(item or "").strip()
            for item in (detail_policy.get("fields") or [])
            if str(item or "").strip()
        ]

        if mode in {"search_payload", "search_payload_only", "prefer_search_payload"}:
            return True

        if mode == "search_payload_if_fields_present":
            if not fields:
                return False
            return all(self._payload_field_has_value(first_result, field_name) for field_name in fields)

        return False


def get_default_video_platform_name() -> str:
    manifests = list(get_protocol_gateway().list_manifests(media_type="video", capability="catalog.search"))
    if not manifests:
        return ""
    return _resolve_canonical_platform_name(manifests[0])


def resolve_video_manifest_or_error(
    platform_name: str = "",
    *,
    capability: Optional[str] = "catalog.search",
):
    gateway = get_protocol_gateway()
    requested_platform = str(platform_name or "").strip().lower()

    manifest = None
    if requested_platform:
        manifest = resolve_platform_manifest(
            requested_platform,
            media_type="video",
            capability=capability,
        )
    else:
        manifests = list(gateway.list_manifests(media_type="video", capability=capability))
        manifest = manifests[0] if manifests else None

    if manifest is None:
        raise ValueError(f"不支持的视频平台: {platform_name or capability or 'unknown'}")

    return _resolve_canonical_platform_name(manifest, fallback=requested_platform), manifest


def execute_video_plugin_capability(
    platform_name: str,
    capability: str,
    params: Optional[Dict[str, Any]] = None,
    *args,
    **kwargs,
):
    client = get_video_adapter(platform_name, *args, capability=capability, **kwargs)
    payload = client.execute(
        capability,
        dict(params or {}),
        require_ready=capability.startswith("catalog.") or capability.startswith("person."),
    )
    return client.platform_name, client.manifest, payload


def get_video_platform_query_status(platform_name: str = "") -> Dict[str, Any]:
    try:
        _platform_name, manifest = resolve_video_manifest_or_error(platform_name, capability=None)
    except Exception:
        return _default_query_status()
    try:
        status = get_protocol_gateway().get_query_status(manifest.plugin_id) or {}
        if isinstance(status, dict):
            return dict(status)
    except Exception:
        pass
    return _default_query_status()


def resolve_video_lookup_context(
    *,
    video_id: str = "",
    code: str = "",
    platform_name: str = "",
) -> Tuple[str, str, Any]:
    normalized_platform = str(platform_name or "").strip().lower()
    normalized_video_id = str(video_id or "").strip()
    normalized_code = str(code or "").strip()
    manifest = None
    lookup_id = normalized_video_id

    if normalized_video_id and "_" in normalized_video_id:
        raw_prefix, raw_rest = normalized_video_id.split("_", 1)
        inline_manifest = resolve_platform_manifest(
            raw_prefix,
            media_type="video",
            capability="catalog.search",
        )
        if inline_manifest is not None and str(raw_rest or "").strip():
            normalized_platform = _resolve_canonical_platform_name(inline_manifest, fallback=raw_prefix) or normalized_platform
            manifest = inline_manifest
            lookup_id = str(raw_rest or "").strip()

    if manifest is None and normalized_video_id and not normalized_video_id.upper().startswith("LOCAL"):
        parsed_platform, original_id, parsed_manifest = split_prefixed_id(
            normalized_video_id,
            media_type="video",
        )
        if parsed_manifest is not None and original_id and original_id != normalized_video_id:
            normalized_platform = str(parsed_platform or "").strip().lower() or normalized_platform
            manifest = parsed_manifest
            lookup_id = str(original_id or "").strip() or lookup_id

    if manifest is None and normalized_platform:
        manifest = resolve_platform_manifest(
            normalized_platform,
            media_type="video",
            capability="catalog.search",
        )

    if manifest is not None:
        normalized_platform = _resolve_canonical_platform_name(
            manifest,
            fallback=normalized_platform,
        )

    if not normalized_platform:
        normalized_platform = get_default_video_platform_name()
        if manifest is None and normalized_platform:
            manifest = resolve_platform_manifest(
                normalized_platform,
                media_type="video",
                capability="catalog.search",
            )

    return normalized_platform, lookup_id or normalized_code or normalized_video_id, manifest


def build_video_host_id(platform_name: str, original_id: str) -> str:
    normalized_platform, _, manifest = resolve_video_lookup_context(
        platform_name=platform_name,
        video_id="",
    )
    host_prefix = resolve_manifest_host_prefix(manifest, fallback=normalized_platform)
    return build_prefixed_id(host_prefix, original_id)


def get_video_adapter(platform_name: str = "", *args, capability: str = "catalog.search", **kwargs):
    if not is_third_party_enabled():
        raise RuntimeError(
            f"third-party integration is disabled in current runtime profile: {get_runtime_profile()}"
        )

    normalized_platform, manifest = resolve_video_manifest_or_error(
        platform_name,
        capability=capability,
    )
    default_params: Dict[str, Any] = {}
    existing_tags = _extract_existing_tags(*args, **kwargs)
    if existing_tags:
        default_params["existing_tags"] = existing_tags
    proxy_base_path = str(kwargs.get("proxy_base_path") or "").strip()
    if proxy_base_path:
        default_params["proxy_base_path"] = proxy_base_path
    return ProtocolVideoPlatformClient(
        gateway=get_protocol_gateway(),
        manifest=manifest,
        platform_name=normalized_platform,
        default_params=default_params,
    )


def get_playback_proxy_client(*args, **kwargs):
    return get_video_adapter("", *args, capability="playback.proxy.stream", **kwargs)


def get_preview_request_client(*args, **kwargs):
    return get_video_adapter("", *args, capability="transport.http.request", **kwargs)


def sanitize_preview_video_value(raw_url: str) -> str:
    return _get_video_service_cls()._sanitize_preview_video_url(raw_url)


def to_proxy_image_url(
    url: str,
    *,
    asset_kind: str = "image",
    video_id: str = "",
    platform_name: str = "",
    content_id: str = "",
) -> str:
    return _get_video_service_cls().to_frontend_asset_url(
        url,
        asset_kind=asset_kind,
        video_id=video_id,
        platform_name=platform_name,
        content_id=content_id,
        proxy_base_path="/api/v1/video/proxy2",
    )


def platform_allows_preview_video_download(platform: str = "", video_id: str = "") -> bool:
    return _get_video_service_cls()._video_platform_allows_preview_download(
        video_id=video_id,
        platform_name=platform,
    )


def _get_preview_import_auto_download_enabled() -> bool:
    try:
        result = _config_service.get_config()
        if not result.success or not isinstance(result.data, dict):
            return True
        return bool(result.data.get("auto_download_preview_assets_for_preview_import", False))
    except Exception:
        return True


def _should_auto_download_preview_assets(source: str = "local") -> bool:
    return str(source or "").strip().lower() != "preview" or _get_preview_import_auto_download_enabled()


def schedule_video_asset_cache(
    *,
    video_id: str,
    source: str,
    cover_url: str = "",
    preview_video: str = "",
    thumbnail_images=None,
    allow_cover: bool = True,
    allow_preview_video: bool = True,
    video_service: Optional[Any] = None,
) -> None:
    if not video_id:
        return

    video_service_cls = _get_video_service_cls()
    service = video_service or video_service_cls()
    cover = str(cover_url or "").strip()
    preview = sanitize_preview_video_value(preview_video or "")
    thumbs = [str(item or "").strip() for item in (thumbnail_images or []) if str(item or "").strip()]
    auto_download_enabled = _should_auto_download_preview_assets(source)
    allow_preview_video = bool(allow_preview_video) and platform_allows_preview_video_download(video_id=video_id)

    if allow_cover and cover:
        service.cache_cover_to_static_async(video_id, cover, source=source)

    if not auto_download_enabled:
        return

    if thumbs:
        service.cache_thumbnail_images_async(video_id, thumbs, source=source)

    if allow_preview_video and preview:
        service.cache_preview_video_async(video_id, preview, source=source)
