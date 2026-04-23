from __future__ import annotations

import os


def pytest_configure(_config) -> None:
    from tests.tools.prepare_test_env import prepare_profile

    prepared = prepare_profile("collection_bootstrap", clean=True)
    runtime_root = str(prepared["runtime_root"])

    os.environ.setdefault("ULTIMATE_CONFIG_DIR", runtime_root)
    os.environ.setdefault("SERVER_CONFIG_PATH", prepared["server_config_path"])
    os.environ.setdefault("THIRD_PARTY_CONFIG_PATH", prepared["third_party_config_path"])
