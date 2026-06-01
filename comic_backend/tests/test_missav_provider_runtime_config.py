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


def _load_client_module():
    module_path = BACKEND_ROOT / "third_party" / "Missav" / "missav" / "client.py"
    module_name = "missav_client_for_tests"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load client from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
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


def test_jable_extract_uses_browser_fallback_when_http_page_hits_cloudflare(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video")

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    def fake_get(url, headers=None, timeout=None, impersonate=None):
        if url == "https://jable.tv/videos/abp-123/":
            return FakeResponse(403, "<html><title>Just a moment...</title></html>")
        if url == "https://cdn.example/master.m3u8":
            return FakeResponse(
                200,
                "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1024,RESOLUTION=1280x720\nstream-720p.m3u8\n",
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(module.cffi_requests, "get", fake_get)
    monkeypatch.setattr(
        client,
        "_fetch_jable_page_with_playwright",
        lambda page_url, headers=None: (
            "<script>var hlsUrl = 'https://cdn.example/master.m3u8'</script>",
            None,
        ),
    )

    result, error = client.extract_from_jable("ABP-123")

    assert error is None
    assert result["source"] == "Jable"
    assert result["browser_fallback"] is True
    assert result["m3u8_url"] == "https://cdn.example/master.m3u8"
    assert result["streams"][0]["url"] == "https://cdn.example/stream-720p.m3u8"


def test_jable_extract_keeps_fast_http_path_when_page_already_contains_hls(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video")

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    def fake_get(url, headers=None, timeout=None, impersonate=None):
        if url == "https://jable.tv/videos/ipx-001/":
            return FakeResponse(
                200,
                "<script>var hlsUrl = 'https://cdn.example/ipx001/master.m3u8'</script>",
            )
        if url == "https://cdn.example/ipx001/master.m3u8":
            return FakeResponse(
                200,
                "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2048,RESOLUTION=1920x1080\n1080p.m3u8\n",
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(module.cffi_requests, "get", fake_get)

    def fail_browser_fallback(*args, **kwargs):
        raise AssertionError("browser fallback should not run when HTTP page already contains hlsUrl")

    monkeypatch.setattr(client, "_fetch_jable_page_with_playwright", fail_browser_fallback)

    result, error = client.extract_from_jable("IPX-001")

    assert error is None
    assert result["browser_fallback"] is False
    assert result["m3u8_url"] == "https://cdn.example/ipx001/master.m3u8"
    assert result["streams"][0]["url"] == "https://cdn.example/ipx001/1080p.m3u8"
