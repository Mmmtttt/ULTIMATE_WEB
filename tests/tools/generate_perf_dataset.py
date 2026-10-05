#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_tags(total: int = 200) -> List[Dict[str, Any]]:
    return [
        {
            "id": f"tag_perf_{index:04d}",
            "name": f"性能标签 {index:04d}",
            "content_type": "all",
        }
        for index in range(total)
    ]


def _pick_ids(prefix: str, pool_size: int, rnd: random.Random, min_count: int, max_count: int) -> List[str]:
    count = rnd.randint(min_count, max_count)
    return [f"{prefix}{value:04d}" for value in sorted(rnd.sample(range(pool_size), count))]


def _build_comics(total: int, tag_count: int, list_count: int) -> List[Dict[str, Any]]:
    rnd = random.Random(20260901)
    now = datetime(2026, 9, 1, 12, 0, 0)
    comics: List[Dict[str, Any]] = []
    for index in range(total):
        created = now - timedelta(minutes=index)
        total_page = rnd.randint(20, 260)
        comics.append(
            {
                "id": f"PERFC{index:06d}",
                "title": f"性能测试漫画 {index:06d}",
                "title_jp": "",
                "author": f"作者 {rnd.randint(1, 300):03d}",
                "desc": f"用于列表搜索筛选排序的性能测试数据 {index}",
                "cover_path": f"/static/cover/PERF/{index:06d}.jpg",
                "total_page": total_page,
                "current_page": rnd.randint(1, total_page),
                "score": round(rnd.uniform(1, 12) * 2) / 2,
                "tag_ids": _pick_ids("tag_perf_", tag_count, rnd, 1, 6),
                "list_ids": _pick_ids("list_perf_", list_count, rnd, 0, 3),
                "create_time": created.strftime("%Y-%m-%dT%H:%M:%S"),
                "last_read_time": (created + timedelta(hours=rnd.randint(0, 800))).strftime("%Y-%m-%dT%H:%M:%S"),
                "is_deleted": rnd.random() < 0.03,
            }
        )
    return comics


def _build_videos(total: int, tag_count: int, list_count: int) -> List[Dict[str, Any]]:
    rnd = random.Random(20260902)
    now = datetime(2026, 9, 1, 12, 0, 0)
    videos: List[Dict[str, Any]] = []
    for index in range(total):
        created = now - timedelta(minutes=index * 2)
        videos.append(
            {
                "id": f"PERFV{index:06d}",
                "code": f"PERF-{index:06d}",
                "title": f"性能测试视频 {index:06d}",
                "creator": f"制作方 {rnd.randint(1, 120):03d}",
                "actors": [f"演员 {rnd.randint(1, 500):03d}" for _ in range(rnd.randint(1, 4))],
                "desc": f"用于视频列表性能测试的数据 {index}",
                "cover_path": f"/static/cover/PERFV/{index:06d}.jpg",
                "cover_path_local": "",
                "total_units": rnd.randint(1, 20),
                "current_unit": rnd.randint(1, 20),
                "score": round(rnd.uniform(1, 12) * 2) / 2,
                "tag_ids": _pick_ids("tag_perf_", tag_count, rnd, 1, 6),
                "list_ids": _pick_ids("list_perf_", list_count, rnd, 0, 3),
                "create_time": created.strftime("%Y-%m-%dT%H:%M:%S"),
                "last_access_time": (created + timedelta(hours=rnd.randint(0, 800))).strftime("%Y-%m-%dT%H:%M:%S"),
                "date": created.strftime("%Y-%m-%d"),
                "is_deleted": rnd.random() < 0.03,
                "thumbnail_images": [],
                "thumbnail_images_local": [],
            }
        )
    return videos


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a large JSON dataset for catalog performance testing.")
    parser.add_argument("--output", required=True, help="Target meta_data directory.")
    parser.add_argument("--items", type=int, default=5000, help="Number of comics and videos to generate.")
    parser.add_argument("--tags", type=int, default=200)
    parser.add_argument("--lists", type=int, default=80)
    args = parser.parse_args()

    meta_dir = Path(args.output)
    tags = _build_tags(args.tags)
    comics = _build_comics(args.items, args.tags, args.lists)
    videos = _build_videos(args.items, args.tags, args.lists)
    today = datetime.now().strftime("%Y-%m-%d")

    _write_json(meta_dir / "tags_database.json", {"last_updated": today, "tags": tags})
    _write_json(
        meta_dir / "comics_database.json",
        {"collection_name": "Perf Comics", "total_comics": len(comics), "last_updated": today, "comics": comics},
    )
    _write_json(
        meta_dir / "videos_database.json",
        {"collection_name": "Perf Videos", "total_videos": len(videos), "last_updated": today, "videos": videos},
    )
    _write_json(meta_dir / "recommendations_database.json", {"last_updated": today, "recommendations": []})
    _write_json(meta_dir / "video_recommendations_database.json", {"last_updated": today, "video_recommendations": []})

    print(f"Generated {len(comics)} comics and {len(videos)} videos under {meta_dir}")


if __name__ == "__main__":
    main()
