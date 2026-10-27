from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.storage_layout import get_meta_dir

from .embedder import EmbeddingProvider
from .schema import SCHEMA_VERSION, semantic_search_available
from .text import normalize

# 与 catalog index 使用同一批文档：语义索引只是「另一种读法」，不另存一份业务数据
SOURCE_DOCUMENTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("comic_local", "comics_database.json", "comics", "local"),
    ("comic_preview", "recommendations_database.json", "recommendations", "preview"),
)

TAGS_DOCUMENT = "tags_database.json"
VIBE_TEXT_LIMIT = 600
CATALOG_TEXT_LIMIT = 1200
TAG_NAMES_IN_VECTOR = 40
DOC_TEXT_LIMIT = 1600
SEARCH_TEXT_LIMIT = 4000


def _document_path(file_name: str) -> str:
    return os.path.join(get_meta_dir(), file_name)


def load_document(file_name: str) -> Dict[str, Any]:
    path = _document_path(file_name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fp:
            payload = json.load(fp)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def source_stats() -> Dict[str, Dict[str, Any]]:
    """源文档的指纹（size + mtime_ns），用于判断语义索引是否过期。"""
    stats: Dict[str, Dict[str, Any]] = {}
    for logical_name, file_name, _data_key, _source in SOURCE_DOCUMENTS:
        path = _document_path(file_name)
        try:
            stat = os.stat(path)
            stats[logical_name] = {
                "path": path,
                "size_bytes": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except OSError:
            stats[logical_name] = {"path": path, "size_bytes": 0, "mtime_ns": 0}
    return stats


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in values:
        value = _text(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def load_tag_vocabulary() -> Dict[str, Dict[str, Any]]:
    """读出受控词表：id -> {name, kind, aliases}。"""
    payload = load_document(TAGS_DOCUMENT)
    vocabulary: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("tags") or []:
        if not isinstance(item, dict):
            continue
        tag_id = _text(item.get("id"))
        if not tag_id:
            continue
        vocabulary[tag_id] = {
            "name": _text(item.get("name")) or tag_id,
            "kind": _text(item.get("kind")) or "题材",
            "aliases": _unique(item.get("aliases") or []),
        }
    return vocabulary


def build_vector_text(title: str, title_jp: str, creator: str, vibe: str, tag_names: List[str]) -> str:
    """喂给向量的正文：只放「气质」相关的内容，篇名长名单不进这里。"""
    parts = [title, title_jp, creator, vibe[:VIBE_TEXT_LIMIT], "、".join(tag_names[:TAG_NAMES_IN_VECTOR])]
    return " ".join(part for part in parts if part).strip()[:DOC_TEXT_LIMIT]


def build_search_text(
    item_id: str,
    title: str,
    title_jp: str,
    creator: str,
    catalog: str,
    desc: str,
    tag_ids: List[str],
    tag_names: List[str],
) -> str:
    """喂给关键词索引的正文：篇名速览、简介、标签 id/名称全进，供字面命中。"""
    parts: List[str] = [item_id, title, title_jp, creator, catalog[:CATALOG_TEXT_LIMIT], desc, *tag_ids, *tag_names]
    text = "\n".join(normalize(part) for part in parts if part)
    return text[:SEARCH_TEXT_LIMIT]


def _extract_row(
    media_type: str,
    source: str,
    raw: Dict[str, Any],
    vocabulary: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    item_id = _text(raw.get("id"))
    if not item_id:
        return None
    title = _text(raw.get("title"))
    title_jp = _text(raw.get("title_jp"))
    creator = _text(raw.get("author") or raw.get("creator"))
    desc = _text(raw.get("desc"))
    # vibe 是「整本气质梗概」；老数据没有这个字段时用 desc 顶上
    vibe = _text(raw.get("vibe")) or desc
    catalog = _text(raw.get("catalog"))
    tag_ids = _unique(raw.get("tag_ids") or [])
    tag_names = [vocabulary.get(tag_id, {}).get("name") or tag_id for tag_id in tag_ids]
    tag_kinds = [vocabulary.get(tag_id, {}).get("kind") or "" for tag_id in tag_ids]

    return {
        "item_key": f"{media_type}:{source}:{item_id}",
        "media_type": media_type,
        "source": source,
        "item_id": item_id,
        "title": title,
        "title_jp": title_jp,
        "creator": creator,
        "desc_text": desc,
        "vibe_text": vibe,
        "catalog_text": catalog,
        "tag_text": "、".join(tag_names),
        "search_text": build_search_text(item_id, title, title_jp, creator, catalog, desc, tag_ids, tag_names),
        "doc_text": build_vector_text(title, title_jp, creator, vibe, tag_names),
        "is_deleted": 1 if bool(raw.get("is_deleted", False)) else 0,
        "tag_ids": tag_ids,
        "tag_names": tag_names,
        "tag_kinds": tag_kinds,
    }


def build_document_text(title: str, title_jp: str, creator: str, desc: str, tag_names: List[str]) -> str:
    """兼容旧调用：等价于 build_vector_text 的 desc 版本。"""
    return build_vector_text(title, title_jp, creator, desc, tag_names)


def rebuild_index(
    conn: sqlite3.Connection,
    embedder: Optional[EmbeddingProvider] = None,
    *,
    build_embeddings: bool = True,
) -> Dict[str, Any]:
    """全量重建语义索引，返回统计信息。"""
    vocabulary = load_tag_vocabulary()
    embedder = embedder or EmbeddingProvider()
    use_vector = bool(build_embeddings and embedder.available)
    search_available = semantic_search_available(conn)

    rows: List[Dict[str, Any]] = []
    for _logical_name, file_name, data_key, source in SOURCE_DOCUMENTS:
        payload = load_document(file_name)
        for raw in payload.get(data_key) or []:
            if not isinstance(raw, dict):
                continue
            row = _extract_row("comic", source, raw, vocabulary)
            if row is not None:
                rows.append(row)

    indexed_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    embedded_count = 0
    dim = 0

    with conn:
        conn.execute("DELETE FROM semantic_item")
        conn.execute("DELETE FROM semantic_item_tag")
        conn.execute("DELETE FROM semantic_tag")
        if search_available:
            conn.execute("DELETE FROM semantic_item_fts")

        # 受控词表：name 与每个同义词各占一行，标签路靠它把「姊妹」映射回「双胞胎」
        for tag_id, entry in vocabulary.items():
            texts = [(entry["name"], 0)] + [(alias, 1) for alias in entry["aliases"]]
            for text, is_alias in texts:
                if not text:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO semantic_tag(tag_id, text, tag_name, kind, is_alias) VALUES (?, ?, ?, ?, ?)",
                    (tag_id, text, entry["name"], entry["kind"], is_alias),
                )

        if use_vector and rows:
            vectors = embedder.embed_documents([row["doc_text"] for row in rows])
            if len(vectors) == len(rows):
                for row, (blob, norm) in zip(rows, vectors):
                    row["embed"] = blob
                    row["embed_norm"] = norm
                    embedded_count += 1
                dim = len(rows[0]["embed"]) // 4 if embedded_count else 0
            else:
                use_vector = False

        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_item (
                    item_key, media_type, source, item_id, title, title_jp, creator,
                    desc_text, vibe_text, catalog_text, tag_text, search_text, doc_text,
                    embed, embed_norm, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["item_key"], row["media_type"], row["source"], row["item_id"],
                    row["title"], row["title_jp"], row["creator"],
                    row["desc_text"], row["vibe_text"], row["catalog_text"], row["tag_text"],
                    row["search_text"], row["doc_text"],
                    row.get("embed"), row.get("embed_norm"), row["is_deleted"],
                ),
            )
            if search_available:
                conn.execute(
                    "INSERT INTO semantic_item_fts(item_key, search_text) VALUES (?, ?)",
                    (row["item_key"], row["search_text"]),
                )
            conn.executemany(
                "INSERT OR REPLACE INTO semantic_item_tag(item_key, tag_id, tag_name, tag_kind) VALUES (?, ?, ?, ?)",
                [
                    (row["item_key"], tag_id, tag_name, tag_kind)
                    for tag_id, tag_name, tag_kind in zip(row["tag_ids"], row["tag_names"], row["tag_kinds"])
                ],
            )

        meta_values = {
            "schema_version": SCHEMA_VERSION,
            "embed_model": embedder.model_name if use_vector else "",
            "embed_dim": str(dim),
            "vector_enabled": "1" if use_vector else "0",
            "doc_count": str(len(rows)),
            "embedded_count": str(embedded_count),
            "built_at": indexed_at,
        }
        for key, value in meta_values.items():
            conn.execute("INSERT OR REPLACE INTO semantic_meta(k, v) VALUES (?, ?)", (key, value))

        for logical_name, stat in source_stats().items():
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_source(logical_name, path, size_bytes, mtime_ns, indexed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (logical_name, stat["path"], stat["size_bytes"], stat["mtime_ns"], indexed_at),
            )

    return {
        "doc_count": len(rows),
        "embedded_count": embedded_count,
        "vector_enabled": use_vector,
        "embed_dim": dim,
        "embed_model": embedder.model_name if use_vector else "",
        "embed_reason": "" if use_vector else (getattr(embedder, "failed_reason", "") or "未启用向量检索"),
        "search_index": "fts5_trigram" if search_available else "like_scan",
        "tag_terms": sum(1 + len(entry["aliases"]) for entry in vocabulary.values()),
        "built_at": indexed_at,
    }


def is_stale(conn: sqlite3.Connection) -> bool:
    """源 JSON 比索引新（或索引缺失/结构版本不符）即视为过期。"""
    try:
        built = conn.execute("SELECT v FROM semantic_meta WHERE k='built_at'").fetchone()
        if built is None:
            return True
        version = conn.execute("SELECT v FROM semantic_meta WHERE k='schema_version'").fetchone()
        if version is None or str(version["v"]) != SCHEMA_VERSION:
            return True
        rows = {
            row["logical_name"]: (int(row["size_bytes"]), int(row["mtime_ns"]))
            for row in conn.execute("SELECT logical_name, size_bytes, mtime_ns FROM semantic_source")
        }
    except sqlite3.Error:
        return True

    stats = source_stats()
    if set(stats.keys()) != set(rows.keys()):
        return True
    for logical_name, stat in stats.items():
        current = (stat["size_bytes"], stat["mtime_ns"])
        if rows.get(logical_name) != current:
            return True
    return False
