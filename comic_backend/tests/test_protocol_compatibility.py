from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol import compatibility
from protocol.base import ProtocolProvider


@dataclass
class _FakeManifest:
    plugin_id: str
    config_key: str
    media_types: list[str]
    capability_keys: list[str]
    lookup_names: list[str]
    name: str = ""
    identity: dict | None = None

    @property
    def identity_aliases(self):
        return [str(item or "").strip() for item in self.lookup_names if str(item or "").strip()]

    def has_capability(self, capability: str) -> bool:
        return str(capability or "").strip() in set(self.capability_keys)

    def list_lookup_names(self):
        return list(self.lookup_names)


class _FakeGateway:
    def __init__(self, manifests):
        self._manifests = list(manifests)
        self.registry = None
        self.client_requests = []

    def list_manifests(self, media_type=None, capability=None):
        manifests = list(self._manifests)
        if media_type:
            manifests = [
                item for item in manifests
                if str(media_type or "").strip().lower()
                in {str(mt or "").strip().lower() for mt in (item.media_types or [])}
            ]
        if capability:
            manifests = [item for item in manifests if item.has_capability(capability)]
        return manifests

    def get_manifest_by_lookup(self, lookup_name, media_type=None, capability=None):
        lookup = str(lookup_name or "").strip().lower()
        if not lookup:
            return None

        for manifest in self.list_manifests(media_type=media_type, capability=capability):
            candidates = {
                str(item or "").strip().lower()
                for item in manifest.list_lookup_names()
                if str(item or "").strip()
            }
            if lookup in candidates:
                return manifest
        return None

    def get_manifest_by_config_key(self, config_key):
        lookup = str(config_key or "").strip().lower()
        for manifest in self._manifests:
            if str(manifest.config_key or "").strip().lower() == lookup:
                return manifest
        return None

    def get_client(self, plugin_id, *args, **kwargs):
        self.client_requests.append({"plugin_id": plugin_id, "args": args, "kwargs": kwargs})
        return {"plugin_id": plugin_id, "kwargs": kwargs}


def test_compatibility_resolves_plugin_ids_from_manifest_metadata(monkeypatch):
    gateway = _FakeGateway(
        [
            _FakeManifest(
                plugin_id="comic.jmcomic",
                config_key="jmcomic",
                media_types=["comic"],
                capability_keys=["catalog.search"],
                lookup_names=["comic.jmcomic", "jmcomic", "JM"],
                name="JMComic",
                identity={"platform_label": "JM", "host_id_prefix": "JM"},
            ),
            _FakeManifest(
                plugin_id="video.javdb",
                config_key="javdb",
                media_types=["video"],
                capability_keys=["catalog.search"],
                lookup_names=["video.javdb", "javdb", "JAVDB"],
                name="JAVDB",
                identity={"platform_label": "JAVDB", "host_id_prefix": "JAVDB"},
            ),
        ]
    )

    monkeypatch.setattr(compatibility, "get_protocol_gateway", lambda: gateway)

    assert compatibility.get_plugin_id_for_adapter_name("jmcomic") == "comic.jmcomic"
    assert compatibility.get_plugin_id_for_comic_platform("JM") == "comic.jmcomic"
    assert compatibility.get_plugin_id_for_video_platform("javdb") == "video.javdb"
    assert compatibility.get_plugin_id_for_platform("video.javdb") == "video.javdb"


def test_compatibility_uses_capability_declared_proxy_client(monkeypatch):
    gateway = _FakeGateway(
        [
            _FakeManifest(
                plugin_id="video.proxy-provider",
                config_key="proxy-provider",
                media_types=["video"],
                capability_keys=["playback.proxy.stream"],
                lookup_names=["proxy-provider", "PROXY"],
                name="Proxy Provider",
                identity={"platform_label": "PROXY"},
            )
        ]
    )

    monkeypatch.setattr(compatibility, "get_protocol_gateway", lambda: gateway)

    client = compatibility.get_playback_proxy_client(proxy_base_path="/api/v1/video")
    assert client["plugin_id"] == "video.proxy-provider"
    assert gateway.client_requests == [
        {
            "plugin_id": "video.proxy-provider",
            "args": (),
            "kwargs": {"proxy_base_path": "/api/v1/video"},
        }
    ]


def test_protocol_provider_client_exposes_public_request_alias():
    captured = {}

    class _FakeProvider(ProtocolProvider):
        def execute(self, capability, params, context, config):
            captured["capability"] = capability
            captured["params"] = dict(params or {})
            return {"ok": True}

    provider = _FakeProvider({}, "")
    client = provider.build_client({})

    result = client.request(
        "GET",
        "https://media.example/preview.m3u8",
        headers={"Referer": "https://media.example/"},
        stream=True,
        timeout=30,
    )

    assert result == {"ok": True}
    assert captured == {
        "capability": "transport.http.request",
        "params": {
            "method": "GET",
            "url": "https://media.example/preview.m3u8",
            "headers": {"Referer": "https://media.example/"},
            "stream": True,
            "timeout": 30,
            "allow_redirects": True,
            "impersonate": "",
        },
    }
