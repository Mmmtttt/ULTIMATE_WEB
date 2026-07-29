from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.runtime_profile import get_runtime_profile, is_third_party_enabled

from .gateway import ProtocolGateway, get_protocol_gateway
from .platform_meta import (
    build_prefixed_id,
    resolve_manifest_host_prefix,
    resolve_manifest_platform_label,
    resolve_platform_manifest,
    split_prefixed_id,
)
from .runtime_config import ProtocolConfigStore


def _default_query_status() -> Dict[str, Any]:
    return {
        "configured": True,
        "message": "",
        "missing_fields": [],
    }


def _normalize_lookup_name(name: Any) -> str:
    return str(getattr(name, "value", name) or "").strip().lower()


def _resolve_canonical_platform_name(manifest: Any, fallback: str = "") -> str:
    return str(
        resolve_manifest_platform_label(
            manifest,
            fallback=fallback or getattr(manifest, "config_key", "") or getattr(manifest, "plugin_id", ""),
        )
        or ""
    ).strip().lower()


class ProtocolVideoClient:
    def __init__(
        self,
        *,
        gateway: ProtocolGateway,
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
        merged.update(dict(params or {}))
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
            raise ValueError(f"插件 {self.plugin_id or self.platform_name} 未声明能力: {normalized_capability}")
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
            {"keyword": keyword, "page": page, "max_pages": max_pages},
            require_ready=True,
        )
        return dict(payload or {})

    def get_video_detail(self, video_id: str, movie_type: Any = None) -> Dict[str, Any]:
        if not self.supports("catalog.detail"):
            return {}
        payload = self.execute(
            "catalog.detail",
            {"video_id": video_id, "movie_type": movie_type},
            require_ready=True,
        )
        return dict(payload or {})

    def get_video_by_code(self, code: str) -> Dict[str, Any]:
        if not self.supports("catalog.by_code"):
            return {}
        payload = self.execute("catalog.by_code", {"code": code}, require_ready=True)
        return dict(payload or {})

    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        if not self.supports("person.search"):
            return []
        payload = self.execute("person.search", {"actor_name": actor_name}, require_ready=True)
        if not isinstance(payload, list):
            return []
        return [dict(item or {}) for item in payload if isinstance(item, dict)]

    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        if not self.supports("person.works"):
            return {}
        payload = self.execute(
            "person.works",
            {"actor_id": actor_id, "page": page, "max_pages": max_pages},
            require_ready=True,
        )
        return dict(payload or {})

    def build_sources(self, code: str):
        return self.execute("playback.sources.build", {"code": code})

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
            return bool(fields) and all(self._payload_field_has_value(first_result, field_name) for field_name in fields)
        return False


