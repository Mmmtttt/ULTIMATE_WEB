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


def test_resolve_ignores_subfolder_when_engine_cannot_choose_dir():
    """链式交接型引擎（落盘位置由对方决定）不该因为子文件夹而整个投递失败。

    前端在视频有番号时会**自动**带上 dir_subfolder，若在此硬报错，这类引擎就完全
    无法投递。忽略的事实由引擎自己在响应里回报。
    """
    host = _FakeHost(base_dir="", features={"target_dir": False})
    assert _resolve_target_dir(host, "libretorrent", {"dir_subfolder": "ABC-123"}) == ""


def test_resolve_keeps_strict_check_when_feature_unknown():
    """功能信息未知（旧引擎字典 / 取不到 features）时不放宽，保持既有契约。"""
    host = _FakeHost(base_dir="", features={})
    with pytest.raises(ValueError):
        _resolve_target_dir(host, "aria2", {"dir_subfolder": "ABC-123"})


def test_resolve_joins_when_engine_supports_target_dir(tmp_path):
    base = tmp_path / "dl"
    host = _FakeHost(base_dir=str(base), features={"target_dir": True})
    target = _resolve_target_dir(host, "aria2", {"dir_subfolder": "ABC-123"})
    assert target == str(base / "ABC-123")
    assert (base / "ABC-123").is_dir()


def test_resolve_prefers_explicit_dir_even_without_target_dir_support(tmp_path):
    """显式给了绝对路径就用它，与引擎是否暴露下载目录设置无关。"""
    host = _FakeHost(base_dir="", features={"target_dir": False})
    target = _resolve_target_dir(host, "libretorrent", {"dir": str(tmp_path / "x")})
    assert target == str(tmp_path / "x")


class _FakeHost:
    def __init__(self, base_dir, features=None):
        self._base_dir = base_dir
        self._features = features

    def get_download_engine_base_dir(self, engine=""):
        return self._base_dir

    def get_download_engine_features(self, engine=""):
        # None / {} 表示「信息未知」——此时不应放宽校验，保持既有契约
        return dict(self._features or {})
