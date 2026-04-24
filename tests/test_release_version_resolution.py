import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import versioning


def test_resolve_release_app_version_prefers_tag_value():
    resolved = versioning.resolve_release_app_version(
        raw_version="refs/tags/v1.2.3",
        package_version="0.0.0",
        run_number="99",
    )

    assert resolved == "1.2.3"


def test_resolve_release_app_version_ignores_placeholder_package_version():
    resolved = versioning.resolve_release_app_version(
        raw_version="",
        package_version="0.0.0",
        run_number="42",
    )

    assert resolved == "0.0.42"


def test_resolve_release_app_version_uses_non_placeholder_package_version():
    resolved = versioning.resolve_release_app_version(
        raw_version="",
        package_version="2.5.0",
        run_number="42",
    )

    assert resolved == "2.5.0"


def test_release_workflow_uses_shared_versioning_script():
    workflow_path = ROOT_DIR / ".github" / "workflows" / "release-three-platforms.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")

    assert "python scripts/versioning.py" in workflow_text


def test_test_gate_workflow_checks_out_recursive_submodules():
    workflow_path = ROOT_DIR / ".github" / "workflows" / "test-gate.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")

    assert "submodules: recursive" in workflow_text
