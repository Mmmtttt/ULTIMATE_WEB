from __future__ import annotations

import os
import sqlite3
import struct
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .builder import is_stale, source_stats
from .embedder import EmbeddingProvider, get_embedding_provider
from .schema import semantic_search_available
from .text import normalize

RRF_K = 60
ROUTE_LIMIT = 60

# 向量路的收口：bge-small-zh 的相似度分布很挤（0.3~0.5），
# 只按名次返回会把整库都塞进结果里，必须同时用绝对下限 + 相对首名的差距卡一遍。
VECTOR_TOP_K = max(1, int(os.environ.get("ULTIMATE_SEMANTIC_TOPK", "8") or 8))
VECTOR_MIN_SIMILARITY = float(os.environ.get("ULTIMATE_SEMANTIC_MIN_SIM", "0.30") or 0.30)
VECTOR_RELATIVE_MARGIN = float(os.environ.get("ULTIMATE_SEMANTIC_MARGIN", "0.05") or 0.05)


def _scope_clause(source: str, media_type: str) -> Tuple[str, List[Any]]:
    return "i.media_type = ? AND i.source = ? AND i.is_deleted = 0", [media_type, source]


# ---------- ① 标签路 ----------
def route_by_tags(conn: sqlite3.Connection, query: str, *, source: str, media_type: str) -> Tuple[List[Tuple[str, float]], List[str]]:
    """查询里出现的标签名或同义词 → 对应的书，按命中标签数排序。"""
    normalized_query = normalize(query)
    if not normalized_query:
        return [], []

    hit_tag_ids: List[str] = []
    hit_labels: List[str] = []
    for row in conn.execute("SELECT tag_id, text, tag_name FROM semantic_tag"):
        needle = normalize(row["text"])
        if not needle or needle not in normalized_query:
            continue
        tag_id = str(row["tag_id"])
        if tag_id in hit_tag_ids:
            continue
        hit_tag_ids.append(tag_id)
        label = str(row["tag_name"] or row["text"])
        if label and label not in hit_labels:
            hit_labels.append(label)
    if not hit_tag_ids:
        return [], []

    placeholders = ",".join("?" for _ in hit_tag_ids)
    where, params = _scope_clause(source, media_type)
    rows = conn.execute(
        f"""
        SELECT it.item_key AS item_key, COUNT(DISTINCT it.tag_id) AS hits
        FROM semantic_item_tag it
        JOIN semantic_item i ON i.item_key = it.item_key
        WHERE it.tag_id IN ({placeholders}) AND {where}
        GROUP BY it.item_key
        ORDER BY hits DESC
        LIMIT ?
        """,
        [*hit_tag_ids, *params, ROUTE_LIMIT],
    ).fetchall()
    return [(row["item_key"], float(row["hits"])) for row in rows], hit_labels


# ---------- ② 关键词路 ----------
def _split_tokens(query: str) -> List[str]:
    return [token for token in normalize(query).split() if token]


def _cjk_bigrams(text: str, limit: int = 16) -> List[str]:
    """中文没有空格，用二元组（bigram）近似分词，让「双胞胎女仆一起伺候」也能命中词条。"""
    cleaned = "".join(char for char in normalize(text) if not char.isspace())
    grams: List[str] = []
    seen = set()
    for index in range(len(cleaned) - 1):
        gram = cleaned[index:index + 2]
        if not gram.strip() or gram in seen:
            continue
        # 纯标点/纯符号的二元组没有检索价值
        if not any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in gram):
            continue
        seen.add(gram)
        grams.append(gram)
        if len(grams) >= limit:
            break
    return grams


def _match_items(
    conn: sqlite3.Connection,
    needle: str,
    *,
    source: str,
    media_type: str,
    search_available: bool,
) -> List[str]:
    where, params = _scope_clause(source, media_type)
    pattern = f"%{needle}%"
    if search_available:
        rows = conn.execute(
            f"""
            SELECT i.item_key AS item_key
            FROM semantic_item_fts f
            JOIN semantic_item i ON i.item_key = f.item_key
            WHERE f.search_text LIKE ? AND {where}
            LIMIT ?
            """,
            [pattern, *params, ROUTE_LIMIT],
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT i.item_key AS item_key FROM semantic_item i WHERE i.search_text LIKE ? AND {where} LIMIT ?",
            [pattern, *params, ROUTE_LIMIT],
        ).fetchall()
    return [row["item_key"] for row in rows]


