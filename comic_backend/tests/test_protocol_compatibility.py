from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol import compatibility


@dataclass
class _FakeManifest:
    plugin_id: str
    config_key: str
    legacy_adapter_name: str
    legacy_platforms: list[str]
    media_types: list[str]
    capability_keys: list[str]
    name: str = ""
    identity: dict | None = None

    def has_capability(self, capability: str) -> bool:
        return str(capability or "").strip() in set(self.capability_keys)


class _FakeGateway:
    def __init__(self, manifests):
        self._manifests = list(manifests)
        self.registry = None
        self.legacy_client_requests = []

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

    def get_manifest_by_legacy_platform(self, *_args, **_kwargs):
        return None

    def get_manifest_by_config_key(self, *_args, **_kwargs):
        return None

    def get_legacy_client(self, plugin_id, *args, **kwargs):
        self.legacy_client_requests.append({"plugin_id": plugin_id, "args": args, "kwargs": kwargs})
        return {"plugin_id": plugin_id, "kwargs": kwargs}


def test_compatibility_resolves_plugin_ids_from_manifest_metadata(monkeypatch):
    gateway = _FakeGateway(
        [
            _FakeManifest(
                plugin_id="comic.jmcomic",
                config_key="jmcomic",
                legacy_adapter_name="jmcomic",
                legacy_platforms=["JM"],
                media_types=["comic"],
                capability_keys=["catalog.search"],
                name="JMComic",
                identity={"platform_label": "JM", "host_id_prefix": "JM"},
            ),
            _FakeManifest(
                plugin_id="video.javdb",
                config_key="javdb",
                legacy_adapter_name="javdb",
                legacy_platforms=["javdb", "JAVDB"],
                media_types=["video"],
                capability_keys=["catalog.search"],
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
                legacy_adapter_name="",
                legacy_platforms=["proxy-provider"],
                media_types=["video"],
                capability_keys=["playback.proxy.stream"],
                name="Proxy Provider",
                identity={"platform_label": "PROXY"},
            )
        ]
    )

    monkeypatch.setattr(compatibility, "get_protocol_gateway", lambda: gateway)

    client = compatibility.get_legacy_playback_proxy_client(proxy_base_path="/api/v1/video")
    assert client["plugin_id"] == "video.proxy-provider"
    assert gateway.legacy_client_requests == [
        {
            "plugin_id": "video.proxy-provider",
            "args": (),
            "kwargs": {"proxy_base_path": "/api/v1/video"},
        }
    ]
