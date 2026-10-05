import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.runtime_config import ProtocolConfigStore


def test_protocol_config_store_bootstraps_protocol_defaults_from_empty_config(tmp_path):
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text('{"default_adapter":"","adapters":{}}', encoding="utf-8")

    store = ProtocolConfigStore(str(config_path))
    manifests = store._list_protocol_manifests()
    comic_manifests = [
        manifest for manifest in manifests if "comic" in set(manifest.media_types or [])
    ]
    assert comic_manifests
    default_key = str(comic_manifests[0].config_key)
    assert store.get_default_adapter() == default_key

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    adapters = dict(persisted.get("adapters") or {})

    assert persisted.get("default_adapter") == default_key
    for manifest in manifests:
        config_key = str(manifest.config_key)
        config = dict(adapters.get(config_key) or {})
        if manifest.plugin_id.startswith("storage."):
            continue
        assert config.get("enabled") is False
        for binding in manifest.list_data_dir_bindings():
            field_name = str(binding.get("config_field") or binding.get("field") or "")
            if field_name:
                assert str(config.get(field_name) or "").strip()


def test_protocol_config_store_preserves_custom_subdir_and_scrubs_legacy_fields(tmp_path):
    config_path = tmp_path / "third_party_config.json"
    config_key = str(ProtocolConfigStore._list_protocol_manifests()[0].config_key)
    config_path.write_text(
        json.dumps(
            {
                "default_adapter": config_key,
                "adapters": {
                    config_key: {
                        "enabled": True,
                        "download_dir": "comic/synthetic-custom",
                        "config_path": "synthetic/config.json",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = ProtocolConfigStore(str(config_path))
    config = store.get_plugin_config(config_key)
    assert "config_path" not in config
    assert config.get("enabled") is True
    assert str(config.get("download_dir") or "").replace("\\", "/").endswith("/comic/synthetic-custom")

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    synthetic_config = dict((persisted.get("adapters") or {}).get(config_key) or {})
    assert "config_path" not in synthetic_config
    assert synthetic_config.get("enabled") is True
    assert str(synthetic_config.get("download_dir") or "").replace("\\", "/").endswith("/comic/synthetic-custom")
