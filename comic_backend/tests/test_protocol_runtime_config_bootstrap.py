import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from third_party.legacy.adapter_factory import AdapterConfig


def test_adapter_config_bootstraps_protocol_defaults_from_empty_config(tmp_path):
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text('{"default_adapter":"","adapters":{}}', encoding="utf-8")

    manager = AdapterConfig(str(config_path))

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    adapters = dict(persisted.get("adapters") or {})

    assert manager.get_default_adapter() == "jmcomic"
    assert persisted.get("default_adapter") == "jmcomic"
    assert bool(adapters.get("jmcomic", {}).get("enabled")) is True
    assert str(adapters.get("jmcomic", {}).get("download_dir") or "").replace("\\", "/").endswith("/comic/JM")
    assert bool(adapters.get("picacomic", {}).get("enabled")) is True
    assert str(adapters.get("picacomic", {}).get("base_dir") or "").replace("\\", "/").endswith("/comic/PK")
    assert bool(adapters.get("javdb", {}).get("enabled")) is True
