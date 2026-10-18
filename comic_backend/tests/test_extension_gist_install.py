"""Secret Gist 扩展安装测试（全程离线）。

覆盖：gist 链接解析 → 匿名拉取后的平铺落盘 → 复用扩展安装校验
（唯一根 manifest / Android 平台声明 / 依赖池覆盖）→ 来源记录与「更新」重装。
所有网络调用都用 monkeypatch 替换，不访问 GitHub。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol import extension_service as svc

GIST_URL = "https://gist.github.com/niaonhu001/aa5a315d61ae9438b18d"
GIST_ID = "aa5a315d61ae9438b18d"


def _manifest(plugin_id: str = "video.demo", *, android: bool = True, requirements=None) -> dict:
    payload = {
        "protocol_version": "2.0",
        "plugin": {
            "id": plugin_id,
            "name": "Demo Gist Plugin",
            "version": "0.1.0",
            "entrypoint": "./ultimate_provider.py:DemoProvider",
            "config_key": "demo",
        },
        "media_types": ["video"],
        "capabilities": [{"key": "catalog.search"}],
        "packaging": {"external": {"pip_requirements": list(requirements or [])}},
    }
    if android:
        payload["packaging"]["android"] = {
            "enabled": True,
            "pip_requirements": list(requirements or []),
        }
    return payload


def _document(manifest=None, extra_files=None, public=False, truncated_provider=False) -> dict:
    files = {
        "ultimate-plugin.json": {
            "filename": "ultimate-plugin.json",
            "content": json.dumps(manifest or _manifest(), ensure_ascii=False),
        },
        "ultimate_provider.py": {
            "filename": "ultimate_provider.py",
            "content": "class DemoProvider:\n    pass\n",
        },
    }
    if truncated_provider:
        files["ultimate_provider.py"] = {
            "filename": "ultimate_provider.py",
            "truncated": True,
            "content": "",
            "raw_url": "https://gist.githubusercontent.com/raw/provider.py",
        }
    files.update(extra_files or {})
    return {"id": GIST_ID, "public": public, "files": files}


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    install_root = tmp_path / "plugins"
    config_path = tmp_path / "third_party_config.json"
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(install_root))
    monkeypatch.delenv("ULTIMATE_PLUGIN_ROOTS", raising=False)
    monkeypatch.delenv("BACKEND_PLUGIN_ROOTS", raising=False)
    monkeypatch.delenv("BACKEND_RUNTIME_PROFILE", raising=False)
    monkeypatch.delenv("ULTIMATE_PLUGIN_DEP_MANIFEST", raising=False)
    # _config_path 依赖 core.constants 的模块级常量，必须直接打桩，避免写真实配置
    monkeypatch.setattr(svc, "_config_path", lambda: config_path)
    return install_root, config_path


def _install(monkeypatch, document, url: str = GIST_URL):
    monkeypatch.setattr(svc, "_fetch_gist_document", lambda gist_id: document)
    return svc.install_extension_from_github(url)


# ---------- 链接解析 ----------

@pytest.mark.parametrize(
    "raw",
    [
        "https://gist.github.com/niaonhu001/aa5a315d61ae9438b18d",
        "gist.github.com/aa5a315d61ae9438b18d",
        "aa5a315d61ae9438b18d",
        "https://gist.github.com/user/aa5a315d61ae9438b18d/raw/deadbeef/provider.py",
        "https://gist.github.com/user/AA5A315D61AE9438B18D.json",
        # git clone 链接（.git 后缀）
        "https://gist.github.com/aa5a315d61ae9438b18d.git",
        "https://gist.github.com/niaonhu001/aa5a315d61ae9438b18d.git",
    ],
)
def test_parse_gist_url_variants(raw):
    assert svc._parse_gist_url(raw) == GIST_ID


@pytest.mark.parametrize(
    "raw",
    ["", "https://github.com/owner/repo", "https://gist.github.com/user/notanid"],
)
def test_parse_gist_url_rejects_invalid(raw):
    with pytest.raises(ValueError):
        svc._parse_gist_url(raw)


def test_gist_and_repo_urls_are_distinguished():
    assert svc._is_gist_url(GIST_URL)
    assert not svc._is_gist_url("https://github.com/owner/repo")


# ---------- 安装主流程 ----------

def test_install_secret_gist_writes_flat_files(sandbox, monkeypatch):
    install_root, config_path = sandbox
    result = _install(monkeypatch, _document())

    assert result["plugin_id"] == "video.demo"
    assert result["requires_restart"] is True
    assert result["source"]["type"] == "gist"
    assert result["source"]["secret"] is True
    assert result["source"]["files"] == ["ultimate-plugin.json", "ultimate_provider.py"]

    plugin_dir = install_root / result["directory"]
    assert (plugin_dir / "ultimate-plugin.json").is_file()
    assert (plugin_dir / "ultimate_provider.py").is_file()
    assert not (plugin_dir / "tests").exists()

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    source = saved["extension_sources"]["video.demo"]
    assert source["type"] == "gist"
    assert source["gist_id"] == GIST_ID
    assert source["url"] == GIST_URL


def test_public_gist_is_marked_not_secret(sandbox, monkeypatch):
    result = _install(monkeypatch, _document(public=True))
    assert result["source"]["secret"] is False


def test_install_requires_manifest(sandbox, monkeypatch):
    document = _document(extra_files={})
    document["files"].pop("ultimate-plugin.json")
    with pytest.raises(ValueError, match="ultimate-plugin.json"):
        _install(monkeypatch, document)


def test_gist_file_names_are_flattened(sandbox, monkeypatch):
    _, _ = sandbox
    document = _document(extra_files={"helpers/note.txt": {"content": "hi"}})
    result = _install(monkeypatch, document)
    plugin_dir = Path(result["directory"])
    assert plugin_dir  # 目录名来自 plugin.id
    assert "note.txt" in result["source"]["files"]


def test_path_traversal_file_name_rejected(sandbox, monkeypatch):
    document = _document(extra_files={"../evil.py": {"content": "x"}})
    with pytest.raises(ValueError, match="不安全路径"):
        _install(monkeypatch, document)


def test_truncated_file_falls_back_to_raw_url(sandbox, monkeypatch):
    monkeypatch.setattr(
        svc,
        "_download_bytes",
        lambda url, *, limit, error_label: b"class DemoProvider:\n    pass\n",
    )
    result = _install(monkeypatch, _document(truncated_provider=True))
    assert "ultimate_provider.py" in result["source"]["files"]


def test_empty_gist_is_rejected(sandbox, monkeypatch):
    with pytest.raises(ValueError, match="没有文件"):
        _install(monkeypatch, {"id": GIST_ID, "public": False, "files": {}})


# ---------- 复用安装校验 ----------

def test_android_profile_requires_packaging_declaration(sandbox, monkeypatch):
    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "android")
    with pytest.raises(ValueError, match="未声明支持 Android"):
        _install(monkeypatch, _document(manifest=_manifest(android=False)))


def test_android_profile_accepts_declared_packaging(sandbox, monkeypatch):
    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "android")
    result = _install(monkeypatch, _document())
    assert result["plugin_id"] == "video.demo"


def test_dependency_pool_must_cover_declared_requirements(sandbox, monkeypatch, tmp_path):
    document = _document(manifest=_manifest(requirements=["requests"]))
    with pytest.raises(ValueError, match="依赖池清单不可用"):
        _install(monkeypatch, document)

    pool = tmp_path / "pool.json"
    pool.write_text(
        json.dumps({"requirement_names": ["requests"], "requirements": ["requests>=2.31.0"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(pool))
    result = _install(monkeypatch, document)
    assert result["plugin_id"] == "video.demo"

    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(pool))
    with pytest.raises(ValueError, match="未被当前安装包预置"):
        _install(monkeypatch, _document(manifest=_manifest(requirements=["curl-cffi"])))


# ---------- 更新（重装）与来源分流 ----------

def test_reinstall_saved_gist_source(sandbox, monkeypatch):
    first = _install(monkeypatch, _document())
    monkeypatch.setattr(svc, "_fetch_gist_document", lambda gist_id: _document(public=True))
    again = svc.reinstall_saved_extension(first["plugin_id"])
    assert again["plugin_id"] == first["plugin_id"]
    assert again["source"]["type"] == "gist"


def test_github_repo_url_does_not_go_through_gist_path(sandbox, monkeypatch):
    monkeypatch.setattr(
        svc,
        "_fetch_gist_document",
        lambda gist_id: pytest.fail("repo 链接不应走 gist 流程"),
    )

    def _sentinel(url):
        raise ValueError("repo-path-reached")

    monkeypatch.setattr(svc, "_parse_github_repo_url", _sentinel)
    with pytest.raises(ValueError, match="repo-path-reached"):
        svc.install_extension_from_github("https://github.com/owner/repo")
