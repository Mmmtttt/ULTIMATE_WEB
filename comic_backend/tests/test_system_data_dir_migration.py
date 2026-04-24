import shutil
import os
import sys
from pathlib import Path
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("ULTIMATE_CONFIG_DIR", str(BACKEND_ROOT / ".pytest_runtime_config"))

import api.v1.config as config_api


def _write_text(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_case_dir(case_name: str) -> Path:
    root = BACKEND_ROOT / ".pytest_runtime_tmp" / f"{case_name}_{uuid4().hex[:8]}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_move_data_dir_merges_into_existing_data_dir():
    case_dir = _make_case_dir("merge_move")
    source_dir = case_dir / "source"
    target_dir = case_dir / "target"

    _write_text(source_dir / "meta_data" / "comics_database.json", '{"comics": []}')
    _write_text(source_dir / "comic" / "JM" / "1001" / "001.jpg", "page")
    _write_text(target_dir / "meta_data" / "existing.json", "{}")

    result = config_api._move_data_dir(str(source_dir), str(target_dir))

    assert result["migrated"] is True
    assert result["mode"] == "move"
    assert not source_dir.exists()
    assert (target_dir / "meta_data" / "comics_database.json").exists()
    assert (target_dir / "comic" / "JM" / "1001" / "001.jpg").exists()


def test_move_data_dir_moves_active_runtime_and_skips_logs(monkeypatch):
    case_dir = _make_case_dir("runtime_move")
    source_dir = case_dir / "runtime_data"
    target_dir = case_dir / "target_data"

    _write_text(source_dir / "meta_data" / "videos_database.json", '{"videos": []}')
    _write_text(source_dir / "logs" / "access.log", "locked-log")
    _write_text(target_dir / "meta_data" / "existing.json", "{}")

    monkeypatch.setattr(config_api, "DATA_DIR", str(source_dir))

    result = config_api._move_data_dir(str(source_dir), str(target_dir))

    assert result["migrated"] is True
    assert result["mode"] == "runtime_move"
    assert (target_dir / "meta_data" / "videos_database.json").exists()
    assert not (target_dir / "logs" / "access.log").exists()
    assert (source_dir / "logs" / "access.log").exists()
    assert not (source_dir / "meta_data" / "videos_database.json").exists()
