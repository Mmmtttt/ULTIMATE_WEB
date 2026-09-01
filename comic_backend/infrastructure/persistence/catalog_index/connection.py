from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from core.storage_layout import get_meta_dir
from .schema import ensure_schema


INDEX_FILE_NAME = "catalog_index.db"


def get_catalog_index_path() -> str:
    meta_dir = get_meta_dir()
    os.makedirs(meta_dir, exist_ok=True)
    return os.path.join(meta_dir, INDEX_FILE_NAME)


def open_catalog_index() -> sqlite3.Connection:
    conn = sqlite3.connect(get_catalog_index_path())
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


@contextmanager
def catalog_index_connection() -> Iterator[sqlite3.Connection]:
    conn = open_catalog_index()
    try:
        yield conn
    finally:
        conn.close()
