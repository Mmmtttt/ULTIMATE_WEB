from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_extension_service():
    module_path = ROOT_DIR / "comic_backend" / "protocol" / "extension_service.py"
    spec = importlib.util.spec_from_file_location(f"extension_service_for_test_{uuid4().hex}", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Upload:
    def __init__(self, data: bytes, filename: str = "plugin.zip"):
        self._data = data
        self.filename = filename

    def save(self, path: str) -> None:
        Path(path).write_bytes(self._data)


def _plugin_zip(plugin_id: str, requirements: list[str] | None = None, *, unsafe: bool = False) -> bytes:
    payload = {
        "protocol_version": "2.0",
        "plugin": {
            "id": plugin_id,
            "name": plugin_id,
            "entrypoint": "./ultimate_provider.py:DemoProvider",
        },
        "media_types": ["comic"],
        "packaging": {
            "external": {
                "pip_requirements": requirements or [],
            },
            "android": {
                "enabled": True,
                "pip_requirements": requirements or [],
            },
        },
    }
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        if unsafe:
            archive.writestr("../evil.txt", "bad")
        archive.writestr("demo/ultimate-plugin.json", json.dumps(payload, ensure_ascii=False))
        archive.writestr("demo/ultimate_provider.py", "class DemoProvider: pass\n")
    return raw.getvalue()


def _plugin_payload(plugin_id: str) -> dict:
    return {
        "protocol_version": "2.0",
        "plugin": {
            "id": plugin_id,
            "name": plugin_id,
            "entrypoint": "./ultimate_provider.py:DemoProvider",
        },
        "media_types": ["comic"],
        "packaging": {
            "external": {"pip_requirements": []},
            "android": {"enabled": True, "pip_requirements": []},
        },
    }


def _repo_zip_with_root_and_nested_manifests() -> bytes:
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("repo/ultimate-plugin.json", json.dumps(_plugin_payload("video.root"), ensure_ascii=False))
        archive.writestr("repo/ultimate_provider.py", "class DemoProvider: pass\n")
        archive.writestr("repo/nested/ultimate-plugin.json", json.dumps(_plugin_payload("video.nested"), ensure_ascii=False))
        archive.writestr("repo/nested/ultimate_provider.py", "class DemoProvider: pass\n")
    return raw.getvalue()


def _repo_zip_with_two_nested_manifests() -> bytes:
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("repo/a/ultimate-plugin.json", json.dumps(_plugin_payload("video.a"), ensure_ascii=False))
        archive.writestr("repo/b/ultimate-plugin.json", json.dumps(_plugin_payload("video.b"), ensure_ascii=False))
    return raw.getvalue()


def test_install_extension_zip_installs_when_dependency_pool_covers_requirements(monkeypatch, tmp_path):
    service = _load_extension_service()
    install_root = tmp_path / "plugins"
    dep_manifest = tmp_path / "dependency_pool_manifest.json"
    dep_manifest.write_text(
        json.dumps({"requirement_names": ["curl-cffi"], "requirements": ["curl_cffi==0.16.3"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(install_root))
    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(dep_manifest))
    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "full")

    result = service.install_extension_zip(_Upload(_plugin_zip("comic.demo", ["curl_cffi==0.16.3"])))

    assert result["plugin_id"] == "comic.demo"
    assert result["requires_restart"] is True
    assert (install_root / "comic.demo" / "ultimate-plugin.json").exists()
    assert service.list_extensions()["installed"][0]["plugin_id"] == "comic.demo"


def test_install_extension_zip_rejects_missing_dependency(monkeypatch, tmp_path):
    service = _load_extension_service()
    dep_manifest = tmp_path / "dependency_pool_manifest.json"
    dep_manifest.write_text(json.dumps({"requirement_names": []}), encoding="utf-8")
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(tmp_path / "plugins"))
    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(dep_manifest))

    try:
        service.install_extension_zip(_Upload(_plugin_zip("comic.demo", ["curl_cffi==0.16.3"])))
    except ValueError as exc:
        assert "扩展依赖未被当前安装包预置" in str(exc)
    else:
        raise AssertionError("missing dependency should be rejected")


def test_install_extension_zip_rejects_path_traversal(monkeypatch, tmp_path):
    service = _load_extension_service()
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(tmp_path / "plugins"))

    try:
        service.install_extension_zip(_Upload(_plugin_zip("comic.demo", unsafe=True)))
    except ValueError as exc:
        assert "不安全路径" in str(exc)
    else:
        raise AssertionError("unsafe zip member should be rejected")


def test_install_extension_zip_prefers_root_manifest_and_ignores_nested_plugins(monkeypatch, tmp_path):
    service = _load_extension_service()
    install_root = tmp_path / "plugins"
    dep_manifest = tmp_path / "dependency_pool_manifest.json"
    dep_manifest.write_text(json.dumps({"requirement_names": []}), encoding="utf-8")
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(install_root))
    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(dep_manifest))
    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "full")

    result = service.install_extension_zip(_Upload(_repo_zip_with_root_and_nested_manifests()))

    assert result["plugin_id"] == "video.root"
    assert result["ignored_manifests"] == ["nested/ultimate-plugin.json"]
    assert (install_root / "video.root" / "ultimate-plugin.json").exists()
    assert not (install_root / "video.root" / "nested" / "ultimate-plugin.json").exists()
    assert [item["plugin_id"] for item in service.list_extensions()["installed"]] == ["video.root"]


def test_install_extension_zip_rejects_ambiguous_nested_manifests(monkeypatch, tmp_path):
    service = _load_extension_service()
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(tmp_path / "plugins"))

    try:
        service.install_extension_zip(_Upload(_repo_zip_with_two_nested_manifests()))
    except ValueError as exc:
        message = str(exc)
        assert "必须明确一个根 ultimate-plugin.json" in message
        assert "repo/a/ultimate-plugin.json" in message
        assert "repo/b/ultimate-plugin.json" in message
    else:
        raise AssertionError("ambiguous nested manifests should be rejected")


def test_install_extension_from_github_downloads_repo_zip(monkeypatch, tmp_path):
    service = _load_extension_service()
    install_root = tmp_path / "plugins"
    dep_manifest = tmp_path / "dependency_pool_manifest.json"
    dep_manifest.write_text(json.dumps({"requirement_names": []}), encoding="utf-8")
    monkeypatch.setenv("ULTIMATE_USER_PLUGIN_ROOT", str(install_root))
    monkeypatch.setenv("ULTIMATE_PLUGIN_DEP_MANIFEST", str(dep_manifest))
    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "full")
    monkeypatch.setattr(service, "_resolve_github_default_branch", lambda owner, repo: "main")

    downloaded_urls = []

    def fake_download(url: str, target_path: Path) -> None:
        downloaded_urls.append(url)
        target_path.write_bytes(_plugin_zip("comic.github"))

    monkeypatch.setattr(service, "_download_url_to_file", fake_download)

    result = service.install_extension_from_github("https://github.com/example/demo-plugin")

    assert result["plugin_id"] == "comic.github"
    assert result["source"]["owner"] == "example"
    assert result["source"]["repo"] == "demo-plugin"
    assert downloaded_urls == ["https://codeload.github.com/example/demo-plugin/zip/main"]
    assert (install_root / "comic.github" / "ultimate-plugin.json").exists()
