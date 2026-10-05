from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import infrastructure.persistence.catalog_index.builder as catalog_index_builder
import infrastructure.persistence.catalog_index.connection as catalog_index_connection
import infrastructure.persistence.catalog_index.writer as catalog_index_writer
from infrastructure.persistence.catalog_index.builder import rebuild_index


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_tag_change_incrementally_refreshes_only_referencing_index_items(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_index_builder, "get_meta_dir", lambda: str(tmp_path))
    monkeypatch.setattr(catalog_index_connection, "get_meta_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        catalog_index_writer,
        "get_catalog_index_path",
        catalog_index_connection.get_catalog_index_path,
    )
    monkeypatch.setattr(
        catalog_index_writer,
        "catalog_index_connection",
        catalog_index_connection.catalog_index_connection,
    )

    _write_json(
        tmp_path / "tags_database.json",
        {
            "tags": [
                {"id": "tag_a", "name": "Old Action", "content_type": "comic"},
                {"id": "tag_b", "name": "Stable Drama", "content_type": "comic"},
            ]
        },
    )
    _write_json(
        tmp_path / "comics_database.json",
        {
            "comics": [
                {
                    "id": "COMIC_A",
                    "title": "Tagged Comic",
                    "author": "Tester",
                    "tag_ids": ["tag_a"],
                    "list_ids": [],
                    "is_deleted": False,
                },
                {
                    "id": "COMIC_B",
                    "title": "Stable Comic",
                    "author": "Tester",
                    "tag_ids": ["tag_b"],
                    "list_ids": [],
                    "is_deleted": False,
                },
            ],
            "total_comics": 2,
        },
    )
    for name, key in (
        ("recommendations_database.json", "recommendations"),
        ("videos_database.json", "videos"),
        ("video_recommendations_database.json", "video_recommendations"),
    ):
        _write_json(tmp_path / name, {key: []})

    with catalog_index_connection.catalog_index_connection() as conn:
        rebuild_index(conn)

    _write_json(
        tmp_path / "tags_database.json",
        {
            "tags": [
                {"id": "tag_a", "name": "New Action", "content_type": "comic"},
                {"id": "tag_b", "name": "Stable Drama", "content_type": "comic"},
            ]
        },
    )

    result = catalog_index_writer.sync_after_json_write(
        "tags_database.json",
        None,
        {
            "tags": [
                {"id": "tag_a", "name": "New Action", "content_type": "comic"},
                {"id": "tag_b", "name": "Stable Drama", "content_type": "comic"},
            ]
        },
        changed_ids=["tag_a"],
    )

    assert result["synced"] is True
    assert result["mode"] == "tag_changed_ids"
    assert result["changed_tag_count"] == 1
    assert result["refreshed_item_count"] == 1

    with catalog_index_connection.catalog_index_connection() as conn:
        rows = conn.execute(
            """
            SELECT item_id, search_text
            FROM catalog_item
            WHERE item_id IN ('COMIC_A', 'COMIC_B')
            ORDER BY item_id
            """
        ).fetchall()

    search_by_id = {row["item_id"]: row["search_text"] for row in rows}
    assert "new action" in search_by_id["COMIC_A"]
    assert "old action" not in search_by_id["COMIC_A"]
    assert "stable drama" in search_by_id["COMIC_B"]
