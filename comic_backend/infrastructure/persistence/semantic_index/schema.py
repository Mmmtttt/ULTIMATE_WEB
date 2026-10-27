from __future__ import annotations

import sqlite3

SCHEMA_VERSION = "2"

# 语义索引独立于 catalog index：同一份 JSON 文档，另一套检索结构。
# 字段分工照抄「书级语义库」的经验：
#   vibe    —— 整本气质梗概，只喂向量（长名单会稀释向量，所以不进这里）
#   catalog —— 收录速览 / 篇名清单，只喂关键词索引
#   tags    —— 受控词表（含 kind 与同义词），走标签路 + 拼进向量文本
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS semantic_meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_source (
    logical_name TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    mtime_ns     INTEGER NOT NULL,
    indexed_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_item (
    item_key     TEXT PRIMARY KEY,
    media_type   TEXT NOT NULL,
    source       TEXT NOT NULL,
    item_id      TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    title_jp     TEXT NOT NULL DEFAULT '',
    creator      TEXT NOT NULL DEFAULT '',
    desc_text    TEXT NOT NULL DEFAULT '',
    vibe_text    TEXT NOT NULL DEFAULT '',
    catalog_text TEXT NOT NULL DEFAULT '',
    tag_text     TEXT NOT NULL DEFAULT '',
    search_text  TEXT NOT NULL DEFAULT '',
    doc_text     TEXT NOT NULL DEFAULT '',
    embed        BLOB,
    embed_norm   REAL,
    is_deleted   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS semantic_item_tag (
    item_key TEXT NOT NULL,
    tag_id   TEXT NOT NULL,
    tag_name TEXT NOT NULL DEFAULT '',
    tag_kind TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (item_key, tag_id)
);

-- 受控词表：name 和每个同义词各一行，标签路拿它做「查询里出现了哪个词」
CREATE TABLE IF NOT EXISTS semantic_tag (
    tag_id TEXT NOT NULL,
    text   TEXT NOT NULL,
    tag_name TEXT NOT NULL DEFAULT '',
    kind   TEXT NOT NULL DEFAULT '',
    is_alias INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tag_id, text)
);

CREATE INDEX IF NOT EXISTS idx_semantic_item_scope
    ON semantic_item(media_type, source, is_deleted);
CREATE INDEX IF NOT EXISTS idx_semantic_item_id
    ON semantic_item(item_id);
CREATE INDEX IF NOT EXISTS idx_semantic_item_tag_tag
    ON semantic_item_tag(tag_id);
CREATE INDEX IF NOT EXISTS idx_semantic_tag_text
    ON semantic_tag(text);
"""

FTS_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS semantic_item_fts USING fts5(
    item_key UNINDEXED,
    search_text,
    tokenize='trigram'
);
"""

# 老库（schema v1）升级时补的列
_ITEM_COLUMNS_V2 = (
    ("vibe_text", "TEXT NOT NULL DEFAULT ''"),
    ("catalog_text", "TEXT NOT NULL DEFAULT ''"),
)
_ITEM_TAG_COLUMNS_V2 = (
    ("tag_kind", "TEXT NOT NULL DEFAULT ''"),
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _migrate_v2(conn)
    if _fts_probe(conn) and not _fts_exists(conn):
        try:
            conn.execute(FTS_TABLE_SQL)
        except sqlite3.Error:
            pass
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _migrate_v2(conn: sqlite3.Connection) -> None:
    for table, columns in (
        ("semantic_item", _ITEM_COLUMNS_V2),
        ("semantic_item_tag", _ITEM_TAG_COLUMNS_V2),
    ):
        existing = _table_columns(conn, table)
        if not existing:
            continue
        for name, ddl in columns:
            if name in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            except sqlite3.Error:
                pass


def _fts_exists(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_item_fts'"
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _fts_probe(conn: sqlite3.Connection) -> bool:
    """探测当前 sqlite 是否支持 fts5 + trigram 分词器（Android 上可能缺失）。"""
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _semantic_fts_probe USING fts5(x, tokenize='trigram')")
        conn.execute("DROP TABLE IF EXISTS _semantic_fts_probe")
        return True
    except sqlite3.Error:
        try:
            conn.execute("DROP TABLE IF EXISTS _semantic_fts_probe")
        except sqlite3.Error:
            pass
        return False


def semantic_search_available(conn: sqlite3.Connection) -> bool:
    """FTS 加速表是否可用。不可用时关键词路退化为 LIKE 全表扫描。"""
    return _fts_exists(conn)
