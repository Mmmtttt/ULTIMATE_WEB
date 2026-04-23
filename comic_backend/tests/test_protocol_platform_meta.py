import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import protocol.platform_meta as platform_meta_module
from core.platform import (
    add_platform_prefix,
    get_original_id,
    get_platform_download_dir,
    get_platform_from_id,
    get_supported_platforms,
    get_video_platforms,
    remove_platform_prefix,
)
from protocol.platform_meta import (
    build_platform_root_dir,
    get_capability_default_params,
    resolve_platform_manifest,
    split_prefixed_id,
)


def test_split_prefixed_id_resolves_registered_comic_manifest():
    platform_key, original_id, manifest = split_prefixed_id("JM100001", media_type="comic")

    assert platform_key == "JM"
    assert original_id == "100001"
    assert manifest is not None
    assert manifest.plugin_id == "comic.jmcomic"


def test_build_platform_root_dir_uses_manifest_host_prefix():
    manifest = resolve_platform_manifest("PK", media_type="comic")
    result = build_platform_root_dir("D:/tmp/runtime-root", manifest=manifest)

    normalized = str(result).replace("\\", "/")
    assert normalized.endswith("/PK")


def test_capability_default_params_reads_manifest_defaults():
    manifest = resolve_platform_manifest("JM", media_type="comic")

    assert get_capability_default_params(manifest, "asset.bundle.fetch") == {
        "decode_images": True,
    }


def test_core_platform_uses_protocol_platform_strings_for_manifest_only_video_plugin():
    platform_key, original_id = remove_platform_prefix("MISSAVABP123")

    assert platform_key == "MISSAV"
    assert original_id == "ABP123"
    assert get_platform_from_id("MISSAVABP123") == "MISSAV"
    assert get_original_id("MISSAVABP123") == "ABP123"
    assert add_platform_prefix("missav", "ABP123") == "MISSAVABP123"
    assert str(get_platform_download_dir("missav", "D:/tmp/runtime-root")).replace("\\", "/").endswith("/MISSAV")


def test_core_platform_lists_include_manifest_registered_video_plugin():
    assert "MISSAV" in get_video_platforms()
    assert "MISSAV" in get_supported_platforms()


def test_split_prefixed_id_uses_internal_legacy_prefix_fallback_without_core_platform(monkeypatch):
    class _EmptyGateway:
        def list_manifests(self, media_type=None, capability=None):
            return []

        def get_manifest_by_legacy_platform(self, *_args, **_kwargs):
            return None

        def get_manifest_by_config_key(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(platform_meta_module, "get_protocol_gateway", lambda: _EmptyGateway())

    platform_key, original_id, manifest = split_prefixed_id("JAVDBABP123", media_type="video")

    assert platform_key == "JAVDB"
    assert original_id == "ABP123"
    assert manifest is None
