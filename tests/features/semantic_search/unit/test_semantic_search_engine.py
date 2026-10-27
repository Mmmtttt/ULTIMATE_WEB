from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[4] / "comic_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TAGS_DOCUMENT = {
    "tags": [
        {"id": "t1", "name": "双胞胎", "kind": "人物", "aliases": ["双生", "姊妹"]},
        {"id": "t2", "name": "女仆", "kind": "人物", "aliases": ["女仆装"]},
        {"id": "t3", "name": "精灵", "kind": "人物"},
        {"id": "t4", "name": "奇幻", "kind": "题材"},
    ]
}

COMICS_DOCUMENT = {
    "comics": [
        {
            "id": "c1",
            "title": "双胞胎女仆的日常",
            "author": "作者A",
            "desc": "双胞胎姐妹和女仆一起服侍主人的甜腻故事",
            "vibe": "双胞胎姐妹和一名女仆共同生活的纯爱日常，甜腻而温柔。",
            "catalog": "楓與鈴2 雙胞胎女僕；女僕的一天；文化祭咖啡廳",
            "tag_ids": ["t1", "t2"],
        },
        {
            "id": "c2",
            "title": "女仆的一天",
            "author": "作者B",
            "desc": "一名女仆打扫房间的安静日常",
            "tag_ids": ["t2"],
        },
        {
            "id": "c3",
            "title": "精灵的地下城冒险",
            "author": "作者C",
            "desc": "精灵骑士在迷宫深处与怪物搏斗的奇幻故事",
            "tag_ids": ["t3", "t4"],
        },
    ]
}


class StubEmbedder:
    """可控向量：用来验证向量路不依赖 onnxruntime。"""

    def __init__(self) -> None:
        self.model_name = "stub-model"
        self.available = True
        self.reason = ""
        self._dim = 3

    @property
    def dim(self) -> int:
        return self._dim

    @staticmethod
    def _vectorize(text: str) -> list[float]:
        text = str(text or "")
        if "双胞胎" in text or "姐妹" in text:
            return [1.0, 0.0, 0.0]
        if "精灵" in text or "地下城" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts, batch_size: int = 64):
        import struct

        packed = []
        for text in texts:
            values = self._vectorize(text)
            blob = struct.pack(f"<{len(values)}f", *values)
            packed.append((blob, sum(value * value for value in values) ** 0.5))
        return packed

    def embed_query(self, text: str):
        return self._vectorize(text)


