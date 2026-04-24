from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from uuid import uuid4
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_package_unified_module():
    module_path = ROOT_DIR / "scripts" / "package_unified.py"
    spec = importlib.util.spec_from_file_location("package_unified_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(plugin_dir: Path, plugin_id: str, packaging: dict | None = None) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "ultimate-plugin.json").write_text(
        json.dumps(
            {
                "protocol_version": "1.0",
                "plugin": {
                    "id": plugin_id,
                    "name": plugin_id,
                    "version": "1.0.0",
                    "entrypoint": "./ultimate_provider.py:DemoProvider",
                },
                "media_types": ["comic"],
                "capabilities": [{"key": "catalog.search"}],
                "packaging": packaging or {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "ultimate_provider.py").write_text(
        "class DemoProvider:\n"
        "    def __init__(self, manifest=None, manifest_path=''):\n"
        "        self.manifest = manifest or {}\n"
        "        self.manifest_path = manifest_path\n"
        "    def execute(self, capability, params, context, config):\n"
        "        return {}\n"
        "    def normalize_config(self, payload):\n"
        "        return dict(payload or {})\n"
        "    def serialize_public_config(self, config):\n"
        "        return dict(config or {})\n",
        encoding="utf-8",
    )


def test_write_pyinstaller_scripts_keeps_third_party_under_backend_layout():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"pyinstaller_paths_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_third_party = staged_target_dir / "comic_backend" / "third_party"
        _write_manifest(
            backend_third_party / "JMComic-Crawler-Python",
            "comic.jmcomic",
            packaging={
                "pyinstaller": {
                    "collect_all": ["common", "Crypto"],
                    "pip_requirements": ["commonx>=0.6.38", "pycryptodome>=3.20.0"],
                }
            },
        )
        _write_manifest(
            backend_third_party / "Missav",
            "video.missav",
            packaging={
                "pyinstaller": {
                    "collect_all": ["curl_cffi", "cffi"],
                    "hidden_imports": ["curl_cffi._wrapper"],
                    "pip_requirements": ["curl_cffi>=0.6.0", "cffi>=1.15.0"],
                }
            },
        )
        _write_manifest(backend_third_party / "Picacomic-Crawler", "comic.picacomic")
        _write_manifest(backend_third_party / "javdb-api-scraper", "video.javdb")
        _write_manifest(
            backend_third_party / "javdb-api-scraper" / "javbus_plugin",
            "video.javbus",
            packaging={
                "pyinstaller": {
                    "collect_all": ["curl_cffi", "lxml"],
                    "pip_requirements": ["curl_cffi>=0.6.0", "lxml>=4.9.0"],
                }
            },
        )

        cmd = package_unified.write_pyinstaller_scripts(
            out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            target="windows" if os.name == "nt" else "linux",
            binary_name="ultimate_backend_test",
            entry="comic_backend/app.py",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        add_data_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--add-data"]
        collect_all_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--collect-all"]
        hidden_import_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--hidden-import"]
        sep = ";" if os.name == "nt" else ":"

        assert any(f"{sep}comic_backend/third_party/JMComic-Crawler-Python" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/Missav" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/Picacomic-Crawler" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/javdb-api-scraper" in item for item in add_data_args)
        assert collect_all_args.count("curl_cffi") == 1
        assert "common" in collect_all_args
        assert "Crypto" in collect_all_args
        assert "lxml" in collect_all_args
        assert "cffi" in collect_all_args
        assert "curl_cffi._wrapper" in hidden_import_args
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