def route_by_keyword(
    conn: sqlite3.Connection,
    query: str,
    *,
    source: str,
    media_type: str,
    search_available: bool,
) -> List[Tuple[str, float]]:
    tokens = _split_tokens(query)
    if not tokens:
        return []

    scores: Dict[str, float] = {}
    # ① 先按空白切词做字面匹配（英文/空格分词的中文关键词）
    for token in tokens:
        for item_key in _match_items(
            conn, token, source=source, media_type=media_type, search_available=search_available
        ):
            scores[item_key] = scores.get(item_key, 0.0) + 2.0

    # ② 中文长句：整串匹配不到时退到二元组投票
    if not scores:
        for gram in _cjk_bigrams(str(query or "")):
            for item_key in _match_items(
                conn, gram, source=source, media_type=media_type, search_available=search_available
            ):
                scores[item_key] = scores.get(item_key, 0.0) + 1.0

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:ROUTE_LIMIT]


# ---------- ③ 向量路 ----------
def _unpack(blob: bytes) -> Sequence[float]:
    count = len(blob) // 4
    return struct.unpack(f"<{count}f", blob)


def _cosine_scores_python(
    query_vector: Sequence[float],
    rows: Sequence[Tuple[str, bytes, float]],
) -> List[Tuple[str, float]]:
    query_norm = sum(value * value for value in query_vector) ** 0.5 or 1.0
    scored: List[Tuple[str, float]] = []
    for item_key, blob, norm in rows:
        vector = _unpack(blob)
        if len(vector) != len(query_vector):
            continue
        dot = 0.0
        for left, right in zip(query_vector, vector):
            dot += left * right
        scored.append((item_key, dot / (query_norm * (norm or 1.0))))
    return scored


def _cosine_scores_numpy(query_vector, rows):
    import numpy as np

    query = np.asarray(query_vector, dtype=np.float32)
    query_norm = float(np.linalg.norm(query)) or 1.0
    keys: List[str] = []
    matrix = []
    norms: List[float] = []
    for item_key, blob, norm in rows:
        vector = np.frombuffer(blob, dtype=np.float32)
        if vector.shape[0] != query.shape[0]:
            continue
        keys.append(item_key)
        matrix.append(vector)
        norms.append(float(norm) or 1.0)
    if not keys:
        return []
    scores = np.asarray(matrix, dtype=np.float32) @ query
    scores = scores / (np.asarray(norms, dtype=np.float32) * query_norm)
    order = np.argsort(-scores)[:ROUTE_LIMIT]
    return [(keys[int(index)], float(scores[int(index)])) for index in order]


def route_by_vector(
    conn: sqlite3.Connection,
    query: str,
    *,
    source: str,
    media_type: str,
    embedder: Optional[EmbeddingProvider],
    ready: bool = True,
) -> Tuple[List[Tuple[str, float]], str, Dict[str, float]]:
    if not ready:
        return [], "index_without_vectors", {}
    if embedder is None:
        return [], "no_embedder", {}
    if not embedder.available:
        return [], embedder.reason or "embedder_unavailable", {}

    query_vector = embedder.embed_query(query)
    if not query_vector:
        return [], "query_embed_failed", {}

    where, params = _scope_clause(source, media_type)
    rows = conn.execute(
        f"SELECT i.item_key AS item_key, i.embed AS embed, i.embed_norm AS embed_norm "
        f"FROM semantic_item i WHERE i.embed IS NOT NULL AND {where}",
        params,
    ).fetchall()
    if not rows:
        return [], "no_vectors", {}

    payload = [(row["item_key"], row["embed"], float(row["embed_norm"] or 1.0)) for row in rows]
    try:
        scored = _cosine_scores_numpy(query_vector, payload)
    except Exception:
        scored = _cosine_scores_python(query_vector, payload)
    scored.sort(key=lambda item: -item[1])
    if not scored:
        return [], "no_scores", {}

    best = float(scored[0][1])
    cutoff = max(VECTOR_MIN_SIMILARITY, best - VECTOR_RELATIVE_MARGIN)
    kept = [item for item in scored if float(item[1]) >= cutoff][:VECTOR_TOP_K]
    stats = {
        "best": round(best, 4),
        "cutoff": round(cutoff, 4),
        "scored": len(scored),
        "kept": len(kept),
    }
    return kept, ("ok" if kept else f"all_below_threshold({best:.3f})"), stats


