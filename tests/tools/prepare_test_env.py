#!/usr/bin/env python3
"""Build isolated test runtime data under tests/.runtime/<profile>."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

BOOTSTRAP_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_REPO_ROOT))

from tests.shared.test_constants import (
    FIFTH_COMIC_ID,
    FIFTH_COMIC_ORIGINAL_ID,
    FIFTH_COMIC_TITLE,
    FOURTH_COMIC_ID,
    FOURTH_COMIC_ORIGINAL_ID,
    FOURTH_COMIC_TITLE,
    PRIMARY_COMIC_ID,
    PRIMARY_COMIC_ORIGINAL_ID,
    PRIMARY_COMIC_TITLE,
    PRIMARY_VIDEO_ID,
    REPO_ROOT,
    RUNTIME_ROOT,
    SECONDARY_COMIC_ID,
    SECONDARY_COMIC_ORIGINAL_ID,
    SECONDARY_COMIC_TITLE,
    SECONDARY_VIDEO_ID,
    SECONDARY_VIDEO_TITLE,
    THIRD_COMIC_ID,
    THIRD_COMIC_ORIGINAL_ID,
    THIRD_COMIC_TITLE,
    THIRD_VIDEO_ID,
    THIRD_VIDEO_TITLE,
)


# 1x1 transparent PNG
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6QHdwAAAAASUVORK5CYII="
)

# 1x1 white JPEG
JPG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxISEhUTEhIVFhUVFRUVFRUVFRUVFRUVFRUXFhUV"
    "FRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMtNygtLisBCgoKDg0OFQ8PFS0dFR0tLS0tLS0tLS0tLS0t"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAXAAEB"
    "AQEAAAAAAAAAAAAAAAAAAQID/8QAFhEBAQEAAAAAAAAAAAAAAAAAAAER/9oADAMBAAIQAxAAAAG8gP/"
    "EABgQAQEAAwAAAAAAAAAAAAAAAAERAAIx/9oACAEBAAEFAjJkWf/EABYRAQEBAAAAAAAAAAAAAAAAAAAB"
    "Ef/aAAgBAwEBPwGn/8QAFhEBAQEAAAAAAAAAAAAAAAAAABEh/9oACAECAQE/Acf/xAAaEAADAQEBAQAAAA"
    "AAAAAAAAABAhEAITFB/9oACAEBAAY/Aq4mV6P/xAAbEAACAgMBAAAAAAAAAAAAAAABEQAhMUFhcf/aAAgB"
    "AQABPyFq2hQ6dYF2jP/Z"
)


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def _write_jpg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(JPG_1X1)


def _seed_meta_data(meta_dir: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    comics_payload = {
        "collection_name": "Test Comics",
        "user": "test-user",
        "total_comics": 5,
        "last_updated": today,
        "comics": [
            {
                "id": PRIMARY_COMIC_ID,
                "title": PRIMARY_COMIC_TITLE,
                "title_jp": "",
                "author": "Tester A",
                "desc": "Seeded comic for end-to-end validation.",
                "cover_path": f"/static/cover/JM/{PRIMARY_COMIC_ORIGINAL_ID}.png",
                "total_page": 3,
                "current_page": 1,
                "score": 8.5,
                "tag_ids": ["tag_action"],
                "list_ids": ["list_favorites_comic"],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": SECONDARY_COMIC_ID,
                "title": SECONDARY_COMIC_TITLE,
                "title_jp": "",
                "author": "Tester B",
                "desc": "Secondary seeded comic.",
                "cover_path": f"/static/cover/JM/{SECONDARY_COMIC_ORIGINAL_ID}.png",
                "total_page": 2,
                "current_page": 1,
                "score": 7,
                "tag_ids": ["tag_story"],
                "list_ids": [],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": THIRD_COMIC_ID,
                "title": THIRD_COMIC_TITLE,
                "title_jp": "",
                "author": "Tester C",
                "desc": "High score action comic.",
                "cover_path": f"/static/cover/JM/{THIRD_COMIC_ORIGINAL_ID}.png",
                "total_page": 5,
                "current_page": 5,
                "score": 9.8,
                "tag_ids": ["tag_action", "tag_drama"],
                "list_ids": ["list_curated_comic"],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": FOURTH_COMIC_ID,
                "title": FOURTH_COMIC_TITLE,
                "title_jp": "",
                "author": "Tester D",
                "desc": "Drama only comic for include-tag filter.",
                "cover_path": f"/static/cover/JM/{FOURTH_COMIC_ORIGINAL_ID}.png",
                "total_page": 4,
                "current_page": 1,
                "score": 6.2,
                "tag_ids": ["tag_drama"],
                "list_ids": ["list_curated_comic"],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": FIFTH_COMIC_ID,
                "title": FIFTH_COMIC_TITLE,
                "title_jp": "",
                "author": "Tester B",
                "desc": "Low score action comic for score-range filter.",
                "cover_path": f"/static/cover/JM/{FIFTH_COMIC_ORIGINAL_ID}.png",
                "total_page": 3,
                "current_page": 1,
                "score": 4.1,
                "tag_ids": ["tag_action", "tag_story"],
                "list_ids": [],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
        ],
        "user_config": {
            "default_page_mode": "left_right",
            "default_background": "white",
        },
    }

    recommendations_payload = {
        "collection_name": "Test Comic Recommendations",
        "user": "test-user",
        "total_recommendations": 0,
        "last_updated": today,
        "recommendations": [],
    }

    videos_payload = {
        "collection_name": "Test Videos",
        "user": "test-user",
        "total_videos": 3,
        "last_updated": today,
        "videos": [
            {
                "id": PRIMARY_VIDEO_ID,
                "code": "TEST-900001",
                "title": "Seed Video",
                "creator": "Video Creator",
                "actors": ["Actor A"],
                "cover_path": "/static/cover/JAVDB/900001.png",
                "thumbnail_images": [],
                "video_url": "",
                "score": 8,
                "tag_ids": ["tag_video"],
                "list_ids": [],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": SECONDARY_VIDEO_ID,
                "code": "TEST-900002",
                "title": SECONDARY_VIDEO_TITLE,
                "creator": "Video Creator B",
                "actors": ["Actor B"],
                "cover_path": "/static/cover/JAVDB/900002.png",
                "thumbnail_images": [],
                "video_url": "",
                "score": 9.3,
                "tag_ids": ["tag_video", "tag_video_action"],
                "list_ids": ["list_curated_video"],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
            {
                "id": THIRD_VIDEO_ID,
                "code": "TEST-900003",
                "title": THIRD_VIDEO_TITLE,
                "creator": "Video Creator C",
                "actors": ["Actor C"],
                "cover_path": "/static/cover/JAVDB/900003.png",
                "thumbnail_images": [],
                "video_url": "",
                "score": 5.6,
                "tag_ids": ["tag_video_story"],
                "list_ids": [],
                "create_time": now,
                "last_read_time": now,
                "is_deleted": False,
            },
        ],
    }

    video_recommendations_payload = {
        "collection_name": "Test Video Recommendations",
        "user": "test-user",
        "total_video_recommendations": 0,
        "last_updated": today,
        "video_recommendations": [],
    }

    tags_payload = {
        "collection_name": "Test Tags",
        "user": "test-user",
        "last_updated": today,
        "tags": [
            {"id": "tag_action", "name": "Action", "content_type": "comic", "create_time": now},
            {"id": "tag_story", "name": "Story", "content_type": "comic", "create_time": now},
            {"id": "tag_drama", "name": "Drama", "content_type": "comic", "create_time": now},
            {"id": "tag_video", "name": "VideoTag", "content_type": "video", "create_time": now},
            {"id": "tag_video_action", "name": "VideoAction", "content_type": "video", "create_time": now},
            {"id": "tag_video_story", "name": "VideoStory", "content_type": "video", "create_time": now},
        ],
    }

    lists_payload = {
        "collection_name": "Test Lists",
        "user": "test-user",
        "last_updated": today,
        "lists": [
            {
                "id": "list_favorites_comic",
                "name": "Comic Favorites",
                "desc": "Default comic favorites",
                "content_type": "comic",
                "is_default": True,
                "create_time": now,
            },
            {
                "id": "list_favorites_video",
                "name": "Video Favorites",
                "desc": "Default video favorites",
                "content_type": "video",
                "is_default": True,
                "create_time": now,
            },
            {
                "id": "list_curated_comic",
                "name": "Curated Comic List",
                "desc": "Seeded custom comic list for filter assertions",
                "content_type": "comic",
                "is_default": False,
                "create_time": now,
            },
            {
                "id": "list_curated_video",
                "name": "Curated Video List",
                "desc": "Seeded custom video list for filter assertions",
                "content_type": "video",
                "is_default": False,
                "create_time": now,
            },
        ],
    }

    user_config_payload = {
        "user_config": {
            "default_page_mode": "left_right",
            "default_background": "white",
            "auto_hide_toolbar": True,
            "show_page_number": True,
            "cache_config": {
                "recommendation_cache_max_size_mb": 5120,
                "cache_ttl_seconds": 3600,
            },
        },
        "last_updated": today,
    }

    _write_json(meta_dir / "comics_database.json", comics_payload)
    _write_json(meta_dir / "recommendations_database.json", recommendations_payload)
    _write_json(meta_dir / "videos_database.json", videos_payload)
    _write_json(meta_dir / "video_recommendations_database.json", video_recommendations_payload)
    _write_json(meta_dir / "tags_database.json", tags_payload)
    _write_json(meta_dir / "lists_database.json", lists_payload)
    _write_json(meta_dir / "user_config.json", user_config_payload)
    _write_json(meta_dir / "authors_database.json", {"authors": [], "last_updated": today})
    _write_json(meta_dir / "actors_database.json", {"actors": [], "last_updated": today})
    _write_json(meta_dir / "import_tasks.json", {"tasks": [], "last_updated": today})
    _write_json(meta_dir / "recommendation_cache_index.json", {"entries": [], "last_updated": today})
    _write_json(meta_dir / "sync_pairing.json", {"peers": [], "last_updated": today})
    _write_json(meta_dir / "sync_sessions.json", {"sessions": [], "last_updated": today})


def _seed_media(data_dir: Path) -> None:
    for original_id, page_count in (
        (PRIMARY_COMIC_ORIGINAL_ID, 3),
        (SECONDARY_COMIC_ORIGINAL_ID, 2),
        (THIRD_COMIC_ORIGINAL_ID, 5),
        (FOURTH_COMIC_ORIGINAL_ID, 4),
        (FIFTH_COMIC_ORIGINAL_ID, 3),
    ):
        comic_dir = data_dir / "comic" / "JM" / original_id
        for page in range(1, page_count + 1):
            _write_png(comic_dir / f"{page:03d}.png")
        _write_png(data_dir / "static" / "cover" / "JM" / f"{original_id}.png")
        _write_jpg(data_dir / "static" / "cover" / "JM" / f"{original_id}.jpg")

    _write_png(data_dir / "static" / "cover" / "JAVDB" / "900001.png")
    _write_jpg(data_dir / "static" / "cover" / "JAVDB" / "900001.jpg")
    _write_png(data_dir / "static" / "cover" / "JAVDB" / "900002.png")
    _write_jpg(data_dir / "static" / "cover" / "JAVDB" / "900002.jpg")
    _write_png(data_dir / "static" / "cover" / "JAVDB" / "900003.png")
    _write_jpg(data_dir / "static" / "cover" / "JAVDB" / "900003.jpg")
    _write_jpg(data_dir / "static" / "default" / "default_cover.jpg")


def _write_manifest(runtime_root: Path, data_dir: Path, profile: str) -> None:
    media_files = sorted(
        str(path.relative_to(runtime_root)).replace("\\", "/")
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    manifest = {
        "profile": profile,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "media_file_count": len(media_files),
        "media_files": media_files,
    }
    _write_json(runtime_root / "seed_manifest.json", manifest)


def _seed_structures(data_dir: Path) -> None:
    for rel in (
        "cache/comic",
        "cache/video",
        "recommendation_cache/comic/JM",
        "recommendation_cache/video/JAVDB",
        "video/JAVDB",
        "video/JAVBUS",
        "comic/PK",
    ):
        (data_dir / rel).mkdir(parents=True, exist_ok=True)


def prepare_profile(profile: str, clean: bool = True) -> Dict[str, str]:
    runtime_root = RUNTIME_ROOT / profile
    data_dir = runtime_root / "data"
    meta_dir = data_dir / "meta_data"
    server_config_path = runtime_root / "server_config.json"
    third_party_config_path = runtime_root / "third_party_config.json"

    if clean and runtime_root.exists():
        shutil.rmtree(runtime_root, ignore_errors=True)

    runtime_root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    _seed_structures(data_dir)
    _seed_meta_data(meta_dir)
    _seed_media(data_dir)
    _write_manifest(runtime_root, data_dir, profile)

    _write_json(
        server_config_path,
        {
            "backend": {"host": "127.0.0.1", "port": 5000},
            "frontend": {"host": "127.0.0.1", "port": 5173},
            "storage": {"data_dir": str(data_dir.resolve())},
        },
    )

    _write_json(
        third_party_config_path,
        {
            "default_adapter": "jmcomic",
            "adapters": {
                "jmcomic": {"enabled": False},
                "picacomic": {"enabled": False},
                "javdb": {"enabled": False},
            },
        },
    )

    return {
        "profile": profile,
        "runtime_root": str(runtime_root.resolve()),
        "data_dir": str(data_dir.resolve()),
        "server_config_path": str(server_config_path.resolve()),
        "third_party_config_path": str(third_party_config_path.resolve()),
        "repo_root": str(REPO_ROOT.resolve()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare isolated runtime data for tests.")
    parser.add_argument("--profile", required=True, help="Runtime profile name, for example: e2e, integration.")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove existing runtime directory.")
    parser.add_argument("--json", action="store_true", help="Print runtime metadata as JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = prepare_profile(args.profile, clean=not args.no_clean)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Prepared test profile '{args.profile}' at {result['runtime_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
