from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DirectionalSyncService = importlib.import_module("application.sync_directional_service").DirectionalSyncService


def test_delta_from_known_filters_cross_content_type_tag_ids(monkeypatch):
    service = DirectionalSyncService()
    datasets_by_root = {
        "comics": [
            {"id": "comic-1", "title": "Comic 1", "tag_ids": ["tag_comic", "tag_video"], "list_ids": []},
        ],
        "recommendations": [],
        "videos": [],
        "video_recommendations": [],
        "tags": [
            {"id": "tag_comic", "name": "漫画标签", "content_type": "comic"},
            {"id": "tag_video", "name": "视频标签", "content_type": "video"},
        ],
        "lists": [],
        "actors": [],
        "authors": [],
        "user_config": {},
    }

    def fake_read_dataset(cfg):
        return datasets_by_root.get(cfg.get("root_key"), [])

    monkeypatch.setattr(service, "_read_dataset", fake_read_dataset)

    result = service.delta_from_known({"datasets": {}})
    comic_rows = result.get("datasets", {}).get("comics", [])

    assert len(comic_rows) == 1
    assert comic_rows[0]["tag_ids"] == ["tag_comic"]