# ---------- 融合（RRF） ----------
def fuse(rankings: Sequence[Sequence[Tuple[str, float]]], k: int = RRF_K) -> List[Tuple[str, float]]:
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for position, (item_key, _score) in enumerate(ranking):
            scores[item_key] = scores.get(item_key, 0.0) + 1.0 / (k + position + 1)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    source: str = "local",
    media_type: str = "comic",
    limit: int = 50,
    embedder: Optional[EmbeddingProvider] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    text = str(query or "").strip()
    if not text:
        return {"results": [], "debug": {"reason": "empty_query"}}

    embedder = embedder or get_embedding_provider()
    search_available = semantic_search_available(conn)
    meta = read_meta(conn)
    vector_ready = meta.get("vector_enabled") == "1"

    tag_rank, hit_tags = route_by_tags(conn, text, source=source, media_type=media_type)
    keyword_rank = route_by_keyword(
        conn, text, source=source, media_type=media_type, search_available=search_available
    )
    vector_rank, vector_state, vector_stats = route_by_vector(
        conn, text, source=source, media_type=media_type, embedder=embedder, ready=vector_ready
    )

    fused = fuse([tag_rank, keyword_rank, vector_rank])[: max(1, int(limit))]

    results: List[Dict[str, Any]] = []
    if fused:
        keys = [item_key for item_key, _score in fused]
        placeholders = ",".join("?" for _ in keys)
        rows = {
            row["item_key"]: row
            for row in conn.execute(
                f"SELECT item_key, item_id, title, tag_text FROM semantic_item WHERE item_key IN ({placeholders})",
                keys,
            )
        }
        tag_positions = {item_key: pos for pos, (item_key, _) in enumerate(tag_rank)}
        keyword_positions = {item_key: pos for pos, (item_key, _) in enumerate(keyword_rank)}
        vector_positions = {item_key: pos for pos, (item_key, _) in enumerate(vector_rank)}
        for item_key, score in fused:
            row = rows.get(item_key)
            if row is None:
                continue
            results.append({
                "item_key": item_key,
                "item_id": row["item_id"],
                "title": row["title"],
                "tag_text": row["tag_text"],
                "score": round(float(score), 6),
                "routes": {
                    "tag": tag_positions.get(item_key),
                    "keyword": keyword_positions.get(item_key),
                    "vector": vector_positions.get(item_key),
                },
            })

    return {
        "results": results,
        "debug": {
            "hit_tags": hit_tags,
            "search_index": "fts5_trigram_like" if search_available else "like_scan",
            "vector_state": vector_state,
            "vector_stats": vector_stats,
            "route_sizes": {
                "tag": len(tag_rank),
                "keyword": len(keyword_rank),
                "vector": len(vector_rank),
            },
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }


def read_meta(conn: sqlite3.Connection) -> Dict[str, str]:
    try:
        return {row["k"]: row["v"] for row in conn.execute("SELECT k, v FROM semantic_meta")}
    except sqlite3.Error:
        return {}


def _embedder_installed(embedder: Optional[EmbeddingProvider]) -> bool:
    """判断向量依赖是否就绪；不触发模型加载（import onnxruntime 要好几秒）。"""
    if embedder is None:
        return False
    if getattr(embedder, "loaded", False):
        return True
    probe = getattr(embedder, "installed", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:
            return False
    # 兼容自定义/测试替身：允许直接给出 available 布尔
    available = getattr(embedder, "available", False)
    return available if isinstance(available, bool) else False


def index_status(conn: sqlite3.Connection, embedder: Optional[EmbeddingProvider] = None) -> Dict[str, Any]:
    meta = read_meta(conn)
    counts: Dict[str, int] = {}
    for label, sql in (
        ("items", "SELECT COUNT(*) AS c FROM semantic_item WHERE is_deleted = 0"),
        ("vectors", "SELECT COUNT(*) AS c FROM semantic_item WHERE embed IS NOT NULL"),
        ("tags", "SELECT COUNT(*) AS c FROM semantic_item_tag"),
        ("vibe_covered", "SELECT COUNT(*) AS c FROM semantic_item WHERE is_deleted = 0 AND vibe_text <> ''"),
        ("catalog_covered", "SELECT COUNT(*) AS c FROM semantic_item WHERE is_deleted = 0 AND catalog_text <> ''"),
        ("vocabulary", "SELECT COUNT(*) AS c FROM semantic_tag"),
    ):
        try:
            counts[label] = int(conn.execute(sql).fetchone()["c"])
        except sqlite3.Error:
            counts[label] = 0

    embedder = embedder or get_embedding_provider()
    installed = _embedder_installed(embedder)
    embedder_reason = ""
    if not installed:
        embedder_reason = getattr(embedder, "failed_reason", "") or "未安装 fastembed"

    return {
        "indexed": bool(meta.get("built_at")),
        "built_at": meta.get("built_at", ""),
        "doc_count": counts.get("items", 0),
        "vector_count": counts.get("vectors", 0),
        "tag_links": counts.get("tags", 0),
        "vibe_covered": counts.get("vibe_covered", 0),
        "catalog_covered": counts.get("catalog_covered", 0),
        "tag_vocabulary": counts.get("vocabulary", 0),
        "embed_model": meta.get("embed_model", ""),
        "embed_dim": int(meta.get("embed_dim") or 0),
        "vector_enabled": meta.get("vector_enabled") == "1",
        "search_index": "fts5_trigram_like" if semantic_search_available(conn) else "like_scan",
        "stale": is_stale(conn),
        "embedder_available": installed,
        "embedder_reason": embedder_reason,
        "source_stats": source_stats(),
    }
