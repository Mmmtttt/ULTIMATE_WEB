from __future__ import annotations

import importlib.util
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


def test_write_pyinstaller_scripts_keeps_third_party_under_backend_layout():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"pyinstaller_paths_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_third_party = staged_target_dir / "comic_backend" / "third_party"
        for plugin_name in (
            "JMComic-Crawler-Python",
            "Missav",
            "Picacomic-Crawler",
            "javdb-api-scraper",
        ):
            (backend_third_party / plugin_name).mkdir(parents=True, exist_ok=True)

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
        sep = ";" if os.name == "nt" else ":"

        assert any(f"{sep}comic_backend/third_party/JMComic-Crawler-Python" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/Missav" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/Picacomic-Crawler" in item for item in add_data_args)
        assert any(f"{sep}comic_backend/third_party/javdb-api-scraper" in item for item in add_data_args)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
