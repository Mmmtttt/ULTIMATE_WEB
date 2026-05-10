import importlib.util
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_provider_module():
    module_path = BACKEND_ROOT / "third_party" / "Missav" / "ultimate_provider.py"
    spec = importlib.util.spec_from_file_location("missav_provider_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load provider from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missav_provider_reads_javdb_cookies_via_protocol_config_store(monkeypatch):
    module = _load_provider_module()

    class FakeStore:
        def get_plugin_config(self, config_key, reload=False):
            assert config_key == "javdb"
            assert reload is True
            return {"cookies": {"_jdb_session": "sess-x", "over18": "1"}}

    monkeypatch.setattr(module, "ProtocolConfigStore", lambda: FakeStore())

    provider = module.MissavProvider(manifest={}, manifest_path="")
    client = provider._get_client(proxy_base_path="/api/v1/video")

    assert client.javdb_cookie_header == "_jdb_session=sess-x; over18=1"
    headers = client._build_proxy_headers("javdb.com", "", None)
    assert headers["Cookie"] == "_jdb_session=sess-x; over18=1"


def test_missav_client_only_adds_cookie_for_javdb_domains(monkeypatch):
    module = _load_provider_module()
    provider = module.MissavProvider(manifest={}, manifest_path="")

    monkeypatch.setattr(provider, "_get_javdb_cookie_header", lambda: "_jdb_session=sess-y; over18=1")
    client = provider._get_client(proxy_base_path="/api/v1/video")

    javdb_headers = client._build_proxy_headers("javdb.com", "", None)
    missav_headers = client._build_proxy_headers("missav.ai", "", None)

    assert javdb_headers["Cookie"] == "_jdb_session=sess-y; over18=1"
    assert "Cookie" not in missav_headers
