from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

softref_reader_module = importlib.import_module("application.softref_comic_reader")
file_parser_module = importlib.import_module("utils.file_parser")

softref_comic_reader = softref_reader_module.softref_comic_reader
file_parser = file_parser_module.file_parser


def test_build_chapter_outline_returns_empty_for_flat_pages():
    chapters = file_parser.build_chapter_outline([
        "001.png",
        "002.png",
        "003.png",
    ])

    assert chapters == []


def test_build_chapter_outline_groups_numbered_top_level_directories():
    chapters = file_parser.build_chapter_outline([
        "1/001.png",
        "1/002.png",
        "2/001.png",
        "2/002.png",
        "2/003.png",
    ])

    assert chapters == [
        {
            "key": "1",
            "title": "第1章",
            "start_page": 1,
            "end_page": 2,
            "page_count": 2,
        },
        {
            "key": "2",
            "title": "第2章",
            "start_page": 3,
            "end_page": 5,
            "page_count": 3,
        },
    ]


def test_build_chapter_outline_prefers_nested_chapter_like_directories():
    chapters = file_parser.build_chapter_outline([
        "Series/第1话/001.png",
        "Series/第1话/002.png",
        "Series/第2话/001.png",
    ])

    assert [chapter["title"] for chapter in chapters] == ["第1话", "第2话"]
    assert [chapter["start_page"] for chapter in chapters] == [1, 3]


def test_softref_reader_exposes_chapter_outline_from_page_entries(monkeypatch):
    monkeypatch.setattr(
        softref_comic_reader,
        "get_page_entries",
        lambda comic_id: [
            {"sort_path": "第1话/001.png"},
            {"sort_path": "第1话/002.png"},
            {"sort_path": "第2话/001.png"},
        ],
    )

    chapters = softref_comic_reader.get_chapter_outline("LOCALTEST001")

    assert len(chapters) == 2
    assert chapters[0]["start_page"] == 1
    assert chapters[1]["start_page"] == 3
