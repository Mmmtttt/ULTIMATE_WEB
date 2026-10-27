from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from core.storage_layout import get_meta_dir

from .schema import ensure_schema

INDEX_FILE_NAME = "semantic_index.db"


def get_semantic_index_path(db_path: Optional[str] = None, mode: Optional[str] = None) -> str:
    if db_path:
        target = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        return target
    meta_dir = get_meta_dir(mode)
    os.makedirs(meta_dir, exist_ok=True)
    return os.path.join(meta_dir, INDEX_FILE_NAME)


def open_semantic_index(db_path: Optional[str] = None, mode: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(get_semantic_index_path(db_path, mode), timeout=10.0)
    conn.row_factory = sqlite3.Row
    # 后台重建与前台检索可能并发：让读请求等待写事务，而不是直接报 database is locked
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
    except sqlite3.Error:
        pass
    ensure_schema(conn)
    return conn


@contextmanager
def semantic_index_connection(
    db_path: Optional[str] = None,
    mode: Optional[str] = None,
) -> Iterator[sqlite3.Connection]:
    conn = open_semantic_index(db_path, mode)
    try:
        yield conn
    finally:
        conn.close()
