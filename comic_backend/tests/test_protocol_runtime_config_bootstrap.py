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
    assert store.get_default_adapter() == "jmcomic"

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    adapters = dict(persisted.get("adapters") or {})

    assert persisted.get("default_adapter") == "jmcomic"
    assert bool(adapters.get("jmcomic", {}).get("enabled")) is True
    assert "config_path" not in dict(adapters.get("jmcomic") or {})
    assert str(adapters.get("jmcomic", {}).get("download_dir") or "").replace("\\", "/").endswith("/comic/JM")
    assert bool(adapters.get("picacomic", {}).get("enabled")) is True
    assert str(adapters.get("picacomic", {}).get("base_dir") or "").replace("\\", "/").endswith("/comic/PK")
    assert bool(adapters.get("javdb", {}).get("enabled")) is True


def test_protocol_config_store_preserves_custom_subdir_and_scrubs_legacy_fields(tmp_path):
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps(
            {
                "default_adapter": "jmcomic",
                "adapters": {
                    "jmcomic": {
                        "enabled": True,
                        "download_dir": "comic/JM-custom",
                        "config_path": "JMComic-Crawler-Python/config.json",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = ProtocolConfigStore(str(config_path))
    config = store.get_plugin_config("jmcomic")
    assert "config_path" not in config
    assert str(config.get("download_dir") or "").replace("\\", "/").endswith("/comic/JM-custom")

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    jm_config = dict((persisted.get("adapters") or {}).get("jmcomic") or {})
    assert "config_path" not in jm_config
    assert str(jm_config.get("download_dir") or "").replace("\\", "/").endswith("/comic/JM-custom")
