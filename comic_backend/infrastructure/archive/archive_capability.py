from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

try:
    import py7zr  # type: ignore
except Exception:  # pragma: no cover
    py7zr = None


def probe_7z_encryption_capability() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "enabled": False,
        "py7zr_installed": py7zr is not None,
        "py7zr_version": "",
        "cryptodome_installed": False,
        "error": "",
    }
    if py7zr is None:
        result["error"] = "py7zr not installed"
        return result

    result["py7zr_version"] = str(getattr(py7zr, "__version__", "") or "")
    try:
        from Cryptodome.Cipher import AES  # type: ignore # noqa: F401

        result["cryptodome_installed"] = True
    except Exception:
        result["cryptodome_installed"] = False

    password = "ultimate-probe-pass"
    payload = b"ultimate-probe-ok"

    try:
        with tempfile.TemporaryDirectory(prefix="ultimate_7z_probe_") as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "probe.7z"
            extract_dir = root / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            with py7zr.SevenZipFile(str(archive_path), "w", password=password) as archive:
                archive.writestr(payload, "probe.txt")

            with py7zr.SevenZipFile(str(archive_path), "r", password=password) as archive:
                names = [str(name or "") for name in archive.getnames()]
            if "probe.txt" not in names:
                raise RuntimeError(f"missing member after create/read: {names}")

            with py7zr.SevenZipFile(str(archive_path), "r", password=password) as archive:
                archive.extractall(path=str(extract_dir))

            extracted = extract_dir / "probe.txt"
            if not extracted.exists() or not extracted.is_file():
                raise RuntimeError("extract probe file missing")
            if extracted.read_bytes() != payload:
                raise RuntimeError("extract probe payload mismatch")
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["enabled"] = True
    return result