@pytest.fixture()
def meta_dir(tmp_path, monkeypatch):
    import infrastructure.persistence.semantic_index.builder as builder
    import infrastructure.persistence.semantic_index.connection as connection

    target = tmp_path / "meta_data"
    target.mkdir()
    (target / "tags_database.json").write_text(
        json.dumps(TAGS_DOCUMENT, ensure_ascii=False), encoding="utf-8"
    )
    (target / "comics_database.json").write_text(
        json.dumps(COMICS_DOCUMENT, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(connection, "get_meta_dir", lambda mode=None: str(target))
    monkeypatch.setattr(builder, "get_meta_dir", lambda mode=None: str(target))
    return target


def _build(embedder=None):
    from infrastructure.persistence.semantic_index import open_semantic_index, rebuild_index

    conn = open_semantic_index()
    stats = rebuild_index(conn, embedder, build_embeddings=embedder is not None)
    return conn, stats


def test_build_index_reads_library_documents(meta_dir):
    conn, stats = _build()
    try:
        assert stats["doc_count"] == 3
        assert stats["vector_enabled"] is False
        assert stats["search_index"] in {"fts5_trigram", "like_scan"}
        assert conn.execute("SELECT COUNT(*) AS c FROM semantic_item_tag").fetchone()["c"] == 5
    finally:
        conn.close()


def test_hybrid_search_ranks_by_tag_and_keyword(meta_dir):
    from infrastructure.persistence.semantic_index import search

    conn, _ = _build()
    try:
        payload = search(conn, "双胞胎女仆一起伺候主人", source="local", limit=5)
        ids = [item["item_id"] for item in payload["results"]]
        assert ids[0] == "c1"
        assert "c2" in ids
        assert payload["debug"]["hit_tags"] == ["双胞胎", "女仆"]
        assert payload["debug"]["route_sizes"]["tag"] == 2
    finally:
        conn.close()


def test_chinese_sentence_falls_back_to_bigram_matching(meta_dir):
    from infrastructure.persistence.semantic_index import search

    conn, _ = _build()
    try:
        payload = search(conn, "精灵在迷宫深处战斗", source="local", limit=5)
        ids = [item["item_id"] for item in payload["results"]]
        assert ids == ["c3"]
        assert payload["debug"]["route_sizes"]["keyword"] >= 1
    finally:
        conn.close()


def test_tag_alias_matches_official_tag(meta_dir):
    """「姊妹」是「双胞胎」的同义词，应把 t1 的书命中为标签路第 1 名。"""
    from infrastructure.persistence.semantic_index import search

    conn, _ = _build()
    try:
        payload = search(conn, "想找姊妹一起的那种", source="local", limit=5)
        assert payload["debug"]["hit_tags"] == ["双胞胎"]
        assert payload["results"][0]["item_id"] == "c1"
        assert payload["results"][0]["routes"]["tag"] == 0
    finally:
        conn.close()


def test_catalog_feeds_keyword_but_not_vector_text(meta_dir):
    """篇名速览只进关键词索引；气质梗概才进向量正文。"""
    from infrastructure.persistence.semantic_index import (
        build_search_text,
        build_vector_text,
        normalize,
        search,
    )

    vector_text = build_vector_text("书名", "", "作者", "一段气质梗概", ["标签一"])
    assert "一段气质梗概" in vector_text and "标签一" in vector_text

    catalog = "楓與鈴2 篇名速览"
    search_text = build_search_text("c1", "书名", "", "作者", catalog, "简介", [], [])
    assert normalize(catalog) in search_text  # 篇名只在关键词侧（可能已简繁归一）

    conn, _ = _build()
    try:
        payload = search(conn, "楓與鈴", source="local", limit=5)
        assert payload["results"][0]["item_id"] == "c1"
        assert payload["debug"]["route_sizes"]["keyword"] >= 1
        # 向量正文里不含 catalog
        row = conn.execute(
            "SELECT doc_text, catalog_text FROM semantic_item WHERE item_id='c1'"
        ).fetchone()
        assert normalize("楓與鈴") not in normalize(row["doc_text"])
        assert normalize("楓與鈴") in normalize(row["catalog_text"])
    finally:
        conn.close()


def test_vector_route_works_with_injected_embedder(meta_dir):
    from infrastructure.persistence.semantic_index import search

    conn, stats = _build(embedder=StubEmbedder())
    try:
        assert stats["vector_enabled"] is True
        assert stats["embedded_count"] == 3
        assert stats["embed_dim"] == 3

        payload = search(conn, "想找姐妹一起的那种", source="local", limit=5, embedder=StubEmbedder())
        assert payload["debug"]["vector_state"] == "ok"
        assert payload["results"][0]["item_id"] == "c1"
        assert payload["results"][0]["routes"]["vector"] == 0
    finally:
        conn.close()


def test_index_detects_stale_when_document_changes(meta_dir):
    from infrastructure.persistence.semantic_index import is_stale, open_semantic_index

    _build()[0].close()
    conn = open_semantic_index()
    try:
        assert is_stale(conn) is False
        payload = dict(COMICS_DOCUMENT)
        payload["comics"] = COMICS_DOCUMENT["comics"][:2]
        (Path(meta_dir) / "comics_database.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        assert is_stale(conn) is True
    finally:
        conn.close()


def test_search_engine_config_defaults_and_validation():
    from domain.config.entity import (
        SEARCH_ENGINE_CATALOG,
        SEARCH_ENGINE_SEMANTIC,
        UserConfig,
    )

    config = UserConfig()
    assert config.search_engine == SEARCH_ENGINE_CATALOG
    assert config.to_dict()["search_engine"] == SEARCH_ENGINE_CATALOG

    assert config.update(search_engine=SEARCH_ENGINE_SEMANTIC) is True
    assert config.search_engine == SEARCH_ENGINE_SEMANTIC

    assert config.update(search_engine="bogus") is False
    assert config.search_engine == SEARCH_ENGINE_SEMANTIC

    assert UserConfig.from_dict({"search_engine": "BOGUS"}).search_engine == SEARCH_ENGINE_CATALOG
    assert UserConfig.from_dict({"search_engine": "semantic"}).search_engine == SEARCH_ENGINE_SEMANTIC

    config.reset()
    assert config.search_engine == SEARCH_ENGINE_CATALOG


class _FakeConfigRepo:
    def __init__(self, engine: str) -> None:
        self._engine = engine

    def get(self):
        from domain.config.entity import UserConfig

        return UserConfig(search_engine=self._engine)


def test_semantic_service_disabled_on_mobile_core(monkeypatch, meta_dir):
    from application.semantic_search_app_service import SemanticSearchAppService

    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "mobile_core")
    service = SemanticSearchAppService(config_repo=_FakeConfigRepo("semantic"), embedder=StubEmbedder())

    assert service.platform_supported() is False
    assert service.is_enabled() is False
    assert service.search("双胞胎女仆") is None

    status = service.get_status()
    assert status["supported"] is False
    assert status["reason"]


def test_semantic_service_returns_ranked_ids_on_desktop(monkeypatch, meta_dir):
    from application.semantic_search_app_service import SemanticSearchAppService

    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)
    service = SemanticSearchAppService(config_repo=_FakeConfigRepo("semantic"), embedder=StubEmbedder())

    assert service.is_enabled() is True
    ids = service.search("双胞胎女仆一起伺候主人", limit=5)
    assert ids and ids[0] == "c1"

    status = service.get_status()
    assert status["supported"] is True
    assert status["enabled"] is True
    assert status["index"]["indexed"] is True


def test_catalog_engine_never_touches_semantic_index(monkeypatch, meta_dir):
    from application.semantic_search_app_service import SemanticSearchAppService

    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)
    service = SemanticSearchAppService(config_repo=_FakeConfigRepo("catalog"), embedder=StubEmbedder())
    assert service.is_enabled() is False
    assert service.search("双胞胎女仆") is None


