import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import protocol.platform_meta as platform_meta_module
import protocol.gateway as gateway_module
from core.platform import (
    add_platform_prefix,
    get_original_id,
    get_platform_download_dir,
    get_platform_from_id,
    get_supported_platforms,
    get_video_platforms,
    remove_platform_prefix,
)
from protocol.base import PluginManifest
from protocol.platform_meta import (
    build_platform_root_dir,
    get_capability_default_params,
    resolve_platform_manifest,
    split_prefixed_id,
)


def _make_manifest(plugin_id, media_type, host_prefix, label, config_key=None, capabilities=None):
    return PluginManifest(
        raw={
            "protocol_version": "2.0",
            "plugin": {
                "id": plugin_id,
                "name": plugin_id,
                "version": "1.0.0",
                "entrypoint": "protocol.snapshot_provider:MetadataOnlyProvider",
                "config_key": config_key or plugin_id.rsplit(".", 1)[-1],
            },
            "media_types": [media_type],
            "identity": {
                "host_id_prefix": host_prefix,
                "platform_label": label,
                "aliases": [str(config_key or "").strip()] if config_key else [],
            },
            "capabilities": list(capabilities or []),
        },
        path="",
    )


class _FakeGateway:
    def __init__(self, manifests):
        self._manifests = list(manifests)

    def list_manifests(self, media_type=None, capability=None):
        results = list(self._manifests)
        if media_type:
            media_key = str(media_type or "").strip().lower()
            results = [item for item in results if media_key in {str(mt).lower() for mt in item.media_types}]
        if capability:
            results = [item for item in results if item.has_capability(capability)]
        return results

    def get_manifest_by_config_key(self, config_key):
        lookup = str(config_key or "").strip().lower()
        for manifest in self._manifests:
            if str(manifest.config_key or "").strip().lower() == lookup:
                return manifest
        return None

    def get_manifest_by_lookup(self, lookup_name, media_type=None, capability=None):
        lookup = str(lookup_name or "").strip().lower()
        for manifest in self.list_manifests(media_type=media_type, capability=capability):
            candidates = {str(item or "").strip().lower() for item in manifest.list_lookup_names()}
            if lookup in candidates:
                return manifest
        return None


def _install_fake_gateway(monkeypatch):
    gateway = _FakeGateway(
        [
            _make_manifest(
                "comic.alpha",
                "comic",
                "CA",
                "CA",
                config_key="comic_alpha",
                capabilities=[{"key": "asset.bundle.fetch", "default_params": {"decode_images": True}}],
            ),
            _make_manifest("comic.beta", "comic", "CB", "CB", config_key="comic_beta"),
            _make_manifest("video.alpha", "video", "VA", "VA", config_key="video_alpha"),
        ]
    )
    monkeypatch.setattr(platform_meta_module, "get_protocol_gateway", lambda: gateway)
    monkeypatch.setattr(gateway_module, "get_protocol_gateway", lambda: gateway)
    return gateway


def test_split_prefixed_id_resolves_registered_comic_manifest(monkeypatch):
    _install_fake_gateway(monkeypatch)

    platform_key, original_id, manifest = split_prefixed_id("CA100001", media_type="comic")

    assert platform_key == "CA"
    assert original_id == "100001"
    assert manifest is not None
    assert manifest.plugin_id == "comic.alpha"


def test_build_platform_root_dir_uses_manifest_host_prefix(monkeypatch):
    _install_fake_gateway(monkeypatch)

    manifest = resolve_platform_manifest("CB", media_type="comic")
    result = build_platform_root_dir("D:/tmp/runtime-root", manifest=manifest)

    normalized = str(result).replace("\\", "/")
    assert normalized.endswith("/CB")


def test_capability_default_params_reads_manifest_defaults(monkeypatch):
    _install_fake_gateway(monkeypatch)

    manifest = resolve_platform_manifest("CA", media_type="comic")

    assert get_capability_default_params(manifest, "asset.bundle.fetch") == {
        "decode_images": True,
    }


def test_core_platform_uses_protocol_platform_strings_for_manifest_only_video_plugin(monkeypatch):
    _install_fake_gateway(monkeypatch)

    platform_key, original_id = remove_platform_prefix("VAABP123")

    assert platform_key == "VA"
    assert original_id == "ABP123"
    assert get_platform_from_id("VAABP123") == "VA"
    assert get_original_id("VAABP123") == "ABP123"
    assert add_platform_prefix("VA", "ABP123") == "VAABP123"
    assert str(get_platform_download_dir("VA", "D:/tmp/runtime-root")).replace("\\", "/").endswith("/VA")


def test_core_platform_lists_include_manifest_registered_video_plugin(monkeypatch):
    _install_fake_gateway(monkeypatch)

    assert "VA" in get_video_platforms()
    assert "VA" in get_supported_platforms()


def test_split_prefixed_id_returns_unresolved_when_registry_empty(monkeypatch):
    class _EmptyGateway:
        def list_manifests(self, media_type=None, capability=None):
            return []

        def get_manifest_by_config_key(self, *_args, **_kwargs):
            return None

        def get_manifest_by_lookup(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(platform_meta_module, "get_protocol_gateway", lambda: _EmptyGateway())

    platform_key, original_id, manifest = split_prefixed_id("VAABP123", media_type="video")

    assert platform_key == ""
    assert original_id == "VAABP123"
    assert manifest is None
