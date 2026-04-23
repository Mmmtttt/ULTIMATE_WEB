from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_javdb_api_class():
    backend_root = Path(__file__).resolve().parents[1]
    plugin_root = backend_root / "third_party" / "javdb-api-scraper"
    plugin_path = str(plugin_root)
    if plugin_path not in sys.path:
        sys.path.insert(0, plugin_path)

    module_name = "test_javdb_api_runtime"
    api_path = plugin_root / "javdb_api.py"
    spec = importlib.util.spec_from_file_location(module_name, api_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.JavdbAPI


def _load_javdb_provider_class():
    provider_path = (
        Path(__file__).resolve().parents[1]
        / "third_party"
        / "javdb-api-scraper"
        / "ultimate_provider.py"
    )
    module_name = "test_javdb_provider_protocol_runtime"
    spec = importlib.util.spec_from_file_location(module_name, provider_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.JavdbProvider, str(provider_path)


def test_javdb_provider_health_status_reports_cookie_keys():
    JavdbProvider, provider_path = _load_javdb_provider_class()
    provider = JavdbProvider({}, provider_path)

    result = provider.execute(
        "health.query.status",
        params={},
        context={},
        config={
            "enabled": True,
            "cookies": {
                "over18": "1",
                "_jdb_session": "sess-abc",
                "locale": "zh",
            },
        },
    )

    assert result["configured"] is True
    assert result["has_session_cookie"] is True
    assert result["cookie_keys"] == ["_jdb_session", "locale", "over18"]


def test_javdb_provider_taxonomy_tags_filters_keyword_and_category(monkeypatch):
    JavdbProvider, provider_path = _load_javdb_provider_class()
    provider = JavdbProvider({}, provider_path)

    class FakeTagManager:
        def get_all_tags(self):
            return {
                "c1=1": {"name": "Action Star", "category": "c1", "category_name": "C1", "tag_id": "1", "value": "1"},
                "c1=2": {"name": "Drama", "category": "c1", "category_name": "C1", "tag_id": "2", "value": "2"},
                "c2=3": {"name": "Action Else", "category": "c2", "category_name": "C2", "tag_id": "3", "value": "3"},
            }

        def get_categories(self):
            return {"c1": "C1", "c2": "C2"}

    class FakeAdapter:
        def __init__(self):
            self.api = SimpleNamespace(tag_manager=FakeTagManager())

    monkeypatch.setattr(provider, "_get_adapter", lambda *_args, **_kwargs: FakeAdapter())
    monkeypatch.setattr(provider, "_is_tag_search_available", lambda *_args, **_kwargs: True)

    result = provider.execute(
        "taxonomy.tags",
        params={"keyword": "act", "category": "c1"},
        context={},
        config={"enabled": True, "cookies": {"_jdb_session": "sess-x", "over18": "1"}},
    )

    assert result["cookie_configured"] is True
    assert result["source_ready"] is True
    assert result["tag_search_available"] is True
    assert len(result["tags"]) == 1
    assert result["tags"][0]["id"] == "c1=1"
    assert result["categories"] == [{"key": "c1", "name": "C1", "count": 1}]


def test_javdb_provider_taxonomy_tag_search_parses_ids_and_builds_query(monkeypatch):
    JavdbProvider, provider_path = _load_javdb_provider_class()
    provider = JavdbProvider({}, provider_path)
    requested_paths = []

    class FakeJavdbApi:
        def get(self, path):
            requested_paths.append(path)
            html = '<html><body><div class="item"><a href="/v/1"></a></div></body></html>'
            return SimpleNamespace(text=html)

        def _parse_work_item(self, _item):
            return {"video_id": "J1", "title": "JAVDB-Work"}

    class FakeAdapter:
        def __init__(self):
            self.api = FakeJavdbApi()

    monkeypatch.setattr(provider, "_get_adapter", lambda *_args, **_kwargs: FakeAdapter())
    monkeypatch.setattr(provider, "_is_tag_search_available", lambda *_args, **_kwargs: True)

    result = provider.execute(
        "taxonomy.tag_search",
        params={"page": 2, "tag_ids": ["c4=22,19", "c1=23"]},
        context={},
        config={"enabled": True, "cookies": {"_jdb_session": "sess-x", "over18": "1"}},
    )

    assert result["effective_tag_ids"] == ["c1=23", "c4=22", "c4=19"]
    assert result["invalid_tag_ids"] == []
    assert result["query"] == "c1=23&c4=22,19"
    assert requested_paths[-1] == "/tags?c1=23&c4=22,19&page=2"
    assert result["videos"] == [{"video_id": "J1", "title": "JAVDB-Work"}]


def test_javdb_provider_taxonomy_tag_search_requires_login(monkeypatch):
    JavdbProvider, provider_path = _load_javdb_provider_class()
    provider = JavdbProvider({}, provider_path)

    class FakeAdapter:
        api = SimpleNamespace()

    monkeypatch.setattr(provider, "_get_adapter", lambda *_args, **_kwargs: FakeAdapter())
    monkeypatch.setattr(provider, "_is_tag_search_available", lambda *_args, **_kwargs: False)

    with pytest.raises(PermissionError):
        provider.execute(
            "taxonomy.tag_search",
            params={"page": 1, "tag_ids": ["c1=23"]},
            context={},
            config={"enabled": True, "cookies": {"_jdb_session": "sess-x", "over18": "1"}},
        )


def test_javdb_api_extracts_preview_video_from_nested_source_element(monkeypatch):
    JavdbAPI = _load_javdb_api_class()
    api = JavdbAPI(domain_index=0)
    html = """
    <html>
      <body>
        <div class="columns">
          <article class="message video-panel">
            <div class="message-body">
              <div class="tile-images preview-images">
                <a class="preview-video-container" href="#preview-video"></a>
                <video id="preview-video" playsinline controls muted preload="auto" style="display:none">
                  <source src="https://javdb.com/movies/ttm3u8/preview/389838/0/720p.m3u8?sign=test-sign&t=1776962800" type="application/x-mpegURL" />
                </video>
              </div>
            </div>
          </article>
        </div>
      </body>
    </html>
    """

    monkeypatch.setattr(
        api,
        "get",
        lambda path: SimpleNamespace(text=html, url=f"https://javdb.com{path}"),
    )

    detail = api.get_video_detail("YwG8Ve", download_images=False)

    assert detail["preview_video"].startswith("https://javdb.com/movies/ttm3u8/preview/")
    assert "sign=test-sign" in detail["preview_video"]
