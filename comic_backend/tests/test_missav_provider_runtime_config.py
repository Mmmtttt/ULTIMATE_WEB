import base64
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


def test_missav_extract_checks_each_candidate_once_without_retry_backoff(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video")
    calls = []

    class FakePageResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    def fake_get(url, headers=None, timeout=None, impersonate=None):
        calls.append(url)
        if url.endswith("/sone-764-chinese-subtitle"):
            return FakePageResponse(404)
        if url.endswith("/sone-764-uncensored-leak"):
            return FakePageResponse(404)
        if url.endswith("/sone-764"):
            return FakePageResponse(
                200,
                "https://surrit.com/46554ca9-8b3c-426b-b017-34df87681b10/playlist.m3u8",
            )
        if url == "https://surrit.com/46554ca9-8b3c-426b-b017-34df87681b10/playlist.m3u8":
            return FakePageResponse(
                200,
                "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100,RESOLUTION=640x360\n360p/video.m3u8\n",
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(module.cffi_requests, "get", fake_get)

    result, error = client.extract_from_missav("SONE-764")

    assert error is None
    assert result["page_url"] == "https://missav.ai/cn/sone-764"
    assert result["streams"][0]["url"] == "https://surrit.com/46554ca9-8b3c-426b-b017-34df87681b10/360p/video.m3u8"
    assert calls == [
        "https://missav.ai/cn/sone-764-chinese-subtitle",
        "https://missav.ai/cn/sone-764-uncensored-leak",
        "https://missav.ai/cn/sone-764",
        "https://surrit.com/46554ca9-8b3c-426b-b017-34df87681b10/playlist.m3u8",
    ]


def test_missav_extract_continues_after_200_page_without_video_source(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video", missav_domains=["missav.ai"])
    calls = []
    impersonates = []

    class FakePageResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    def fake_get(url, headers=None, timeout=None, impersonate=None):
        calls.append(url)
        impersonates.append(impersonate)
        if url.endswith("/sone-764-chinese-subtitle"):
            return FakePageResponse(200, "<html>not a video page</html>")
        if url.endswith("/sone-764-uncensored-leak"):
            return FakePageResponse(
                200,
                "https://surrit.com/5f5bca10-88e6-468b-bb1e-b68e6cae1756/playlist.m3u8",
            )
        if url == "https://surrit.com/5f5bca10-88e6-468b-bb1e-b68e6cae1756/playlist.m3u8":
            return FakePageResponse(
                200,
                "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=200,RESOLUTION=1280x720\n720p/video.m3u8\n",
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(module.cffi_requests, "get", fake_get)

    result, error = client.extract_from_missav("SONE-764")

    assert error is None
    assert result["page_url"] == "https://missav.ai/cn/sone-764-uncensored-leak"
    assert result["streams"][0]["resolution"] == "1280x720"
    assert calls == [
        "https://missav.ai/cn/sone-764-chinese-subtitle",
        "https://missav.ai/cn/sone-764-uncensored-leak",
        "https://surrit.com/5f5bca10-88e6-468b-bb1e-b68e6cae1756/playlist.m3u8",
    ]
    assert set(impersonates) == {"chrome131"}


def test_missav_proxy_url_streams_media_segments_without_browser_origin_override(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video")
    target_url = "https://surrit.com/video/seg-001.ts"
    encoded_url = base64.b64encode(target_url.encode("utf-8")).decode("utf-8")
    captured = {}

    class FakeStreamingResponse:
        status_code = 206
        headers = {
            "Access-Control-Allow-Origin": "https://missav.ai",
            "Content-Type": "video/mp2t",
            "Content-Range": "bytes 0-3/8",
        }

        @property
        def content(self):
            raise AssertionError("media segment should be streamed, not buffered")

        def iter_content(self, chunk_size=1):
            yield b"abcd"

        def close(self):
            captured["closed"] = True

    def fake_request(method, url, headers=None, stream=False, timeout=None, impersonate=None):
        captured.update(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "stream": stream,
                "timeout": timeout,
                "impersonate": impersonate,
            }
        )
        return FakeStreamingResponse()

    monkeypatch.setattr(module.cffi_requests, "request", fake_request)

    response = client.proxy_url(
        method="GET",
        query_string=f"url={encoded_url}",
        incoming_referer="https://127.0.0.1:5173/video-recommendation/JAVDBEJZW4",
        incoming_headers={
            "Range": "bytes=0-",
            "Accept": "*/*",
            "Origin": "https://127.0.0.1:5173",
            "Referer": "https://127.0.0.1:5173/video-recommendation/JAVDBEJZW4",
            "User-Agent": "mobile-browser-agent",
        },
    )

    assert response.status_code == 206
    assert hasattr(response, "iter_content")
    assert list(response.iter_content(chunk_size=2)) == [b"abcd"]
    assert captured["url"] == target_url
    assert captured["stream"] is True
    assert captured["headers"]["Referer"] == "https://missav.ai/"
    assert captured["headers"]["Origin"] == "https://missav.ai"
    assert captured["headers"]["Range"] == "bytes=0-"
    assert captured["headers"]["Accept"] == "*/*"
    assert captured["headers"]["User-Agent"] != "mobile-browser-agent"


def test_missav_proxy_url_rewrites_m3u8_and_removes_stale_length(monkeypatch):
    module = _load_client_module()
    client = module.MissavClient(proxy_base_path="/api/v1/video")
    target_url = "https://surrit.com/video/index.m3u8"
    encoded_url = base64.b64encode(target_url.encode("utf-8")).decode("utf-8")
    captured = {"closed": False}

    class FakeM3u8Response:
        status_code = 200
        headers = {
            "Access-Control-Allow-Origin": "https://missav.ai",
            "Content-Type": "application/vnd.apple.mpegurl",
            "Content-Length": "17",
            "Connection": "keep-alive",
        }
        content = (
            b"#EXTM3U\n"
            b"#EXT-X-KEY:METHOD=AES-128,URI=\"key.key\"\n"
            b"#EXTINF:3,\n"
            b"seg-001.ts\n"
        )

        def close(self):
            captured["closed"] = True

    def fake_request(method, url, headers=None, stream=False, timeout=None, impersonate=None):
        captured["stream"] = stream
        return FakeM3u8Response()

    monkeypatch.setattr(module.cffi_requests, "request", fake_request)

    response = client.proxy_url(method="GET", query_string=f"url={encoded_url}")
    header_names = {name.lower() for name, _ in response.headers}
    text = response.content.decode("utf-8")

    assert response.status_code == 200
    assert captured["stream"] is True
    assert captured["closed"] is True
    assert "access-control-allow-origin" not in header_names
    assert "content-length" not in header_names
    assert "connection" not in header_names
    assert "/api/v1/video/proxy2?url=" in text
    assert "seg-001.ts" not in text
