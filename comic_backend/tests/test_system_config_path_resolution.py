import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("ULTIMATE_CONFIG_DIR", str(BACKEND_ROOT / ".pytest_runtime_config"))

import api.v1.config as config_api
from core.constants import DEFAULT_SERVER_CONFIG, resolve_configured_data_dir


def test_config_api_uses_runtime_default_server_config():
    assert config_api._default_server_config() == DEFAULT_SERVER_CONFIG


def test_config_api_resolve_data_dir_matches_runtime_logic():
    assert config_api._resolve_data_dir("./../UltimateData") == resolve_configured_data_dir("./../UltimateData")
    assert config_api._resolve_data_dir("./custom_data_root") == resolve_configured_data_dir("./custom_data_root")
    assert config_api._resolve_data_dir("D:/tmp/ultimate-data-root") == resolve_configured_data_dir("D:/tmp/ultimate-data-root")