def test_comic_service_semantic_order_helper():
    from application.comic_app_service import ComicAppService

    class _FakeSemanticService:
        def __init__(self, ids):
            self._ids = ids

        def is_enabled(self):
            return True

        def search(self, keyword, **_kwargs):
            return self._ids

    service = ComicAppService()
    service._semantic_search_service = _FakeSemanticService(["c3", "c1"])

    assert service._semantic_ranked_ids("女仆") == {"c3": 0, "c1": 1}
    assert service._semantic_ranked_ids("") is None

    service._semantic_search_service = _FakeSemanticService([])
    assert service._semantic_ranked_ids("女仆") is None


def test_comic_entity_round_trips_vibe_and_catalog():
    from domain.comic import Comic

    comic = Comic.from_dict({
        "id": "c1",
        "title": "书名",
        "author": "作者",
        "vibe": "整本的气质梗概",
        "catalog": "篇名速览一、篇名速览二",
    })
    assert comic.vibe == "整本的气质梗概"
    assert comic.catalog == "篇名速览一、篇名速览二"

    payload = comic.to_dict()
    assert payload["vibe"] == "整本的气质梗概"
    assert payload["catalog"] == "篇名速览一、篇名速览二"

    comic.update_meta({"vibe": "新的梗概", "catalog": "新的速览"})
    assert comic.vibe == "新的梗概"
    assert comic.catalog == "新的速览"

    # 老数据没有这两个字段时不能炸
    legacy = Comic.from_dict({"id": "c2", "title": "老数据"})
    assert legacy.vibe == "" and legacy.catalog == ""


def test_schema_migrates_v1_index_to_v2(meta_dir):
    """老索引（v1，没有 vibe_text/catalog_text 列）打开时应自动补列。"""
    import sqlite3

    from infrastructure.persistence.semantic_index import open_semantic_index

    db_path = Path(meta_dir) / "semantic_index.db"
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE semantic_item (
            item_key TEXT PRIMARY KEY,
            media_type TEXT NOT NULL,
            source TEXT NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            is_deleted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE semantic_item_tag (
            item_key TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            tag_name TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (item_key, tag_id)
        );
        """
    )
    legacy.commit()
    legacy.close()

    conn = open_semantic_index()
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(semantic_item)")}
        tag_columns = {row[1] for row in conn.execute("PRAGMA table_info(semantic_item_tag)")}
        assert {"vibe_text", "catalog_text"} <= columns
        assert "tag_kind" in tag_columns
    finally:
        conn.close()


def test_vector_route_drops_unrelated_items(meta_dir):
    """相似度低于阈值/离首名太远的条目不应该混进结果。"""
    from infrastructure.persistence.semantic_index import search

    conn, _ = _build(embedder=StubEmbedder())
    try:
        payload = search(conn, "想找姐妹一起的那种", source="local", limit=10, embedder=StubEmbedder())
        ids = [item["item_id"] for item in payload["results"]]
        # 只有 c1 的向量与查询同向，其余同向分量为 0，必须被阈值挡掉
        assert ids == ["c1"]
        assert payload["debug"]["vector_state"] == "ok"
        assert payload["debug"]["vector_stats"]["kept"] == 1
    finally:
        conn.close()
