from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class PluginManifest:
    raw: Dict[str, Any]
    path: str

    @property
    def protocol_version(self) -> str:
        return str(self.raw.get("protocol_version") or "").strip()

    @property
    def plugin(self) -> Dict[str, Any]:
        return dict(self.raw.get("plugin") or {})

    @property
    def plugin_id(self) -> str:
        return str(self.plugin.get("id") or "").strip()

    @property
    def name(self) -> str:
        return str(self.plugin.get("name") or self.plugin_id).strip()

    @property
    def version(self) -> str:
        return str(self.plugin.get("version") or "").strip()

    @property
    def entrypoint(self) -> str:
        return str(self.plugin.get("entrypoint") or "").strip()

    @property
    def config_key(self) -> str:
        return str(self.plugin.get("config_key") or "").strip()

    @property
    def media_types(self) -> List[str]:
        return [str(item or "").strip() for item in (self.raw.get("media_types") or []) if str(item or "").strip()]

    @property
    def capability_entries(self) -> List[Dict[str, Any]]:
        return [dict(item or {}) for item in (self.raw.get("capabilities") or []) if isinstance(item, dict)]

    @property
    def capability_keys(self) -> List[str]:
        keys: List[str] = []
        for item in self.capability_entries:
            key = str(item.get("key") or "").strip()
            if key:
                keys.append(key)
        return keys

    @property
    def configuration(self) -> Dict[str, Any]:
        return dict(self.raw.get("configuration") or {})

    @property
    def helpers(self) -> Dict[str, Any]:
        return dict(self.raw.get("helpers") or {})

    @property
    def storage(self) -> Dict[str, Any]:
        return dict(self.raw.get("storage") or {})

    @property
    def identity(self) -> Dict[str, Any]:
        return dict(self.raw.get("identity") or {})

    @property
    def identity_aliases(self) -> List[str]:
        identity = self.identity
        raw_aliases = (
            identity.get("aliases")
            or identity.get("lookup_aliases")
            or []
        )

        aliases: List[str] = []
        if isinstance(raw_aliases, list):
            for item in raw_aliases:
                normalized = str(item or "").strip()
                if normalized:
                    aliases.append(normalized)

        return aliases

    @property
    def presentation(self) -> Dict[str, Any]:
        return dict(self.raw.get("presentation") or {})

    @property
    def actions(self) -> List[Dict[str, Any]]:
        return [dict(item or {}) for item in (self.raw.get("actions") or []) if isinstance(item, dict)]

    @property
    def resource_policy(self) -> Dict[str, Any]:
        return dict(self.raw.get("resource_policy") or {})

    @property
    def collections(self) -> Dict[str, Any]:
        return dict(self.raw.get("collections") or {})

    @property
    def order(self) -> int:
        try:
            return int(self.configuration.get("order", 100))
        except Exception:
            return 100

    @property
    def collection_list_mode(self) -> str:
        return str(self.collections.get("list_mode") or "").strip().lower()

    def has_capability(self, capability: str) -> bool:
        return str(capability or "").strip() in set(self.capability_keys)

    def get_capability_entry(self, capability: str) -> Dict[str, Any]:
        lookup = str(capability or "").strip()
        if not lookup:
            return {}
        for item in self.capability_entries:
            key = str(item.get("key") or "").strip()
            if key == lookup:
                return dict(item)
        return {}

    def list_configuration_fields(self) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        sections = self.configuration.get("sections") or []
        for section in sections:
            if not isinstance(section, dict):
                continue
            for field in section.get("fields") or []:
                if isinstance(field, dict):
                    fields.append(dict(field))
        return fields

    def list_configuration_actions(self) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        for action in self.actions:
            scope = str(action.get("scope") or "").strip().lower()
            if scope in {"config", "configuration", "settings"}:
                actions.append(dict(action))

        for action in (self.configuration.get("actions") or []):
            if not isinstance(action, dict):
                continue
            normalized = dict(action)
            normalized.setdefault("scope", "configuration")
            actions.append(normalized)

        return actions

    def list_helpers(self) -> Dict[str, Dict[str, Any]]:
        helpers: Dict[str, Dict[str, Any]] = {}
        for helper_key, helper_value in (self.helpers or {}).items():
            normalized_key = str(helper_key or "").strip()
            if not normalized_key or not isinstance(helper_value, dict):
                continue
            helpers[normalized_key] = dict(helper_value)
        return helpers

    def get_helper(self, helper_key: str) -> Dict[str, Any]:
        lookup = str(helper_key or "").strip()
        if not lookup:
            return {}
        return dict(self.list_helpers().get(lookup) or {})

    def list_data_dir_bindings(self) -> List[Dict[str, Any]]:
        bindings: List[Dict[str, Any]] = []
        for item in (self.storage.get("data_dir_bindings") or []):
            if isinstance(item, dict):
                bindings.append(dict(item))
        return bindings

    def list_virtual_lists(self) -> List[Dict[str, Any]]:
        virtual_lists: List[Dict[str, Any]] = []
        for item in (self.collections.get("virtual_lists") or []):
            if isinstance(item, dict):
                virtual_lists.append(dict(item))
        return virtual_lists

    def list_lookup_names(self) -> List[str]:
        candidates = [
            self.plugin_id,
            self.config_key,
            self.name,
            str(self.identity.get("platform_label") or "").strip(),
            str(self.identity.get("host_id_prefix") or "").strip(),
            *self.identity_aliases,
        ]
        deduped: List[str] = []
        seen = set()
        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(normalized)
        return deduped

    def to_public_descriptor(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "config_key": self.config_key,
            "name": self.name,
            "version": self.version,
            "media_types": self.media_types,
            "capabilities": self.capability_keys,
            "lookup_names": self.list_lookup_names(),
            "identity": self.identity,
            "presentation": self.presentation,
            "actions": self.actions,
            "collections": self.collections,
            "resource_policy": self.resource_policy,
            "order": self.order,
        }