class ProtocolHostService:
    def __init__(
        self,
        gateway: Optional[ProtocolGateway] = None,
        config_store: Optional[ProtocolConfigStore] = None,
    ):
        self._gateway = gateway or get_protocol_gateway()
        self._config_store = config_store or ProtocolConfigStore()

    @property
    def gateway(self) -> ProtocolGateway:
        return self._gateway

    def _find_manifest(
        self,
        name: Any,
        *,
        media_type: Optional[str] = None,
        capability: Optional[str] = None,
    ):
        lookup = _normalize_lookup_name(name)
        if not lookup:
            return None
        registry = getattr(self._gateway, "registry", None)
        resolvers = []
        if registry is not None:
            resolvers.extend(
                [
                    lambda: registry.find_by_lookup_name(lookup, media_type=media_type, capability=capability),
                    lambda: registry.find_by_config_key(lookup),
                ]
            )
        else:
            resolvers.extend(
                [
                    lambda: self._gateway.get_manifest_by_lookup(lookup, media_type=media_type, capability=capability),
                    lambda: self._gateway.get_manifest_by_lookup(lookup, capability=capability),
                    lambda: self._gateway.get_manifest_by_lookup(lookup),
                    lambda: self._gateway.get_manifest_by_config_key(lookup),
                ]
            )

        for resolve in resolvers:
            try:
                manifest = resolve()
            except Exception:
                manifest = None
            if manifest is None:
                continue
            has_capability = getattr(manifest, "has_capability", None)
            if capability and callable(has_capability) and not bool(has_capability(capability)):
                continue
            if media_type:
                raw_media_types = getattr(manifest, "media_types", None)
                manifest_media_types = {
                    str(item or "").strip().lower()
                    for item in (raw_media_types or [])
                    if str(item or "").strip()
                }
                if manifest_media_types and str(media_type or "").strip().lower() not in manifest_media_types:
                    continue
            return manifest
        return None

    def get_plugin_id(self, name: Any, *, media_type: Optional[str] = None, capability: Optional[str] = None) -> Optional[str]:
        manifest = self._find_manifest(name, media_type=media_type, capability=capability)
        if manifest is None:
            return None
        plugin_id = str(getattr(manifest, "plugin_id", "") or "").strip()
        return plugin_id or None

    def get_query_status(self, name: Any, *, media_type: Optional[str] = None) -> Dict[str, Any]:
        plugin_id = self.get_plugin_id(name, media_type=media_type)
        if not plugin_id:
            return _default_query_status()
        return self._gateway.get_query_status(plugin_id)

    def resolve_adapter_name(self, adapter_name: Optional[str] = None) -> str:
        resolved = adapter_name if adapter_name is not None else self._config_store.get_default_adapter()
        return str(resolved or "").strip()

    def resolve_comic_adapter_manifest(self, adapter_name: Optional[str] = None, capability: Optional[str] = None):
        resolved_name = self.resolve_adapter_name(adapter_name)
        if not resolved_name:
            return None
        return self._find_manifest(resolved_name, media_type="comic", capability=capability)

    def get_comic_adapter_client(self, adapter_name: Optional[str] = None):
        manifest = self.resolve_comic_adapter_manifest(adapter_name)
        if manifest is None:
            raise ValueError(f"unsupported adapter: {self.resolve_adapter_name(adapter_name)}")
        return self._gateway.get_client(manifest.plugin_id)

    def execute_comic_adapter(self, capability: str, params: Dict[str, Any], adapter_name: Optional[str] = None):
        manifest = self.resolve_comic_adapter_manifest(adapter_name, capability=capability)
        if manifest is None:
            raise ValueError(f"unsupported adapter: {self.resolve_adapter_name(adapter_name)}")
        return self._gateway.execute_plugin(manifest.plugin_id, capability, params=dict(params or {}))

    def get_comic_platform_client(self, platform: Any):
        manifest = self._find_manifest(platform, media_type="comic")
        if manifest is None:
            raise ValueError(f"未知平台: {platform}")
        return self._gateway.get_client(manifest.plugin_id)

    def execute_comic_platform(self, platform: Any, capability: str, params: Optional[Dict[str, Any]] = None):
        manifest = self._find_manifest(platform, media_type="comic", capability=capability)
        if manifest is None:
            raise ValueError(f"未知平台: {platform}")
        return self._gateway.execute_plugin(manifest.plugin_id, capability, params=dict(params or {}))

    def get_default_video_platform_name(self) -> str:
        manifests = list(self._gateway.list_manifests(media_type="video", capability="catalog.search"))
        if not manifests:
            return ""
        return _resolve_canonical_platform_name(manifests[0])

    def resolve_video_manifest(self, platform_name: str = "", *, capability: Optional[str] = "catalog.search"):
        requested_platform = str(platform_name or "").strip().lower()
        manifest = None
        if requested_platform:
            manifest = resolve_platform_manifest(requested_platform, media_type="video", capability=capability)
        else:
            manifests = list(self._gateway.list_manifests(media_type="video", capability=capability))
            manifest = manifests[0] if manifests else None
        if manifest is None:
            raise ValueError(f"不支持的视频平台: {platform_name or capability or 'unknown'}")
        return _resolve_canonical_platform_name(manifest, fallback=requested_platform), manifest

    @staticmethod
    def _extract_existing_tags(*args, **kwargs) -> List[Dict[str, Any]]:
        if args:
            first_arg = args[0]
            if isinstance(first_arg, list):
                return list(first_arg)
        existing_tags = kwargs.get("existing_tags")
        if isinstance(existing_tags, list):
            return list(existing_tags)
        return []

    def get_video_client(self, platform_name: str = "", *args, capability: str = "catalog.search", **kwargs) -> ProtocolVideoClient:
        if not is_third_party_enabled():
            raise RuntimeError(
                f"third-party integration is disabled in current runtime profile: {get_runtime_profile()}"
            )
        normalized_platform, manifest = self.resolve_video_manifest(platform_name, capability=capability)
        default_params: Dict[str, Any] = {}
        existing_tags = self._extract_existing_tags(*args, **kwargs)
        if existing_tags:
            default_params["existing_tags"] = existing_tags
        proxy_base_path = str(kwargs.get("proxy_base_path") or "").strip()
        if proxy_base_path:
            default_params["proxy_base_path"] = proxy_base_path
        return ProtocolVideoClient(
            gateway=self._gateway,
            manifest=manifest,
            platform_name=normalized_platform,
            default_params=default_params,
        )

    def execute_video_capability(
        self,
        platform_name: str,
        capability: str,
        params: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ):
        client = self.get_video_client(platform_name, *args, capability=capability, **kwargs)
        payload = client.execute(
            capability,
            dict(params or {}),
            require_ready=capability.startswith("catalog.") or capability.startswith("person."),
        )
        return client.platform_name, client.manifest, payload

    def get_video_query_status(self, platform_name: str = "") -> Dict[str, Any]:
        try:
            _platform_name, manifest = self.resolve_video_manifest(platform_name, capability=None)
        except Exception:
            return _default_query_status()
        try:
            status = self._gateway.get_query_status(manifest.plugin_id) or {}
            if isinstance(status, dict):
                return dict(status)
        except Exception:
            pass
        return _default_query_status()

    def resolve_video_lookup_context(
        self,
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
            inline_manifest = resolve_platform_manifest(raw_prefix, media_type="video", capability="catalog.search")
            if inline_manifest is not None and str(raw_rest or "").strip():
                normalized_platform = _resolve_canonical_platform_name(inline_manifest, fallback=raw_prefix) or normalized_platform
                manifest = inline_manifest
                lookup_id = str(raw_rest or "").strip()

        if manifest is None and normalized_video_id and not normalized_video_id.upper().startswith("LOCAL"):
            parsed_platform, original_id, parsed_manifest = split_prefixed_id(normalized_video_id, media_type="video")
            if parsed_manifest is not None and original_id and original_id != normalized_video_id:
                normalized_platform = str(parsed_platform or "").strip().lower() or normalized_platform
                manifest = parsed_manifest
                lookup_id = str(original_id or "").strip() or lookup_id

        if manifest is None and normalized_platform:
            manifest = resolve_platform_manifest(normalized_platform, media_type="video", capability="catalog.search")

        if manifest is not None:
            normalized_platform = _resolve_canonical_platform_name(manifest, fallback=normalized_platform)

        if not normalized_platform:
            normalized_platform = self.get_default_video_platform_name()
            if manifest is None and normalized_platform:
                manifest = resolve_platform_manifest(normalized_platform, media_type="video", capability="catalog.search")

        return normalized_platform, lookup_id or normalized_code or normalized_video_id, manifest

    def build_video_host_id(self, platform_name: str, original_id: str) -> str:
        normalized_platform, _, manifest = self.resolve_video_lookup_context(platform_name=platform_name, video_id="")
        host_prefix = resolve_manifest_host_prefix(manifest, fallback=normalized_platform)
        return build_prefixed_id(host_prefix, original_id)

    def get_playback_proxy_client(self, *args, **kwargs) -> ProtocolVideoClient:
        return self.get_video_client("", *args, capability="playback.proxy.stream", **kwargs)

    def get_preview_request_client(self, *args, **kwargs) -> ProtocolVideoClient:
        return self.get_video_client("", *args, capability="transport.http.request", **kwargs)


_host_service_singleton: Optional[ProtocolHostService] = None


def get_protocol_host_service() -> ProtocolHostService:
    global _host_service_singleton
    if _host_service_singleton is None:
        _host_service_singleton = ProtocolHostService()
    return _host_service_singleton
