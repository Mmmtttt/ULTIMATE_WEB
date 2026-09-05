"""下载目录解析测试：子文件夹净化与拼接、host 引擎根目录暴露。"""
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.v1.download import _resolve_target_dir, _sanitize_subfolder


def test_sanitize_subfolder_removes_traversal():
    assert _sanitize_subfolder("../../etc") == "etc"
    assert _sanitize_subfolder("..\\..\\ABC-123") == "ABC-123"
    assert _sanitize_subfolder("A/B/C") == "C"
    assert _sanitize_subfolder("..") == ""
    assert _sanitize_subfolder("  ABC-123  ") == "ABC-123"
    # Windows 非法字符被替换/清除
    cleaned = _sanitize_subfolder('ABC:123?*"<>|')
    assert ":" not in cleaned and "?" not in cleaned


def test_resolve_prefers_explicit_dir(tmp_path):
    host = _FakeHost(base_dir=str(tmp_path / "base"))
    target = _resolve_target_dir(host, "qbittorrent", {"dir": str(tmp_path / "x")})
    assert target == str(tmp_path / "x")


def test_resolve_empty_when_no_subfolder(tmp_path):
    host = _FakeHost(base_dir=str(tmp_path / "base"))
    assert _resolve_target_dir(host, "qbittorrent", {}) == ""
    assert _resolve_target_dir(host, "qbittorrent", {"dir_subfolder": ""}) == ""


def test_resolve_joins_subfolder_and_creates(tmp_path):
    base = tmp_path / "dl"
    host = _FakeHost(base_dir=str(base))
    target = _resolve_target_dir(host, "qbittorrent", {"dir_subfolder": "ABC-123"})
    assert target == str(base / "ABC-123")
    assert (base / "ABC-123").is_dir()


def test_resolve_requires_base_dir_for_subfolder():
    host = _FakeHost(base_dir="")
    with pytest.raises(ValueError):
        _resolve_target_dir(host, "qbittorrent", {"dir_subfolder": "ABC-123"})


class _FakeHost:
    def __init__(self, base_dir):
        self._base_dir = base_dir

    def get_download_engine_base_dir(self, engine=""):
        return self._base_dir