class ProtocolProviderClient:
    def __init__(self, provider: "ProtocolProvider", config: Dict[str, Any], *args, **kwargs):
        self._provider = provider
        self._config = dict(config or {})
        self._context = dict(kwargs.get("context") or {})
        self._default_params: Dict[str, Any] = {}

        existing_tags = kwargs.get("existing_tags")
        if existing_tags is None and args and isinstance(args[0], list):
            existing_tags = args[0]
        if isinstance(existing_tags, list):
            self._default_params["existing_tags"] = existing_tags

        proxy_base_path = str(kwargs.get("proxy_base_path") or "").strip()
        if proxy_base_path:
            self._default_params["proxy_base_path"] = proxy_base_path

    def _execute(self, capability: str, **params):
        merged_params = dict(self._default_params)
        for key, value in (params or {}).items():
            if value is not None:
                merged_params[key] = value
        return self._provider.execute(
            str(capability or "").strip(),
            merged_params,
            dict(self._context),
            dict(self._config),
        )

    def search_albums(self, keyword: str, page: int = 1, max_pages: int = 1, fast_mode: bool = False):
        return self._execute(
            "catalog.search",
            keyword=keyword,
            page=page,
            max_pages=max_pages,
            fast_mode=fast_mode,
        )

    def get_album_by_id(self, album_id: str):
        return self._execute("catalog.detail", album_id=album_id)

    def get_favorites(self):
        return self._execute("collection.favorites")

    def get_favorites_basic(self):
        return self._execute("collection.favorites_basic")

    def get_user_lists(self):
        return self._execute("collection.list")

    def get_list_detail(self, list_id: str):
        return self._execute("collection.detail", list_id=list_id)

    def download_album(self, album_id: str, download_dir: str, show_progress: bool = False, **kwargs):
        result = self._execute(
            "asset.bundle.fetch",
            album_id=album_id,
            download_dir=download_dir,
            show_progress=show_progress,
            extra=dict(kwargs or {}),
        )
        return dict(result.get("detail") or {}), bool(result.get("success"))

    def download_cover(self, album_id: str, save_path: str, show_progress: bool = False):
        result = self._execute(
            "asset.cover.fetch",
            album_id=album_id,
            save_path=save_path,
            show_progress=show_progress,
        )
        return dict(result.get("detail") or {}), bool(result.get("success"))

    def get_comic_dir(self, album_id: str, author: str = None, title: str = None, base_dir: str = None):
        return self._execute(
            "storage.comic_dir.resolve",
            album_id=album_id,
            author=author,
            title=title,
            base_dir=base_dir,
        )

    def get_preview_image_urls(self, album_id: str, preview_pages: List[int]):
        return self._execute(
            "asset.preview.resolve",
            album_id=album_id,
            preview_pages=list(preview_pages or []),
        )

    def get_cover_url(self, album_id: str):
        return None

    def get_image_url(self, album_id: str, page: int):
        return None

    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1):
        return self._execute(
            "catalog.search",
            keyword=keyword,
            page=page,
            max_pages=max_pages,
        )

    def get_video_detail(self, video_id: str):
        return self._execute("catalog.detail", video_id=video_id)

    def get_video_by_code(self, code: str):
        return self._execute("catalog.by_code", code=code)

    def search_actor(self, actor_name: str):
        return self._execute("person.search", actor_name=actor_name)

    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1):
        return self._execute(
            "person.works",
            actor_id=actor_id,
            page=page,
            max_pages=max_pages,
        )

    def build_sources(self, code: str):
        return self._execute("playback.sources.build", code=code)

    def proxy_stream(self, domain: str, path: str, query_string: str = "", incoming_referer: str = ""):
        return self._execute(
            "playback.proxy.stream",
            domain=domain,
            path=path,
            query_string=query_string,
            incoming_referer=incoming_referer,
        )

    def proxy_url(
        self,
        method: str = "GET",
        query_string: str = "",
        body_url: str = "",
        incoming_referer: str = "",
        incoming_headers: Dict[str, Any] = None,
    ):
        return self._execute(
            "playback.proxy.url",
            method=method,
            query_string=query_string,
            body_url=body_url,
            incoming_referer=incoming_referer,
            incoming_headers=dict(incoming_headers or {}),
        )

    def _request(
        self,
        method: str,
        url: str,
        headers: Dict[str, Any] = None,
        stream: bool = False,
        timeout: int = None,
        allow_redirects: bool = True,
        impersonate: str = "",
    ):
        return self._execute(
            "transport.http.request",
            method=method,
            url=url,
            headers=dict(headers or {}),
            stream=stream,
            timeout=timeout,
            allow_redirects=allow_redirects,
            impersonate=impersonate,
        )

    def request(
        self,
        method: str,
        url: str,
        headers: Dict[str, Any] = None,
        stream: bool = False,
        timeout: int = None,
        allow_redirects: bool = True,
        impersonate: str = "",
    ):
        return self._request(
            method=method,
            url=url,
            headers=headers,
            stream=stream,
            timeout=timeout,
            allow_redirects=allow_redirects,
            impersonate=impersonate,
        )


class ProtocolProvider:
    def __init__(self, manifest: Dict[str, Any], manifest_path: str):
        self.manifest = dict(manifest or {})
        self.manifest_path = str(manifest_path or "")

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(payload or {})

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return dict(config or {})

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "configured": True,
            "message": "",
            "missing_fields": [],
        }

    def build_client(self, config: Dict[str, Any], *args, **kwargs):
        return ProtocolProviderClient(self, config, *args, **kwargs)

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        raise NotImplementedError
