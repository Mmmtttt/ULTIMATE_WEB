from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 1


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        CREATE TABLE IF NOT EXISTS catalog_item (
            item_key TEXT PRIMARY KEY,
            media_type TEXT NOT NULL,
            source TEXT NOT NULL,
            source_order INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            title_jp TEXT NOT NULL DEFAULT '',
            creator TEXT NOT NULL DEFAULT '',
            actors_text TEXT NOT NULL DEFAULT '',
            code TEXT NOT NULL DEFAULT '',
            desc TEXT NOT NULL DEFAULT '',
            search_text TEXT NOT NULL DEFAULT '',
            score REAL,
            current_unit INTEGER NOT NULL DEFAULT 1,
            total_units INTEGER NOT NULL DEFAULT 0,
            create_time TEXT NOT NULL DEFAULT '',
            last_access_time TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL DEFAULT '',
            is_deleted INTEGER NOT NULL DEFAULT 0,
            cover_path TEXT NOT NULL DEFAULT '',
            cover_path_local TEXT NOT NULL DEFAULT '',
            custom_order INTEGER,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS catalog_tag (
            item_key TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            PRIMARY KEY (item_key, tag_id)
        );

        CREATE TABLE IF NOT EXISTS catalog_list (
            item_key TEXT NOT NULL,
            list_id TEXT NOT NULL,
            PRIMARY KEY (item_key, list_id)
        );

        CREATE TABLE IF NOT EXISTS catalog_author (
            item_key TEXT NOT NULL,
            name TEXT NOT NULL,
            PRIMARY KEY (item_key, name)
        );

        CREATE TABLE IF NOT EXISTS catalog_index_meta (
            logical_name TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS catalog_index_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_catalog_item_scope_order
            ON catalog_item(media_type, source, is_deleted, source_order);
        CREATE INDEX IF NOT EXISTS idx_catalog_item_score
            ON catalog_item(media_type, source, is_deleted, score);
        CREATE INDEX IF NOT EXISTS idx_catalog_item_create_time
            ON catalog_item(media_type, source, is_deleted, create_time);
        CREATE INDEX IF NOT EXISTS idx_catalog_item_access_time
            ON catalog_item(media_type, source, is_deleted, last_access_time);
        CREATE INDEX IF NOT EXISTS idx_catalog_item_code
            ON catalog_item(media_type, source, is_deleted, code);
        CREATE INDEX IF NOT EXISTS idx_catalog_item_date
            ON catalog_item(media_type, source, is_deleted, date);
        CREATE INDEX IF NOT EXISTS idx_catalog_tag_tag_id
            ON catalog_tag(tag_id, item_key);
        CREATE INDEX IF NOT EXISTS idx_catalog_list_list_id
            ON catalog_list(list_id, item_key);
        CREATE INDEX IF NOT EXISTS idx_catalog_author_name
            ON catalog_author(name, item_key);
        """
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO catalog_index_state(key, value)
        VALUES ('schema_version', ?)
        """,
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
