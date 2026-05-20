#!/usr/bin/env python3
"""
Unified packaging orchestrator on top of staged multi-target workspaces.

Expected staged input layout (from scripts/build_unified.py):
  output/multi_target/<target>/
    comic_backend/
    comic_frontend_dist/
    runtime.env
    package_manifest.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STAGED_DIR = ROOT_DIR / "output" / "multi_target"
DEFAULT_PACKAGES_DIR = ROOT_DIR / "output" / "packages"
DEFAULT_TARGETS_CONFIG = ROOT_DIR / "build" / "targets.json"
DEFAULT_PACKAGERS_CONFIG = ROOT_DIR / "build" / "packagers.json"
DEFAULT_APP_VERSION = "0.0.0"
DEFAULT_WINDOWS_FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
HOST_OVERLAY_FILENAME = "ultimate-host.json"
MOBILE_PROTOCOL_SNAPSHOT_FILENAME = "mobile_protocol_snapshot.json"
SNAPSHOT_PROVIDER_ENTRYPOINT = "protocol.snapshot_provider:MetadataOnlyProvider"
PLUGIN_PACKAGE_MODE_EXTERNAL = "external"
PLUGIN_PACKAGE_MODE_BUNDLED = "bundled"
PLUGIN_PACKAGE_MODES = (
    PLUGIN_PACKAGE_MODE_EXTERNAL,
    PLUGIN_PACKAGE_MODE_BUNDLED,
)
DEFAULT_PLUGIN_PACKAGE_MODE = PLUGIN_PACKAGE_MODE_EXTERNAL
DESKTOP_PLUGIN_RUNTIME_COLLECT_SUBMODULES = (
    "email",
    "html",
    "http",
    "urllib",
    "xml",
)
DESKTOP_PLUGIN_RUNTIME_HIDDEN_IMPORTS = (
    "base64",
    "bz2",
    "concurrent.futures",
    "concurrent.futures.thread",
    "datetime",
    "email.encoders",
    "email.generator",
    "email.header",
    "email.message",
    "email.mime",
    "email.mime.application",
    "email.mime.audio",
    "email.mime.base",
    "email.mime.image",
    "email.mime.message",
    "email.mime.multipart",
    "email.mime.nonmultipart",
    "email.mime.text",
    "email.parser",
    "email.policy",
    "email.utils",
    "gzip",
    "hashlib",
    "hmac",
    "html.entities",
    "html.parser",
    "http.client",
    "http.cookiejar",
    "http.cookies",
    "importlib.metadata",
    "importlib.resources",
    "lzma",
    "mimetypes",
    "netrc",
    "queue",
    "secrets",
    "selectors",
    "socket",
    "ssl",
    "threading",
    "urllib.error",
    "urllib.parse",
    "urllib.request",
    "urllib.response",
    "urllib.robotparser",
    "uuid",
    "xml.dom",
    "xml.dom.minidom",
    "xml.etree",
    "xml.etree.ElementPath",
    "xml.etree.ElementTree",
    "xml.parsers",
    "xml.parsers.expat",
    "zlib",
)


@dataclass
class PackageResult:
    target: str
    status: str
    message: str
    output_dir: str
    command: Optional[List[str]] = None


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def parse_runtime_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def normalize_plugin_package_mode(raw: str, default: str = DEFAULT_PLUGIN_PACKAGE_MODE) -> str:
    mode = str(raw or "").strip().lower()
    if not mode:
        mode = default
    aliases = {
        "external_plugins": PLUGIN_PACKAGE_MODE_EXTERNAL,
        "hotplug": PLUGIN_PACKAGE_MODE_EXTERNAL,
        "dynamic": PLUGIN_PACKAGE_MODE_EXTERNAL,
        "compiled": PLUGIN_PACKAGE_MODE_BUNDLED,
        "embedded": PLUGIN_PACKAGE_MODE_BUNDLED,
        "builtin": PLUGIN_PACKAGE_MODE_BUNDLED,
    }
    mode = aliases.get(mode, mode)
    if mode not in PLUGIN_PACKAGE_MODES:
        raise ValueError(f"unsupported plugin package mode: {raw}")
    return mode


def normalize_app_version(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.lower().startswith("refs/tags/"):
        text = text.split("/", 2)[-1]
    if text.startswith(("v", "V")) and re.search(r"\d", text[1:]):
        text = text[1:]
    return text.strip()


def resolve_app_version_from_staged(staged_target_dir: Path) -> str:
    candidates: List[str] = []

    manifest_path = staged_target_dir / "package_manifest.json"
    if manifest_path.exists():
        try:
            payload = load_json(manifest_path)
            candidates.append(str(payload.get("app_version", "")).strip())
        except Exception:
            pass

    runtime_env = parse_runtime_env(staged_target_dir / "runtime.env")
    candidates.append(runtime_env.get("ULTIMATE_APP_VERSION", ""))
    candidates.extend(
        [
            os.environ.get("ULTIMATE_APP_VERSION", ""),
            os.environ.get("GITHUB_REF_NAME", ""),
            os.environ.get("GITHUB_REF", ""),
        ]
    )

    for candidate in candidates:
        normalized = normalize_app_version(candidate)
        if normalized and re.search(r"\d", normalized):
            return normalized
    return DEFAULT_APP_VERSION


def resolve_android_version_meta(app_version: str) -> Tuple[str, int]:
    version_name = normalize_app_version(app_version) or DEFAULT_APP_VERSION
    nums = [int(part) for part in re.findall(r"\d+", version_name)]
    major = nums[0] if len(nums) > 0 else 0
    minor = nums[1] if len(nums) > 1 else 0
    patch = nums[2] if len(nums) > 2 else 0
    major = max(0, min(major, 999))
    minor = max(0, min(minor, 999))
    patch = max(0, min(patch, 999))
    version_code = major * 1_000_000 + minor * 1_000 + patch
    return version_name, max(1, version_code)


def run_cmd(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (process.stdout or "") + (process.stderr or "")
    return process.returncode, output


def is_pyinstaller_available() -> bool:
    return importlib.util.find_spec("PyInstaller") is not None


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def select_targets(targets: List[str], requested: str) -> List[str]:
    available = [item.strip().lower() for item in targets if item.strip()]
    if requested.strip().lower() == "all":
        return available
    selected = [item.strip().lower() for item in requested.split(",") if item.strip()]
    unknown = [item for item in selected if item not in available]
    if unknown:
        raise ValueError(f"unknown targets: {', '.join(unknown)}")
    return selected


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_repeated_cli_option(cmd: List[str], option: str, values: List[str] | Tuple[str, ...]) -> None:
    for value in _normalize_string_list(values):
        cmd.extend([option, value])


def has_non_ascii_path(path: Path) -> bool:
    return any(ord(ch) > 127 for ch in str(path))


def choose_android_workspace_dir(target_out_dir: Path, staged_target_dir: Path, packager_cfg: Dict) -> Path:
    workspace_leaf = f"{target_out_dir.parent.name}_{target_out_dir.name}_{staged_target_dir.name}"
    configured_root = str(packager_cfg.get("workspace_root", "")).strip()
    if configured_root:
        root = Path(configured_root).expanduser().resolve()
        return root / workspace_leaf

    default_workspace = target_out_dir / "android_workspace"
    if os.name != "nt" or not has_non_ascii_path(default_workspace):
        return default_workspace / workspace_leaf

    env_root = os.environ.get("ULTIMATE_ANDROID_WORKSPACE_ROOT", "").strip()
    if env_root:
        fallback_root = Path(env_root).expanduser().resolve()
    else:
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        if local_appdata:
            fallback_root = Path(local_appdata) / "UltimateWebBuild" / "android_workspace"
        else:
            fallback_root = Path.home() / "AppData" / "Local" / "UltimateWebBuild" / "android_workspace"
    return fallback_root / workspace_leaf


def get_android_workspace_backend_dir(packager_cfg: Dict) -> str:
    return str(packager_cfg.get("workspace_backend_dir", "_backend_build_input")).strip() or "_backend_build_input"


def get_npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def get_npx_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def resolve_android_sdk_dir() -> str:
    for key in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(key, "").strip()
        if value and Path(value).exists():
            return str(Path(value).resolve())

    candidates: List[Path] = []
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        if local_appdata:
            candidates.append(Path(local_appdata) / "Android" / "Sdk")
        userprofile = os.environ.get("USERPROFILE", "").strip()
        if userprofile:
            candidates.append(Path(userprofile) / "AppData" / "Local" / "Android" / "Sdk")
    else:
        home = Path.home()
        candidates.extend([
            home / "Android" / "Sdk",
            home / "Library" / "Android" / "sdk",
        ])

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def write_android_local_properties(android_project_dir: Path, sdk_dir: str) -> Path:
    local_properties = android_project_dir / "local.properties"
    escaped = sdk_dir.replace("\\", "\\\\")
    write_text(local_properties, f"sdk.dir={escaped}\n")
    return local_properties


def apply_android_launcher_icon(workspace_dir: Path, packager_cfg: Dict) -> None:
    icon_source_raw = str(packager_cfg.get("icon_source", "")).strip()
    if not icon_source_raw:
        return

    icon_source = Path(icon_source_raw)
    if not icon_source.is_absolute():
        icon_source = (ROOT_DIR / icon_source).resolve()
    if not icon_source.exists():
        raise FileNotFoundError(f"android icon source not found: {icon_source}")

    ext = icon_source.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError(f"android icon source format not supported: {icon_source.name}")

    android_main = workspace_dir / "android" / "app" / "src" / "main"
    if not android_main.exists():
        raise FileNotFoundError(f"android main source dir not found: {android_main}")

    resource_name = "app_icon"
    drawable_dir = android_main / "res" / "drawable"
    drawable_dir.mkdir(parents=True, exist_ok=True)

    target_suffix = ".jpg" if ext in {".jpg", ".jpeg"} else ext
    target_image = drawable_dir / f"{resource_name}{target_suffix}"
    for stale in drawable_dir.glob(f"{resource_name}.*"):
        if stale != target_image:
            stale.unlink()
    shutil.copy2(icon_source, target_image)

    manifest_path = android_main / "AndroidManifest.xml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"android manifest not found: {manifest_path}")
    manifest_raw = manifest_path.read_text(encoding="utf-8")
    manifest_patched = re.sub(
        r'android:icon="[^"]*"',
        f'android:icon="@drawable/{resource_name}"',
        manifest_raw,
        count=1,
    )
    manifest_patched = re.sub(
        r'android:roundIcon="[^"]*"',
        f'android:roundIcon="@drawable/{resource_name}"',
        manifest_patched,
        count=1,
    )
    if manifest_patched != manifest_raw:
        write_text(manifest_path, manifest_patched)


def patch_android_min_sdk(android_project_dir: Path, min_sdk: int) -> None:
    variables_gradle = android_project_dir / "variables.gradle"
    if not variables_gradle.exists():
        return
    raw = variables_gradle.read_text(encoding="utf-8")
    patched = re.sub(
        r"(minSdkVersion\s*=\s*)(\d+)",
        lambda m: f"{m.group(1)}{max(int(m.group(2)), min_sdk)}",
        raw,
    )
    if patched != raw:
        write_text(variables_gradle, patched)


def ensure_android_project_chaquopy_root(android_project_dir: Path, chaquopy_version: str) -> None:
    build_gradle = android_project_dir / "build.gradle"
    if not build_gradle.exists():
        return
    raw = build_gradle.read_text(encoding="utf-8")
    patched = raw

    if "https://chaquo.com/maven" not in patched:
        patched = patched.replace(
            "mavenCentral()\n",
            "mavenCentral()\n        maven { url 'https://chaquo.com/maven' }\n",
            1,
        )
        patched = patched.replace(
            "mavenCentral()\n",
            "mavenCentral()\n        maven { url 'https://chaquo.com/maven' }\n",
            1,
        )

    classpath_line = f"        classpath 'com.chaquo.python:gradle:{chaquopy_version}'\n"
    if "com.chaquo.python:gradle" not in patched:
        marker = "        classpath 'com.google.gms:google-services:4.4.2'\n"
        if marker in patched:
            patched = patched.replace(marker, marker + classpath_line, 1)
        else:
            patched = patched.replace(
                "dependencies {\n",
                "dependencies {\n" + classpath_line,
                1,
            )

    if patched != raw:
        write_text(build_gradle, patched)


def ensure_android_manifest_network(android_project_dir: Path) -> None:
    manifest = android_project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        return
    raw = manifest.read_text(encoding="utf-8")
    patched = raw
    permission_lines = [
        '<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />',
        '<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="28" />',
        '<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />',
        '<uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />',
        '<uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />',
    ]
    for line in permission_lines:
        permission_name = ""
        marker = 'android:name="'
        if marker in line:
            permission_name = line.split(marker, 1)[1].split('"', 1)[0]
        if permission_name and permission_name in patched:
            continue
        if "<application" in patched:
            patched = patched.replace("<application", f"    {line}\n\n    <application", 1)
    if 'android:usesCleartextTraffic="true"' not in patched and "<application" in patched:
        patched = patched.replace("<application", '<application\n        android:usesCleartextTraffic="true"', 1)

    archive_intent_marker = "ULTIMATE_ARCHIVE_OPEN_INTENT_START"
    if archive_intent_marker not in patched:
        archive_intent_block = (
            "            <!-- ULTIMATE_ARCHIVE_OPEN_INTENT_START -->\n"
            "            <intent-filter>\n"
            "                <action android:name=\"android.intent.action.VIEW\" />\n"
            "                <action android:name=\"android.intent.action.SEND\" />\n"
            "                <category android:name=\"android.intent.category.DEFAULT\" />\n"
            "                <data android:mimeType=\"application/zip\" />\n"
            "                <data android:mimeType=\"application/x-zip-compressed\" />\n"
            "                <data android:mimeType=\"application/vnd.rar\" />\n"
            "                <data android:mimeType=\"application/x-rar-compressed\" />\n"
            "                <data android:mimeType=\"application/x-7z-compressed\" />\n"
            "                <data android:mimeType=\"application/octet-stream\" />\n"
            "            </intent-filter>\n"
            "            <!-- ULTIMATE_ARCHIVE_OPEN_INTENT_END -->\n"
        )
        activity_pattern = re.compile(
            r"(<activity[^>]*android:name=\"(?:\\.MainActivity|[^\"]*MainActivity)\"[^>]*>)(.*?)(</activity>)",
            flags=re.DOTALL,
        )
        match = activity_pattern.search(patched)
        if match:
            body = match.group(2)
            if archive_intent_marker not in body:
                new_body = body.rstrip() + "\n" + archive_intent_block + "        "
                patched = patched[:match.start(2)] + new_body + patched[match.end(2):]

    if patched != raw:
        write_text(manifest, patched)


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_android_signing_config(packager_cfg: Dict) -> Dict[str, str | bool | Path]:
    enabled = parse_bool(packager_cfg.get("android_signing_enabled", True), default=True)
    keystore_raw = str(
        packager_cfg.get("android_signing_keystore", "build/android_signing/ultimate-release.keystore")
    ).strip() or "build/android_signing/ultimate-release.keystore"
    keystore_path = Path(keystore_raw)
    if not keystore_path.is_absolute():
        keystore_path = (ROOT_DIR / keystore_path).resolve()

    module_keystore_name = str(
        packager_cfg.get("android_signing_module_keystore_name", "ultimate-release.keystore")
    ).strip() or "ultimate-release.keystore"
    key_alias = str(packager_cfg.get("android_signing_key_alias", "ultimate")).strip() or "ultimate"
    store_password = (
        str(packager_cfg.get("android_signing_store_password", "ultimate123456")).strip() or "ultimate123456"
    )
    key_password = str(packager_cfg.get("android_signing_key_password", store_password)).strip() or store_password
    dname = str(
        packager_cfg.get(
            "android_signing_dname",
            "CN=Ultimate Web, OU=ULTIMATE_WEB, O=Mmmtttt, L=Internet, ST=Internet, C=CN",
        )
    ).strip() or "CN=Ultimate Web, OU=ULTIMATE_WEB, O=Mmmtttt, L=Internet, ST=Internet, C=CN"
    validity_days = int(packager_cfg.get("android_signing_validity_days", 36500))
    validity_days = max(1, validity_days)

    return {
        "enabled": enabled,
        "keystore_path": keystore_path,
        "module_keystore_name": module_keystore_name,
        "key_alias": key_alias,
        "store_password": store_password,
        "key_password": key_password,
        "dname": dname,
        "validity_days": validity_days,
    }


def ensure_android_signing_keystore(signing_cfg: Dict[str, str | bool | Path]) -> None:
    if not bool(signing_cfg.get("enabled", False)):
        return

    keystore_path = Path(str(signing_cfg.get("keystore_path", "")))
    if not str(keystore_path):
        raise RuntimeError("android signing keystore path is empty")
    if keystore_path.exists():
        return

    keytool = shutil.which("keytool")
    if not keytool:
        raise RuntimeError("android signing requires keytool, but keytool was not found in PATH")

    keystore_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        keytool,
        "-genkeypair",
        "-v",
        "-storetype",
        "PKCS12",
        "-keystore",
        str(keystore_path),
        "-alias",
        str(signing_cfg.get("key_alias", "ultimate")),
        "-storepass",
        str(signing_cfg.get("store_password", "")),
        "-keypass",
        str(signing_cfg.get("key_password", "")),
        "-keyalg",
        "RSA",
        "-keysize",
        "2048",
        "-validity",
        str(signing_cfg.get("validity_days", 36500)),
        "-dname",
        str(signing_cfg.get("dname", "")),
        "-noprompt",
    ]
    code, output = run_cmd(cmd, cwd=ROOT_DIR)
    if code != 0 or not keystore_path.exists():
        raise RuntimeError(
            f"failed to generate android signing keystore: {keystore_path}\n{output}"
        )


def _groovy_escape(text: str) -> str:
    return str(text or "").replace("\\", "\\\\").replace('"', '\\"')


def apply_android_version_and_signing(
    app_build_gradle: Path,
    version_name: str,
    version_code: int,
    signing_cfg: Dict[str, str | bool | Path],
) -> None:
    raw = app_build_gradle.read_text(encoding="utf-8")
    patched = raw

    marker_start = "// ULTIMATE_ANDROID_VERSION_SIGNING_START"
    marker_end = "// ULTIMATE_ANDROID_VERSION_SIGNING_END"
    block_regex = re.compile(
        re.escape(marker_start) + r".*?" + re.escape(marker_end) + r"\n?",
        flags=re.DOTALL,
    )
    patched = re.sub(block_regex, "", patched).rstrip() + "\n\n"

    if bool(signing_cfg.get("enabled", False)):
        signing_block = (
            f"{marker_start}\n"
            "android {\n"
            "    defaultConfig {\n"
            f"        versionName \"{_groovy_escape(version_name)}\"\n"
            f"        versionCode {int(version_code)}\n"
            "    }\n"
            "    signingConfigs {\n"
            "        create(\"ultimateRelease\") {\n"
            f"            storeFile file(\"{_groovy_escape(str(signing_cfg.get('module_keystore_name', 'ultimate-release.keystore')))}\")\n"
            f"            storePassword \"{_groovy_escape(str(signing_cfg.get('store_password', '')))}\"\n"
            f"            keyAlias \"{_groovy_escape(str(signing_cfg.get('key_alias', 'ultimate')))}\"\n"
            f"            keyPassword \"{_groovy_escape(str(signing_cfg.get('key_password', '')))}\"\n"
            "        }\n"
            "    }\n"
            "    buildTypes {\n"
            "        debug {\n"
            "            signingConfig signingConfigs.ultimateRelease\n"
            "        }\n"
            "        release {\n"
            "            signingConfig signingConfigs.ultimateRelease\n"
            "        }\n"
            "    }\n"
            "}\n"
            f"{marker_end}\n"
        )
    else:
        signing_block = (
            f"{marker_start}\n"
            "android {\n"
            "    defaultConfig {\n"
            f"        versionName \"{_groovy_escape(version_name)}\"\n"
            f"        versionCode {int(version_code)}\n"
            "    }\n"
            "}\n"
            f"{marker_end}\n"
        )

    patched += signing_block
    if patched != raw:
        write_text(app_build_gradle, patched)


def copy_android_archive_tools_to_python_source(py_dir: Path, packager_cfg: Dict) -> Dict[str, Any]:
    source_dir_raw = str(packager_cfg.get("android_archive_tools_dir", "build/android_archive_tools")).strip()
    binary_name = str(packager_cfg.get("android_archive_tool_binary_name", "7zz")).strip() or "7zz"
    configured_abis = packager_cfg.get("android_archive_tool_abis", ["arm64-v8a", "x86_64"])
    if not isinstance(configured_abis, list) or not configured_abis:
        configured_abis = ["arm64-v8a", "x86_64"]
    abi_list = [str(item or "").strip() for item in configured_abis if str(item or "").strip()]
    if not abi_list:
        abi_list = ["arm64-v8a", "x86_64"]

    if not source_dir_raw:
        return {"copied": [], "missing": abi_list, "source_dir": ""}

    source_dir = Path(source_dir_raw)
    if not source_dir.is_absolute():
        source_dir = (ROOT_DIR / source_dir).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        return {"copied": [], "missing": abi_list, "source_dir": str(source_dir)}

    target_root = py_dir / "_android_tools" / "archive"
    target_root.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    missing: List[str] = []
    for abi in abi_list:
        src = source_dir / abi / binary_name
        if not src.exists() or not src.is_file():
            missing.append(abi)
            continue
        dst_dir = target_root / abi
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / binary_name
        shutil.copy2(src, dst)
        try:
            dst.chmod(0o755)
        except OSError:
            pass
        copied.append(abi)

    return {"copied": copied, "missing": missing, "source_dir": str(source_dir)}


def ensure_android_project_chaquopy_app(
    android_project_dir: Path,
    workspace_dir: Path,
    packager_cfg: Dict,
    app_version: str,
) -> None:
    workspace_web_dir = str(packager_cfg.get("workspace_web_dir", "web")).strip() or "web"
    workspace_backend_dir = get_android_workspace_backend_dir(packager_cfg)
    app_build_gradle = android_project_dir / "app" / "build.gradle"
    if not app_build_gradle.exists():
        return
    raw = app_build_gradle.read_text(encoding="utf-8")
    patched = raw

    if "apply plugin: 'com.chaquo.python'" not in patched:
        patched = patched.replace(
            "apply plugin: 'com.android.application'\n",
            "apply plugin: 'com.android.application'\napply plugin: 'com.chaquo.python'\n",
            1,
        )

    if "abiFilters" not in patched:
        patched = patched.replace(
            "        minSdkVersion rootProject.ext.minSdkVersion\n",
            "        minSdkVersion rootProject.ext.minSdkVersion\n"
            "        ndk {\n"
            "            abiFilters 'arm64-v8a', 'x86_64'\n"
            "        }\n",
            1,
        )

    chaquopy_python = str(packager_cfg.get("chaquopy_python_version", "3.13")).strip() or "3.13"
    py_exe = str(packager_cfg.get("chaquopy_build_python", "")).strip()
    if not py_exe:
        py_exe = sys.executable
    py_exe = py_exe.replace("\\", "/")

    reqs = packager_cfg.get("embed_backend_requirements")
    if not isinstance(reqs, list) or not reqs:
        reqs = [
            "flask==2.3.0",
            "flask-cors==4.0.0",
            "requests>=2.31.0",
            "PyYAML",
            "Pillow",
            "beautifulsoup4",
            "rarfile>=4.2",
        ]
    req_lines = "\n".join([f'                install("{item}")' for item in reqs if str(item).strip()])
    chaquopy_block = (
        "\nchaquopy {\n"
        "    defaultConfig {\n"
        f'        version = "{chaquopy_python}"\n'
        f'        buildPython("{py_exe}")\n'
        "        pip {\n"
        f"{req_lines}\n"
        "        }\n"
        "    }\n"
        "    sourceSets {\n"
        "        main {\n"
        '            srcDirs = ["src/main/python"]\n'
        "        }\n"
        "    }\n"
        "}\n"
    )
    if "chaquopy {" not in patched:
        if "\nrepositories {" in patched:
            patched = patched.replace("\nrepositories {", chaquopy_block + "\nrepositories {", 1)
        else:
            patched = patched + chaquopy_block

    if patched != raw:
        write_text(app_build_gradle, patched)

    version_name, version_code = resolve_android_version_meta(app_version)
    signing_cfg = resolve_android_signing_config(packager_cfg)
    if bool(signing_cfg.get("enabled", False)):
        ensure_android_signing_keystore(signing_cfg)
        source_keystore = Path(str(signing_cfg.get("keystore_path", "")))
        module_keystore_name = str(signing_cfg.get("module_keystore_name", "ultimate-release.keystore"))
        module_keystore_path = android_project_dir / "app" / module_keystore_name
        module_keystore_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_keystore, module_keystore_path)

    apply_android_version_and_signing(
        app_build_gradle=app_build_gradle,
        version_name=version_name,
        version_code=version_code,
        signing_cfg=signing_cfg,
    )

    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip() or "com.ultimate.web"
    backend_port = int(packager_cfg.get("backend_port", 5000))
    third_party_enabled = str(packager_cfg.get("android_backend_enable_third_party", "false")).strip().lower()
    java_rel = Path(*app_id.split(".")) / "MainActivity.java"
    java_path = android_project_dir / "app" / "src" / "main" / "java" / java_rel
    java_source = f"""package {app_id};

import android.Manifest;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.util.Log;
import android.webkit.WebView;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.BridgeActivity;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends BridgeActivity {{
    private static final String TAG = "UltimateEmbeddedBackend";
    private static final AtomicBoolean BACKEND_STARTED = new AtomicBoolean(false);
    private static final int REQUEST_STORAGE_PERMISSION = 1101;
    private static final int ARCHIVE_EVENT_RETRY_COUNT = 6;
    private static final long ARCHIVE_EVENT_RETRY_INTERVAL_MS = 420L;
    private static final String ARCHIVE_SESSION_KEY = "ultimate_android_open_archive_path";
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private Runnable pendingArchiveDispatchTask = null;
    private volatile String pendingArchivePath = null;

    @Override
    public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        normalizeWebViewTextScale();
        ensureStorageAccessPermission();
        startEmbeddedBackend();
        captureArchiveIntent(getIntent());
    }}

    @Override
    public void onResume() {{
        super.onResume();
        normalizeWebViewTextScale();
        dispatchPendingArchivePathWithRetry();
    }}

    @Override
    protected void onNewIntent(Intent intent) {{
        super.onNewIntent(intent);
        setIntent(intent);
        captureArchiveIntent(intent);
        dispatchPendingArchivePathWithRetry();
    }}

    @Override
    public void onBackPressed() {{
        if (bridge != null) {{
            WebView webView = bridge.getWebView();
            if (webView != null && webView.canGoBack()) {{
                webView.goBack();
                return;
            }}
        }}
        super.onBackPressed();
    }}

    private void normalizeWebViewTextScale() {{
        try {{
            if (bridge == null) {{
                return;
            }}
            WebView webView = bridge.getWebView();
            if (webView == null || webView.getSettings() == null) {{
                return;
            }}
            // Keep APK typography aligned with mobile browser defaults.
            webView.getSettings().setTextZoom(100);
            webView.getSettings().setUseWideViewPort(true);
            webView.getSettings().setLoadWithOverviewMode(false);
        }} catch (Throwable ex) {{
            Log.w(TAG, "Failed to normalize WebView text scale", ex);
        }}
    }}

    private void ensureStorageAccessPermission() {{
        try {{
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
                if (!Environment.isExternalStorageManager()) {{
                    Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                }}
                return;
            }}

            boolean readGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED;
            boolean writeGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED;
            if (!readGranted || !writeGranted) {{
                ActivityCompat.requestPermissions(
                    this,
                    new String[] {{
                        Manifest.permission.READ_EXTERNAL_STORAGE,
                        Manifest.permission.WRITE_EXTERNAL_STORAGE
                    }},
                    REQUEST_STORAGE_PERMISSION
                );
            }}
        }} catch (Throwable ex) {{
            Log.w(TAG, "Failed to request storage permissions", ex);
        }}
    }}

    private void startEmbeddedBackend() {{
        if (!BACKEND_STARTED.compareAndSet(false, true)) {{
            return;
        }}
        String dataRoot = null;
        if (getApplicationContext().getExternalFilesDir(null) != null) {{
            dataRoot = getApplicationContext().getExternalFilesDir(null).getAbsolutePath();
        }}
        if (dataRoot == null || dataRoot.trim().isEmpty()) {{
            dataRoot = getApplicationContext().getFilesDir().getAbsolutePath();
        }}
        final String filesDir = dataRoot;
        final String internalFilesDir = getApplicationContext().getFilesDir().getAbsolutePath();
        final int backendPort = {backend_port};
        new Thread(() -> {{
            try {{
                if (!Python.isStarted()) {{
                    Python.start(new AndroidPlatform(getApplicationContext()));
                }}
                PyObject module = Python.getInstance().getModule("ultimate_android_backend");
                module.callAttr("start_backend", filesDir, "127.0.0.1", backendPort, "{third_party_enabled}", internalFilesDir);
                Log.i(TAG, "Embedded backend startup invoked on port " + backendPort);
            }} catch (Throwable ex) {{
                Log.e(TAG, "Failed to start embedded backend", ex);
            }}
        }}, "ultimate-backend-thread").start();
    }}

    private boolean isSupportedArchiveName(String name) {{
        String lower = String.valueOf(name == null ? "" : name).trim().toLowerCase();
        return lower.endsWith(".zip") || lower.endsWith(".rar") || lower.endsWith(".7z");
    }}

    private String sanitizeFileName(String name) {{
        String base = String.valueOf(name == null ? "" : name).trim();
        if (base.isEmpty()) {{
            return "incoming_archive.zip";
        }}
        String sanitized = base.replaceAll("[^A-Za-z0-9._-]", "_");
        if (!isSupportedArchiveName(sanitized)) {{
            sanitized = sanitized + ".zip";
        }}
        return sanitized;
    }}

    private String queryDisplayName(Uri uri) {{
        if (uri == null) {{
            return "";
        }}
        Cursor cursor = null;
        try {{
            cursor = getContentResolver().query(uri, null, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {{
                int idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0) {{
                    String value = cursor.getString(idx);
                    if (value != null) {{
                        return value;
                    }}
                }}
            }}
        }} catch (Throwable ex) {{
            Log.w(TAG, "Failed to query display name from uri", ex);
        }} finally {{
            if (cursor != null) {{
                cursor.close();
            }}
        }}
        return "";
    }}

    private String inferArchiveFileName(Uri uri) {{
        String displayName = queryDisplayName(uri);
        if (isSupportedArchiveName(displayName)) {{
            return displayName;
        }}
        String fromPath = uri != null ? uri.getLastPathSegment() : "";
        if (isSupportedArchiveName(fromPath)) {{
            return fromPath;
        }}
        return "incoming_archive.zip";
    }}

    private String copyContentUriToLocalArchive(Uri uri) {{
        if (uri == null) {{
            return null;
        }}
        try {{
            ContentResolver resolver = getContentResolver();
            InputStream input = resolver.openInputStream(uri);
            if (input == null) {{
                return null;
            }}

            File root = getApplicationContext().getExternalFilesDir(null);
            if (root == null) {{
                root = getApplicationContext().getFilesDir();
            }}
            File incomingDir = new File(root, "incoming_archives");
            if (!incomingDir.exists() && !incomingDir.mkdirs()) {{
                Log.w(TAG, "Failed to create incoming archive dir: " + incomingDir.getAbsolutePath());
            }}

            String fileName = sanitizeFileName(inferArchiveFileName(uri));
            String uniqueName = System.currentTimeMillis() + "_" + fileName;
            File target = new File(incomingDir, uniqueName);

            try (InputStream in = input; OutputStream out = new FileOutputStream(target)) {{
                byte[] buffer = new byte[8192];
                int read;
                while ((read = in.read(buffer)) > 0) {{
                    out.write(buffer, 0, read);
                }}
                out.flush();
            }}

            if (target.exists()) {{
                return target.getAbsolutePath();
            }}
        }} catch (Throwable ex) {{
            Log.e(TAG, "Failed to copy content uri archive to local storage", ex);
        }}
        return null;
    }}

    private String resolveArchivePathFromIntent(Intent intent) {{
        if (intent == null) {{
            return null;
        }}
        try {{
            String action = intent.getAction();
            Uri uri = null;

            if (Intent.ACTION_VIEW.equals(action)) {{
                uri = intent.getData();
            }} else if (Intent.ACTION_SEND.equals(action)) {{
                Object streamObj = intent.getParcelableExtra(Intent.EXTRA_STREAM);
                if (streamObj instanceof Uri) {{
                    uri = (Uri) streamObj;
                }}
                if (uri == null) {{
                    uri = intent.getData();
                }}
            }} else {{
                return null;
            }}

            if (uri == null) {{
                return null;
            }}

            String scheme = String.valueOf(uri.getScheme() == null ? "" : uri.getScheme()).trim().toLowerCase();
            if ("file".equals(scheme)) {{
                String path = uri.getPath();
                if (isSupportedArchiveName(path)) {{
                    return path;
                }}
                return null;
            }}
            if ("content".equals(scheme)) {{
                return copyContentUriToLocalArchive(uri);
            }}
            return null;
        }} catch (Throwable ex) {{
            Log.w(TAG, "Failed to resolve archive path from intent", ex);
            return null;
        }}
    }}

    private void captureArchiveIntent(Intent intent) {{
        String path = resolveArchivePathFromIntent(intent);
        if (path == null || path.trim().isEmpty()) {{
            return;
        }}
        pendingArchivePath = path.trim();
        Log.i(TAG, "Captured archive open intent path: " + pendingArchivePath);
    }}

    private boolean emitArchivePathToWeb(String path) {{
        try {{
            if (path == null || path.trim().isEmpty()) {{
                return false;
            }}
            if (bridge == null) {{
                return false;
            }}
            WebView webView = bridge.getWebView();
            if (webView == null) {{
                return false;
            }}
            final String archivePath = path.trim();
            final String escaped = JSONObject.quote(archivePath);
            final String js = "try {{"
                + "window.sessionStorage.setItem(" + JSONObject.quote(ARCHIVE_SESSION_KEY) + ", " + escaped + ");"
                + "window.dispatchEvent(new CustomEvent('ultimateArchiveOpen', {{ detail: {{ path: " + escaped + " }} }}));"
                + "}} catch (e) {{}}";
            webView.post(() -> {{
                try {{
                    webView.evaluateJavascript(js, null);
                }} catch (Throwable ex) {{
                    Log.w(TAG, "Failed to dispatch archive open event to web", ex);
                }}
            }});
            return true;
        }} catch (Throwable ex) {{
            Log.w(TAG, "Failed to emit archive path to web", ex);
            return false;
        }}
    }}

    private void dispatchPendingArchivePathWithRetry() {{
        final String path = pendingArchivePath;
        if (path == null || path.trim().isEmpty()) {{
            return;
        }}
        if (pendingArchiveDispatchTask != null) {{
            mainHandler.removeCallbacks(pendingArchiveDispatchTask);
            pendingArchiveDispatchTask = null;
        }}

        final int[] retries = new int[] {{ ARCHIVE_EVENT_RETRY_COUNT }};
        pendingArchiveDispatchTask = new Runnable() {{
            @Override
            public void run() {{
                if (retries[0] <= 0) {{
                    pendingArchivePath = null;
                    pendingArchiveDispatchTask = null;
                    return;
                }}

                emitArchivePathToWeb(path);
                retries[0] -= 1;

                if (retries[0] <= 0) {{
                    pendingArchivePath = null;
                    pendingArchiveDispatchTask = null;
                    return;
                }}
                mainHandler.postDelayed(this, ARCHIVE_EVENT_RETRY_INTERVAL_MS);
            }}
        }};
        mainHandler.postDelayed(pendingArchiveDispatchTask, 240L);
    }}
}}
"""
    write_text(java_path, java_source)

    py_dir = android_project_dir / "app" / "src" / "main" / "python"
    py_dir.mkdir(parents=True, exist_ok=True)
    source_backend_dir = workspace_dir / workspace_backend_dir
    if source_backend_dir.exists():
        excluded_names = {
            "__pycache__",
            ".git",
            ".idea",
            ".vscode",
            "venv",
            "data",
            "logs",
            "output",
            "third_party",
        }
        for item in source_backend_dir.iterdir():
            if item.name in excluded_names:
                continue
            target = py_dir / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    protocol_dir = py_dir / "protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)
    third_party_root = source_backend_dir / "third_party"
    snapshot_payload = build_mobile_protocol_snapshot(third_party_root)
    snapshot_path = protocol_dir / MOBILE_PROTOCOL_SNAPSHOT_FILENAME
    write_text(snapshot_path, json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n")
    embedded_snapshot_json = json.dumps(
        snapshot_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    archive_copy_status = copy_android_archive_tools_to_python_source(py_dir, packager_cfg)
    copied_abis = list(archive_copy_status.get("copied") or [])
    missing_abis = list(archive_copy_status.get("missing") or [])
    source_dir_text = str(archive_copy_status.get("source_dir") or "").strip()
    if copied_abis:
        print(f"[android-archive] copied 7zz for abi={copied_abis} from {source_dir_text}")
    elif source_dir_text:
        print(f"[android-archive] no 7zz copied; missing abi={missing_abis} under {source_dir_text}")

    py_bootstrap = py_dir / "ultimate_android_backend.py"
    bootstrap_build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    py_source = """import json
import os
import sys
import platform
import shutil
import threading
import subprocess
import importlib
import importlib.util
from datetime import datetime


_started = False
_lock = threading.Lock()
BOOTSTRAP_BUILD_ID = "__BOOTSTRAP_BUILD_ID__"
EMBEDDED_PROTOCOL_SNAPSHOT_JSON = __EMBEDDED_SNAPSHOT_JSON__


def _write_boot_log(files_dir, message):
    try:
        target_dir = str(files_dir or "").strip() or "."
        os.makedirs(target_dir, exist_ok=True)
        log_path = os.path.join(target_dir, "ultimate_backend_boot.log")
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(f"{datetime.utcnow().isoformat()}Z {message}\\n")
    except Exception:
        pass


def _extract_snapshot_templates(raw_values):
    templates = []
    for item in (raw_values or []):
        if isinstance(item, dict):
            value = str(item.get("path") or "").strip()
        else:
            value = str(item or "").strip()
        if value:
            templates.append(value)
    return templates


def _discover_snapshot_candidates(module_dir, snapshot_filename):
    matches = []
    try:
        for root, _dirs, files in os.walk(module_dir):
            if snapshot_filename in files:
                matches.append(os.path.join(root, snapshot_filename))
                if len(matches) >= 10:
                    break
    except Exception:
        pass
    return matches


def _load_embedded_protocol_snapshot_payload():
    try:
        raw = str(EMBEDDED_PROTOCOL_SNAPSHOT_JSON or "").strip()
        if not raw:
            return {}
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _materialize_protocol_snapshot(files_dir, internal_exec_dir=""):
    try:
        payload = _load_embedded_protocol_snapshot_payload()
        manifests = payload.get("manifests") or payload.get("plugins") or []
        target_root = (
            str(internal_exec_dir or "").strip()
            or str(files_dir or "").strip()
            or os.path.abspath(os.path.dirname(__file__))
        )
        protocol_dir = os.path.join(target_root, "protocol_runtime")
        os.makedirs(protocol_dir, exist_ok=True)
        snapshot_path = os.path.join(protocol_dir, "__SNAPSHOT_FILENAME__")
        serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\\n"
        should_write = True
        if os.path.isfile(snapshot_path):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as existing_fp:
                    should_write = existing_fp.read() != serialized
            except Exception:
                should_write = True
        if should_write:
            with open(snapshot_path, "w", encoding="utf-8") as fp:
                fp.write(serialized)
        _write_boot_log(
            files_dir,
            f"protocol snapshot materialized path={snapshot_path!r} manifest_count={len(manifests)} "
            f"target_root={target_root!r}",
        )
        return snapshot_path
    except Exception as ex:
        _write_boot_log(files_dir, f"protocol snapshot materialize failed: {ex!r}")
        return ""


def _log_protocol_snapshot_summary(files_dir, snapshot_path):
    try:
        if not snapshot_path or not os.path.isfile(snapshot_path):
            module_dir = os.path.abspath(os.path.dirname(__file__))
            protocol_dir = os.path.join(module_dir, "protocol")
            protocol_entries = []
            if os.path.isdir(protocol_dir):
                try:
                    protocol_entries = sorted(os.listdir(protocol_dir))[:40]
                except Exception as list_ex:
                    protocol_entries = [f"<list_failed:{list_ex!r}>"]
            discovered = _discover_snapshot_candidates(module_dir, "__SNAPSHOT_FILENAME__")
            _write_boot_log(
                files_dir,
                f"protocol snapshot missing path={snapshot_path!r} "
                f"module_dir={module_dir!r} protocol_dir_exists={os.path.isdir(protocol_dir)!r} "
                f"protocol_entries={protocol_entries!r} discovered={discovered!r} "
                f"embedded_snapshot_present={bool(str(EMBEDDED_PROTOCOL_SNAPSHOT_JSON or '').strip())!r}",
            )
            return

        with open(snapshot_path, "r", encoding="utf-8") as fp:
            payload = json.load(fp)

        manifests = payload.get("manifests") or payload.get("plugins") or []
        plugin_ids = []
        _write_boot_log(
            files_dir,
            f"protocol snapshot found path={snapshot_path!r} manifest_count={len(manifests)}",
        )
        for item in manifests:
            plugin = dict(item.get("plugin") or {})
            identity = dict(item.get("identity") or {})
            storage = dict(item.get("storage") or {})
            comic_dir = dict(storage.get("comic_dir") or {})
            host_resolution = dict(storage.get("host_resolution") or {})
            plugin_id = str(plugin.get("id") or "").strip()
            if plugin_id:
                plugin_ids.append(plugin_id)
            _write_boot_log(
                files_dir,
                "protocol snapshot manifest "
                + (
                    f"plugin_id={plugin_id!r} "
                    f"host_prefix={str(identity.get('host_id_prefix') or '').strip()!r} "
                    f"media_types={item.get('media_types')!r} "
                    f"comic_dir_template={str(comic_dir.get('template') or '').strip()!r} "
                    f"comic_dir_fallbacks={_extract_snapshot_templates(comic_dir.get('fallback_templates') or [])!r} "
                    f"host_resolution_keys={list(host_resolution.keys())!r}"
                ),
            )
        _write_boot_log(files_dir, f"protocol snapshot plugin_ids={plugin_ids!r}")
    except Exception as ex:
        _write_boot_log(files_dir, f"protocol snapshot inspect failed: {ex!r}")


def _detect_android_abi():
    machine = str(platform.machine() or "").strip().lower()
    mapping = {
        "aarch64": "arm64-v8a",
        "arm64": "arm64-v8a",
        "x86_64": "x86_64",
        "amd64": "x86_64",
    }
    return mapping.get(machine, "")


def _validate_archive_tool(tool_path, files_dir):
    try:
        stat_info = os.stat(str(tool_path))
        _write_boot_log(
            files_dir,
            f"android archive runtime probe start path={tool_path!r} mode={oct(stat_info.st_mode)} size={stat_info.st_size}",
        )
        proc = subprocess.run(
            [str(tool_path), "i"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        if int(proc.returncode) in (0, 1, 2):
            return True
        _write_boot_log(files_dir, f"android archive runtime probe returned code={proc.returncode}")
        return False
    except PermissionError as ex:
        _write_boot_log(files_dir, f"android archive runtime probe permission denied: {ex!r}")
        return False
    except Exception as ex:
        _write_boot_log(files_dir, f"android archive runtime probe failed: {ex!r}")
        return False


def _prepare_android_archive_runtime(files_dir, internal_exec_dir=None):
    try:
        module_dir = os.path.abspath(os.path.dirname(__file__))
        abi = _detect_android_abi()
        if not abi:
            _write_boot_log(files_dir, f"android archive runtime skipped: unknown abi machine={platform.machine()!r}")
            return ""
        source_tool = os.path.join(module_dir, "_android_tools", "archive", abi, "7zz")
        if not os.path.isfile(source_tool):
            _write_boot_log(files_dir, f"android archive runtime skipped: missing source tool abi={abi} path={source_tool!r}")
            return ""
        exec_base = str(internal_exec_dir or "").strip() or str(files_dir or "").strip() or "."
        target_root = os.path.join(exec_base, "tools", "archive")
        os.makedirs(target_root, exist_ok=True)
        target_tool = os.path.join(target_root, "7zz")
        if (not os.path.exists(target_tool)) or (os.path.getsize(target_tool) != os.path.getsize(source_tool)):
            shutil.copy2(source_tool, target_tool)
        try:
            os.chmod(target_tool, 0o755)
        except Exception:
            pass
        skip_probe = str(os.environ.get("ULTIMATE_ANDROID_ARCHIVE_SKIP_PROBE", "1")).strip().lower()
        if skip_probe not in {"0", "false", "no", "off"}:
            _write_boot_log(files_dir, "android archive runtime probe skipped by config")
            return target_tool
        if not _validate_archive_tool(target_tool, files_dir):
            return ""
        return target_tool
    except Exception as ex:
        _write_boot_log(files_dir, f"android archive runtime prepare failed: {ex!r}")
        return ""


def start_backend(files_dir, host="127.0.0.1", port=5000, third_party_enabled="false", internal_exec_dir=""):
    global _started
    _write_boot_log(files_dir, f"bootstrap build_id={BOOTSTRAP_BUILD_ID}")
    with _lock:
        if _started:
            return "already_started"
        _started = True

    os.environ["BACKEND_RUNTIME_PROFILE"] = "android"
    os.environ["ANDROID_APP_FILES_DIR"] = str(files_dir or "")
    os.environ["BACKEND_HOST"] = str(host or "127.0.0.1")
    os.environ["BACKEND_PORT"] = str(int(port or 5000))
    os.environ["BACKEND_DEBUG"] = "false"
    os.environ["BACKEND_ENABLE_THIRD_PARTY"] = str(third_party_enabled or "false").lower()
    os.environ["ULTIMATE_APP_VERSION"] = "__APP_VERSION__"
    snapshot_path = _materialize_protocol_snapshot(files_dir, internal_exec_dir=internal_exec_dir)
    if os.path.isfile(snapshot_path):
        os.environ["BACKEND_PROTOCOL_SNAPSHOT_PATH"] = snapshot_path
    _log_protocol_snapshot_summary(files_dir, snapshot_path)
    archive_tool = _prepare_android_archive_runtime(files_dir, internal_exec_dir=internal_exec_dir)
    if archive_tool:
        os.environ["RAR_BACKEND_MODE"] = "7z"
        os.environ["RAR_7Z_PATH"] = archive_tool
        os.environ["RAR_7ZZ_PATH"] = archive_tool
        _write_boot_log(files_dir, f"android archive runtime enabled tool={archive_tool!r}")
    else:
        _write_boot_log(files_dir, "android archive runtime unavailable; RAR parsing may be limited")
    _write_boot_log(files_dir, f"start requested host={host} port={port}")

    try:
        module_dir = os.path.abspath(os.path.dirname(__file__))
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)
        backend_app = importlib.import_module("app")
        _write_boot_log(files_dir, f"import app success file={getattr(backend_app, '__file__', None)!r}")
        if not hasattr(backend_app, "run_backend_server"):
            app_py = os.path.join(module_dir, "app.py")
            if os.path.isfile(app_py):
                spec = importlib.util.spec_from_file_location("ultimate_backend_app_local", app_py)
                if spec and spec.loader:
                    local_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(local_mod)
                    backend_app = local_mod
                    _write_boot_log(files_dir, f"fallback local app.py loaded file={app_py!r}")
        if not hasattr(backend_app, "run_backend_server"):
            raise AttributeError("module 'app' has no attribute 'run_backend_server'")
    except Exception as ex:
        _write_boot_log(files_dir, f"import app failed: {ex!r}")
        raise

    try:
        backend_app.run_backend_server(host="0.0.0.0", port=int(port or 5000), debug=False)
    except Exception as ex:
        _write_boot_log(files_dir, f"backend run failed: {ex!r}")
        raise

    _write_boot_log(files_dir, "backend started")
    return "started"
"""
    py_source = py_source.replace("__BOOTSTRAP_BUILD_ID__", bootstrap_build_id)
    py_source = py_source.replace("__APP_VERSION__", normalize_app_version(app_version) or DEFAULT_APP_VERSION)
    py_source = py_source.replace("__SNAPSHOT_FILENAME__", MOBILE_PROTOCOL_SNAPSHOT_FILENAME)
    py_source = py_source.replace("__EMBEDDED_SNAPSHOT_JSON__", repr(embedded_snapshot_json))
    write_text(py_bootstrap, py_source)

    marker_path = workspace_dir / workspace_web_dir / "backend_bootstrap.json"
    if marker_path.exists():
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        payload["chaquopy_injected"] = True
        payload["android_main_activity"] = str(java_path)
        write_text(marker_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def inject_android_embedded_backend(
    workspace_dir: Path,
    packager_cfg: Dict,
    app_version: str,
) -> None:
    android_project_dir = workspace_dir / "android"
    if not android_project_dir.exists():
        raise FileNotFoundError(f"android project dir not found: {android_project_dir}")
    min_sdk = int(packager_cfg.get("chaquopy_min_sdk", 24))
    chaquopy_version = str(packager_cfg.get("chaquopy_version", "17.0.0")).strip() or "17.0.0"
    patch_android_min_sdk(android_project_dir, min_sdk)
    ensure_android_project_chaquopy_root(android_project_dir, chaquopy_version)
    ensure_android_manifest_network(android_project_dir)
    ensure_android_project_chaquopy_app(android_project_dir, workspace_dir, packager_cfg, app_version)


def resolve_android_java_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        java_bin = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if java_bin.exists():
            env["JAVA_HOME"] = str(Path(java_home))

    if not env and os.name == "nt":
        candidates = [
            r"C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot",
            r"C:\Program Files\Eclipse Adoptium\jdk-21",
            r"C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot",
            r"C:\Program Files\Eclipse Adoptium\jdk-17",
            r"C:\Program Files\Microsoft\jdk-21",
            r"C:\Program Files\Microsoft\jdk-17",
        ]
        for item in candidates:
            java_bin = Path(item) / "bin" / "java.exe"
            if java_bin.exists():
                env["JAVA_HOME"] = item
                break

    if not env:
        java_cmd = shutil.which("java")
        if java_cmd:
            java_path = Path(java_cmd).resolve()
            java_home_guess = java_path.parent.parent
            env["JAVA_HOME"] = str(java_home_guess)

    if "JAVA_HOME" in env:
        java_bin_dir = str(Path(env["JAVA_HOME"]) / "bin")
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if java_bin_dir not in path_parts:
            env["PATH"] = java_bin_dir + os.pathsep + os.environ.get("PATH", "")
    return env


def current_host_target() -> str:
    if os.name == "nt":
        return "windows"
    return "linux"


def is_desktop_target(target: str) -> bool:
    return target in {"windows", "linux"}


def _collect_ffmpeg_toolset(primary_binary: Path, target: str) -> Dict[str, Path]:
    binary_name = "ffmpeg.exe" if target == "windows" else "ffmpeg"
    ffprobe_name = "ffprobe.exe" if target == "windows" else "ffprobe"
    tools: Dict[str, Path] = {}

    try:
        resolved_primary = primary_binary.resolve()
    except Exception:
        resolved_primary = primary_binary

    if resolved_primary.exists() and resolved_primary.is_file():
        tools[binary_name] = resolved_primary

    ffprobe_candidate = resolved_primary.with_name(ffprobe_name)
    if ffprobe_candidate.exists() and ffprobe_candidate.is_file():
        try:
            tools[ffprobe_name] = ffprobe_candidate.resolve()
        except Exception:
            tools[ffprobe_name] = ffprobe_candidate
    return tools


def discover_ffmpeg_runtime_tools(target: str) -> Dict[str, Path]:
    if not is_desktop_target(target):
        return {}

    binary_name = "ffmpeg.exe" if target == "windows" else "ffmpeg"
    candidates: List[Path] = []

    for env_key in ("ULTIMATE_FFMPEG_PATH", "FFMPEG_PATH"):
        env_value = str(os.environ.get(env_key, "")).strip()
        if not env_value:
            continue
        candidate = Path(env_value).expanduser()
        if candidate.is_dir():
            candidate = candidate / binary_name
        candidates.append(candidate)

    candidates.extend(
        [
            ROOT_DIR / "tools" / "ffmpeg" / target / binary_name,
            ROOT_DIR / "build" / "runtime_tools" / "ffmpeg" / target / binary_name,
            ROOT_DIR / "runtime_tools" / "ffmpeg" / target / binary_name,
        ]
    )

    resolved_from_path = shutil.which("ffmpeg")
    if resolved_from_path:
        candidates.append(Path(resolved_from_path))

    for candidate in candidates:
        try:
            normalized = candidate.resolve()
        except Exception:
            normalized = candidate
        if normalized.exists() and normalized.is_file():
            return _collect_ffmpeg_toolset(normalized, target)
    return {}


def provision_windows_ffmpeg_runtime_tools() -> Dict[str, Path]:
    target = "windows"
    binary_name = "ffmpeg.exe"
    output_dir = ROOT_DIR / "build" / "runtime_tools" / "ffmpeg" / target
    existing_binary = output_dir / binary_name
    if existing_binary.exists():
        return _collect_ffmpeg_toolset(existing_binary, target)

    download_url = str(
        os.environ.get("ULTIMATE_WINDOWS_FFMPEG_DOWNLOAD_URL")
        or os.environ.get("ULTIMATE_FFMPEG_DOWNLOAD_URL")
        or DEFAULT_WINDOWS_FFMPEG_DOWNLOAD_URL
    ).strip()
    if not download_url:
        return {}

    print(f"[ffmpeg] provisioning windows runtime from {download_url}")
    with tempfile.TemporaryDirectory(prefix="ultimate-ffmpeg-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        archive_path = temp_dir / "ffmpeg-runtime.zip"
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        urllib.request.urlretrieve(download_url, archive_path)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_dir)

        ffmpeg_source = next(extract_dir.rglob(binary_name), None)
        if ffmpeg_source is None or not ffmpeg_source.exists():
            raise RuntimeError(f"downloaded ffmpeg archive did not contain {binary_name}")

        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ffmpeg_source, existing_binary)

        ffprobe_source = next(extract_dir.rglob("ffprobe.exe"), None)
        if ffprobe_source is not None and ffprobe_source.exists():
            shutil.copy2(ffprobe_source, output_dir / "ffprobe.exe")

    return _collect_ffmpeg_toolset(existing_binary, target)


def discover_archive_runtime_tools(target: str) -> Dict[str, Path]:
    tools: Dict[str, Path] = {}

    def _resolve(executable: str, windows_candidates: Optional[List[str]] = None) -> Optional[Path]:
        resolved = shutil.which(executable)
        if not resolved:
            if os.name == "nt":
                for raw in windows_candidates or []:
                    candidate = Path(raw)
                    if candidate.exists():
                        resolved = str(candidate)
                        break
            if not resolved:
                return None
        try:
            return Path(resolved).resolve()
        except Exception:
            return Path(resolved)

    if target == "windows":
        sevenzip = _resolve(
            "7z",
            windows_candidates=[
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files (x86)\7-Zip\7z.exe",
            ],
        ) or _resolve("7z.exe")
        if sevenzip:
            tools["7z.exe"] = sevenzip
            dll = sevenzip.parent / "7z.dll"
            if dll.exists():
                tools["7z.dll"] = dll.resolve()
        return tools

    if target == "linux":
        for name in ("unrar", "7z", "7zz", "bsdtar"):
            resolved = _resolve(name)
            if resolved:
                tools[name] = resolved
    return tools


def copy_archive_runtime_tools(target: str, bundle_dir: Path) -> Optional[Path]:
    if not is_desktop_target(target):
        return None

    tools = discover_archive_runtime_tools(target)
    if not tools:
        return None

    out_dir = bundle_dir / "tools" / "archive"
    out_dir.mkdir(parents=True, exist_ok=True)
    for output_name, source_path in tools.items():
        destination = out_dir / output_name
        shutil.copy2(source_path, destination)
        if target != "windows":
            try:
                destination.chmod(0o755)
            except OSError:
                pass
    return out_dir


def copy_ffmpeg_runtime_tools(target: str, bundle_dir: Path) -> Optional[Path]:
    if not is_desktop_target(target):
        return None

    tools = discover_ffmpeg_runtime_tools(target)
    if not tools and target == "windows":
        tools = provision_windows_ffmpeg_runtime_tools()
    if not tools:
        return None

    out_dir = bundle_dir / "tools" / "ffmpeg"
    out_dir.mkdir(parents=True, exist_ok=True)
    for output_name, source_path in tools.items():
        destination = out_dir / output_name
        shutil.copy2(source_path, destination)
        if target != "windows":
            try:
                destination.chmod(0o755)
            except OSError:
                pass
    return out_dir


def write_desktop_bundle_scripts(
    bundle_dir: Path,
    binary_name: str,
    runtime_env: Dict[str, str],
) -> None:
    runtime_profile = runtime_env.get("BACKEND_RUNTIME_PROFILE", "full")
    third_party_enabled = runtime_env.get("BACKEND_ENABLE_THIRD_PARTY", "true")

    bat = (
        "@echo off\n"
        "setlocal\n"
        f"set BACKEND_RUNTIME_PROFILE={runtime_profile}\n"
        f"set BACKEND_ENABLE_THIRD_PARTY={third_party_enabled}\n"
        "set SCRIPT_DIR=%~dp0\n"
        "set ULTIMATE_PLUGIN_ROOTS=%SCRIPT_DIR%plugins\n"
        "set ARCHIVE_TOOLS_DIR=%SCRIPT_DIR%tools\\archive\n"
        "if exist \"%ARCHIVE_TOOLS_DIR%\" set PATH=%ARCHIVE_TOOLS_DIR%;%PATH%\n"
        "set FFMPEG_TOOLS_DIR=%SCRIPT_DIR%tools\\ffmpeg\n"
        "if exist \"%FFMPEG_TOOLS_DIR%\" set PATH=%FFMPEG_TOOLS_DIR%;%PATH%\n"
        "set BACKEND_DEBUG=false\n"
        "set FRONTEND_DIST_DIR=%SCRIPT_DIR%frontend_dist\n"
        "cd /d \"%SCRIPT_DIR%\"\n"
        f"if exist \"%SCRIPT_DIR%bin\\{binary_name}.exe\" (\n"
        f"  \"%SCRIPT_DIR%bin\\{binary_name}.exe\"\n"
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        "cd /d \"%SCRIPT_DIR%backend_source\"\n"
        "python app.py\n"
    )
    write_text(bundle_dir / "start_backend.bat", bat)

    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        f"$env:BACKEND_RUNTIME_PROFILE = \"{runtime_profile}\"\n"
        f"$env:BACKEND_ENABLE_THIRD_PARTY = \"{third_party_enabled}\"\n"
        "$env:ULTIMATE_PLUGIN_ROOTS = Join-Path $scriptDir \"plugins\"\n"
        "$archiveTools = Join-Path $scriptDir \"tools/archive\"\n"
        "if (Test-Path $archiveTools) {\n"
        "    $env:PATH = \"$archiveTools;$env:PATH\"\n"
        "}\n"
        "$ffmpegTools = Join-Path $scriptDir \"tools/ffmpeg\"\n"
        "if (Test-Path $ffmpegTools) {\n"
        "    $env:PATH = \"$ffmpegTools;$env:PATH\"\n"
        "}\n"
        "$env:BACKEND_DEBUG = \"false\"\n"
        "$env:FRONTEND_DIST_DIR = Join-Path $scriptDir \"frontend_dist\"\n"
        "Set-Location $scriptDir\n"
        f"$exePath = Join-Path $scriptDir \"bin/{binary_name}.exe\"\n"
        "if (Test-Path $exePath) {\n"
        "    & $exePath\n"
        "    exit $LASTEXITCODE\n"
        "}\n"
        "$backendSource = Join-Path $scriptDir \"backend_source\"\n"
        "Set-Location $backendSource\n"
        "python app.py\n"
    )
    write_text(bundle_dir / "start_backend.ps1", ps1)

    sh = (
        "#!/usr/bin/env sh\n"
        "set -e\n"
        f"export BACKEND_RUNTIME_PROFILE=\"{runtime_profile}\"\n"
        f"export BACKEND_ENABLE_THIRD_PARTY=\"{third_party_enabled}\"\n"
        "SCRIPT_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        "export ULTIMATE_PLUGIN_ROOTS=\"$SCRIPT_DIR/plugins\"\n"
        "ARCHIVE_TOOLS_DIR=\"$SCRIPT_DIR/tools/archive\"\n"
        "if [ -d \"$ARCHIVE_TOOLS_DIR\" ]; then\n"
        "  export PATH=\"$ARCHIVE_TOOLS_DIR:$PATH\"\n"
        "fi\n"
        "FFMPEG_TOOLS_DIR=\"$SCRIPT_DIR/tools/ffmpeg\"\n"
        "if [ -d \"$FFMPEG_TOOLS_DIR\" ]; then\n"
        "  export PATH=\"$FFMPEG_TOOLS_DIR:$PATH\"\n"
        "fi\n"
        "export BACKEND_DEBUG=\"false\"\n"
        "export FRONTEND_DIST_DIR=\"$SCRIPT_DIR/frontend_dist\"\n"
        "cd \"$SCRIPT_DIR\"\n"
        f"if [ -x \"$SCRIPT_DIR/bin/{binary_name}\" ]; then\n"
        f"  exec \"$SCRIPT_DIR/bin/{binary_name}\"\n"
        "fi\n"
        "cd \"$SCRIPT_DIR/backend_source\"\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "  exec python3 app.py\n"
        "fi\n"
        "exec python app.py\n"
    )
    sh_path = bundle_dir / "start_backend.sh"
    write_text(sh_path, sh)
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass

    app_bat = (
        "@echo off\n"
        "set SCRIPT_DIR=%~dp0\n"
        "set APP_PORT=5000\n"
        "for /f \"usebackq delims=\" %%I in (`powershell -NoProfile -Command \"$p=5000; $defaultCfgDir = Join-Path $env:APPDATA 'ULTIMATE_WEB'; $cfgDir = $defaultCfgDir; $envCfgDir = [string]$env:ULTIMATE_CONFIG_DIR; if (-not [string]::IsNullOrWhiteSpace($envCfgDir)) { $cfgDir = [Environment]::ExpandEnvironmentVariables($envCfgDir) } else { $overridePath = Join-Path $defaultCfgDir 'config_dir.override.json'; if (Test-Path -LiteralPath $overridePath) { try { $ov = Get-Content -LiteralPath $overridePath -Raw ^| ConvertFrom-Json; $persisted = [string]$ov.config_dir; if (-not [string]::IsNullOrWhiteSpace($persisted)) { $cfgDir = [Environment]::ExpandEnvironmentVariables($persisted) } } catch {} } }; $cfgPath = Join-Path $cfgDir 'server_config.json'; if (Test-Path -LiteralPath $cfgPath) { try { $cfg = Get-Content -LiteralPath $cfgPath -Raw ^| ConvertFrom-Json; if ($cfg.backend.port -ne $null) { $p = [int]$cfg.backend.port } } catch {} }; Write-Output $p\"`) do set APP_PORT=%%I\n"
        "start \"\" \"%SCRIPT_DIR%start_backend.bat\"\n"
        "timeout /t 2 >nul\n"
        "start \"\" \"http://127.0.0.1:%APP_PORT%/\"\n"
    )
    write_text(bundle_dir / "start_app.bat", app_bat)

    app_ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "$appPort = 5000\n"
        "$defaultCfgDir = Join-Path $env:APPDATA 'ULTIMATE_WEB'\n"
        "$cfgDir = $defaultCfgDir\n"
        "$envCfgDir = [string]$env:ULTIMATE_CONFIG_DIR\n"
        "if (-not [string]::IsNullOrWhiteSpace($envCfgDir)) {\n"
        "    $cfgDir = [Environment]::ExpandEnvironmentVariables($envCfgDir)\n"
        "} else {\n"
        "    $overridePath = Join-Path $defaultCfgDir 'config_dir.override.json'\n"
        "    if (Test-Path -LiteralPath $overridePath) {\n"
        "        try {\n"
        "            $ov = Get-Content -LiteralPath $overridePath -Raw | ConvertFrom-Json\n"
        "            $persisted = [string]$ov.config_dir\n"
        "            if (-not [string]::IsNullOrWhiteSpace($persisted)) {\n"
        "                $cfgDir = [Environment]::ExpandEnvironmentVariables($persisted)\n"
        "            }\n"
        "        } catch {\n"
        "        }\n"
        "    }\n"
        "}\n"
        "$configPath = Join-Path $cfgDir 'server_config.json'\n"
        "if (Test-Path -LiteralPath $configPath) {\n"
        "    try {\n"
        "        $cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json\n"
        "        if ($null -ne $cfg.backend.port) {\n"
        "            $appPort = [int]$cfg.backend.port\n"
        "        }\n"
        "    } catch {\n"
        "    }\n"
        "}\n"
        "Start-Process -FilePath (Join-Path $scriptDir 'start_backend.ps1') -NoNewWindow\n"
        "Start-Sleep -Seconds 2\n"
        "Start-Process (\"http://127.0.0.1:{0}/\" -f $appPort)\n"
    )
    write_text(bundle_dir / "start_app.ps1", app_ps1)


def prepare_desktop_release_bundle(
    target: str,
    target_out_dir: Path,
    staged_target_dir: Path,
    binary_name: str,
    runtime_env: Dict[str, str],
    plugin_package_mode: str = DEFAULT_PLUGIN_PACKAGE_MODE,
) -> Path:
    plugin_mode = normalize_plugin_package_mode(plugin_package_mode)
    bundle_dir = target_out_dir / "release_bundle"
    ensure_clean_dir(bundle_dir)

    backend_src = staged_target_dir / "comic_backend"
    frontend_dist = staged_target_dir / "comic_frontend_dist"

    if backend_src.exists():
        shutil.copytree(backend_src, bundle_dir / "backend_source")
    if frontend_dist.exists():
        frontend_target = bundle_dir / "frontend_dist"
        if frontend_target.exists():
            shutil.rmtree(frontend_target)
        shutil.copytree(frontend_dist, frontend_target)

    runtime_env_src = staged_target_dir / "runtime.env"
    if runtime_env_src.exists():
        shutil.copy2(runtime_env_src, bundle_dir / "runtime.env")

    server_config_src = staged_target_dir / "server_config.json"
    if server_config_src.exists():
        shutil.copy2(server_config_src, bundle_dir / "server_config.json")

    manifest_src = staged_target_dir / "package_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, bundle_dir / "stage_manifest.json")

    if plugin_mode == PLUGIN_PACKAGE_MODE_EXTERNAL:
        external_plugin_roots = copy_external_plugins_to_bundle(backend_src, bundle_dir) if backend_src.exists() else []
    else:
        plugins_dir = bundle_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            plugins_dir / "README.md",
            "Drop additional protocol plugin directories here. Built-in release plugins are bundled in the executable.\n",
        )
        external_plugin_roots = []
    write_external_plugin_dependency_scripts(bundle_dir, external_plugin_roots)

    archive_tools_dir = copy_archive_runtime_tools(target, bundle_dir)
    ffmpeg_tools_dir = copy_ffmpeg_runtime_tools(target, bundle_dir)

    notes = [
        "# Desktop Release Bundle",
        "",
        f"- target: `{target}`",
        "- `backend_source/`: fallback Python source runtime",
        "- `frontend_dist/`: frontend static assets",
        f"- plugin package mode: `{plugin_mode}`",
        "- `plugins/`: external hot-pluggable protocol plugins",
        "- `bin/`: packaged backend executable (if packaging executed successfully)",
    ]
    if plugin_mode == PLUGIN_PACKAGE_MODE_BUNDLED:
        notes.append("- default repository plugins are bundled into the executable; `plugins/` is reserved for extra plugins")
    else:
        notes.append("- default repository plugins are placed under `plugins/` and loaded dynamically at runtime")
    if archive_tools_dir is not None:
        notes.append("- `tools/archive/`: bundled archive runtime binaries for RAR/7z support")
    if ffmpeg_tools_dir is not None:
        notes.append("- `tools/ffmpeg/`: bundled ffmpeg runtime for local video thumbnail generation")
    notes.extend(
        [
            "",
            "Start commands:",
            "- Windows cmd: `start_backend.bat`",
            "- Windows PowerShell: `start_backend.ps1`",
            "- Linux/macOS: `start_backend.sh`",
            "- Install external plugin deps manually if needed: `install_plugin_deps.ps1` / `install_plugin_deps.sh`",
        ]
    )
    write_text(bundle_dir / "README.md", "\n".join(notes) + "\n")

    (bundle_dir / "bin").mkdir(parents=True, exist_ok=True)
    write_desktop_bundle_scripts(bundle_dir, binary_name=binary_name, runtime_env=runtime_env)
    return bundle_dir


def _normalize_string_list(values: object) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _deep_merge_dict(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: json.loads(json.dumps(value)) for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _deep_merge_dict(merged.get(key), value)
        return merged
    if override is None:
        return json.loads(json.dumps(base))
    return json.loads(json.dumps(override))


def discover_packaged_plugin_roots(third_party_root: Path) -> List[Path]:
    if not third_party_root.exists():
        return []

    roots: List[Path] = []
    for child in sorted(third_party_root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        if any(path.name == "ultimate-plugin.json" for path in child.rglob("ultimate-plugin.json")):
            roots.append(child)
    return roots


def current_plugin_platform_tag() -> str:
    system_name = str(platform.system() or "").strip().lower() or sys.platform.lower()
    machine = str(platform.machine() or "").strip().lower() or "unknown"
    return f"{system_name}-{machine}"


def current_plugin_python_tag() -> str:
    return f"py{sys.version_info.major}{sys.version_info.minor}"


def get_external_plugin_vendor_relative_dir() -> Path:
    return Path("vendor") / "python" / current_plugin_python_tag() / current_plugin_platform_tag()


def get_external_plugin_dependency_state_filename() -> str:
    return ".ultimate_vendor_state.json"


def get_external_plugin_dependency_state_path(plugin_root: Path) -> Path:
    return plugin_root / get_external_plugin_dependency_state_filename()


def _collect_external_plugin_requirements(payload: Dict[str, Any]) -> List[str]:
    packaging = dict(payload.get("packaging") or {})
    external = dict(packaging.get("external") or {})
    if external.get("pip_requirements"):
        return _normalize_string_list(external.get("pip_requirements") or [])
    pyinstaller = dict(packaging.get("pyinstaller") or {})
    return _normalize_string_list(pyinstaller.get("pip_requirements") or [])


def collect_external_plugin_metadata(plugin_root: Path) -> Dict[str, Any]:
    requirements: List[str] = []
    for manifest_path in sorted(plugin_root.rglob("ultimate-plugin.json")):
        payload = load_json(manifest_path)
        requirements.extend(_collect_external_plugin_requirements(payload))
    vendor_relative_dir = str(get_external_plugin_vendor_relative_dir()).replace("\\", "/")
    return {
        "root": str(plugin_root),
        "requirements": _normalize_string_list(requirements),
        "vendor_relative_dir": vendor_relative_dir,
        "python_tag": current_plugin_python_tag(),
        "state_filename": get_external_plugin_dependency_state_filename(),
        "state_payload": {
            "requirements": _normalize_string_list(requirements),
            "vendor_relative_dir": vendor_relative_dir,
            "python_tag": current_plugin_python_tag(),
        },
    }


def copy_external_plugins_to_bundle(staged_backend: Path, bundle_dir: Path) -> List[Path]:
    third_party_root = staged_backend / "third_party"
    plugin_roots = discover_packaged_plugin_roots(third_party_root)
    if not plugin_roots:
        return []

    plugins_dir = bundle_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    copied_roots: List[Path] = []
    for plugin_root in plugin_roots:
        target_root = plugins_dir / plugin_root.name
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(plugin_root, target_root)
        copied_roots.append(target_root)

        backend_plugin_root = bundle_dir / "backend_source" / "third_party" / plugin_root.name
        if backend_plugin_root.exists():
            shutil.rmtree(backend_plugin_root, ignore_errors=True)

    return copied_roots


def _serialize_external_plugin_dependency_state(metadata: Dict[str, Any]) -> str:
    payload = dict(metadata.get("state_payload") or {})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _external_plugin_dependency_install_is_current(plugin_root: Path, metadata: Dict[str, Any]) -> bool:
    vendor_relative_dir = str(metadata.get("vendor_relative_dir") or "").strip()
    if not vendor_relative_dir:
        return False
    vendor_target = plugin_root / Path(vendor_relative_dir)
    state_path = get_external_plugin_dependency_state_path(plugin_root)
    if not vendor_target.exists() or not state_path.exists():
        return False
    try:
        if not any(vendor_target.iterdir()):
            return False
    except OSError:
        return False
    try:
        actual = state_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return actual == _serialize_external_plugin_dependency_state(metadata)


def _write_external_plugin_dependency_state(plugin_root: Path, metadata: Dict[str, Any]) -> None:
    write_text(
        get_external_plugin_dependency_state_path(plugin_root),
        _serialize_external_plugin_dependency_state(metadata) + "\n",
    )


def _quote_powershell_single(text: str) -> str:
    return "'" + str(text or "").replace("'", "''") + "'"


def write_external_plugin_dependency_scripts(bundle_dir: Path, plugin_roots: List[Path]) -> List[List[str]]:
    commands: List[List[str]] = []
    script_specs: List[Dict[str, str]] = []
    for plugin_root in plugin_roots:
        metadata = collect_external_plugin_metadata(plugin_root)
        requirements = list(metadata.get("requirements") or [])
        if not requirements:
            continue
        vendor_target = plugin_root / get_external_plugin_vendor_relative_dir()
        vendor_target.mkdir(parents=True, exist_ok=True)
        relative_vendor_target = vendor_target.relative_to(bundle_dir).as_posix()
        state_path = get_external_plugin_dependency_state_path(plugin_root)
        relative_state_path = state_path.relative_to(bundle_dir).as_posix()
        commands.append(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(vendor_target),
                *requirements,
            ]
        )
        script_specs.append(
            {
                "plugin_name": plugin_root.name,
                "relative_vendor_target": relative_vendor_target,
                "relative_state_path": relative_state_path,
                "requirements": " ".join(requirements),
                "requirements_ps": " ".join(_quote_powershell_single(item) for item in requirements),
                "requirements_shell": " ".join(shlex.quote(item) for item in requirements),
                "expected_state": _serialize_external_plugin_dependency_state(metadata),
            }
        )

    ps1_lines = [
        "$ErrorActionPreference = 'Stop'",
        "$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path",
        "$pythonCmd = Get-Command python -ErrorAction SilentlyContinue",
        "if (-not $pythonCmd) { throw 'python command not found' }",
        f"$expectedPyTag = {_quote_powershell_single(current_plugin_python_tag())}",
        "$actualPyTag = (& $pythonCmd.Source -c \"import sys; print(f'py{sys.version_info.major}{sys.version_info.minor}')\").Trim()",
        "if ($LASTEXITCODE -ne 0) { throw 'failed to probe python version' }",
        "if ($actualPyTag -ne $expectedPyTag) { throw \"python version mismatch: expected $expectedPyTag, got $actualPyTag\" }",
    ]
    sh_lines = [
        "#!/usr/bin/env sh",
        "set -e",
        "SCRIPT_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"",
        "if command -v python3 >/dev/null 2>&1; then PYTHON_CMD=python3; else PYTHON_CMD=python; fi",
        f"EXPECTED_PY_TAG={shlex.quote(current_plugin_python_tag())}",
        "ACTUAL_PY_TAG=\"$($PYTHON_CMD -c 'import sys; print(f\"py{sys.version_info.major}{sys.version_info.minor}\")')\"",
        "if [ \"$ACTUAL_PY_TAG\" != \"$EXPECTED_PY_TAG\" ]; then",
        "  echo \"python version mismatch: expected $EXPECTED_PY_TAG, got $ACTUAL_PY_TAG\" >&2",
        "  exit 1",
        "fi",
    ]
    for spec in script_specs:
        expected_state_ps = _quote_powershell_single(spec["expected_state"])
        ps1_lines.append(
            f"$vendorPath = Join-Path $scriptDir {_quote_powershell_single(spec['relative_vendor_target'].replace('/', '\\'))}"
        )
        ps1_lines.append(
            f"$statePath = Join-Path $scriptDir {_quote_powershell_single(spec['relative_state_path'].replace('/', '\\'))}"
        )
        ps1_lines.append(f"$expectedState = {expected_state_ps}")
        ps1_lines.append("New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null")
        ps1_lines.append(
            f"if ((Test-Path $statePath) -and (Test-Path $vendorPath) -and "
            f"(@(Get-ChildItem -Force $vendorPath -ErrorAction SilentlyContinue).Count -gt 0) -and "
            f"((Get-Content -Raw -Path $statePath).Trim() -eq $expectedState)) "
            f"{{ Write-Host \"Skipping {spec['plugin_name']} plugin dependencies; already installed.\" }}"
        )
        ps1_lines.append("else {")
        ps1_lines.append(
            f"  & $pythonCmd.Source -m pip install --target $vendorPath {spec['requirements_ps']}"
        )
        ps1_lines.append(
            f"  if ($LASTEXITCODE -ne 0) {{ throw \"plugin dependency install failed: {spec['plugin_name']}\" }}"
        )
        ps1_lines.append("  Set-Content -Path $statePath -Value $expectedState -Encoding UTF8")
        ps1_lines.append("}")

        sh_lines.append(
            f"VENDOR_PATH=\"$SCRIPT_DIR/{spec['relative_vendor_target']}\""
        )
        sh_lines.append(f"STATE_PATH=\"$SCRIPT_DIR/{spec['relative_state_path']}\"")
        sh_lines.append(f"EXPECTED_STATE={shlex.quote(spec['expected_state'])}")
        sh_lines.append("mkdir -p \"$VENDOR_PATH\"")
        sh_lines.append(
            f"if [ -f \"$STATE_PATH\" ] && [ -n \"$(ls -A \"$VENDOR_PATH\" 2>/dev/null)\" ] "
            f"&& [ \"$(tr -d '\\r\\n' < \"$STATE_PATH\")\" = \"$EXPECTED_STATE\" ]; then"
        )
        sh_lines.append(f"  echo \"Skipping {spec['plugin_name']} plugin dependencies; already installed.\"")
        sh_lines.append("else")
        sh_lines.append(
            f"  \"$PYTHON_CMD\" -m pip install --target \"$VENDOR_PATH\" {spec['requirements_shell']}"
        )
        sh_lines.append("  printf '%s' \"$EXPECTED_STATE\" > \"$STATE_PATH\"")
        sh_lines.append("fi")

    write_text(bundle_dir / "install_plugin_deps.ps1", "\n".join(ps1_lines) + "\n")
    sh_path = bundle_dir / "install_plugin_deps.sh"
    write_text(sh_path, "\n".join(sh_lines) + "\n")
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return commands


def install_external_plugin_dependencies(bundle_dir: Path, plugin_roots: List[Path]) -> Tuple[bool, str]:
    outputs: List[str] = []
    for plugin_root in plugin_roots:
        metadata = collect_external_plugin_metadata(plugin_root)
        requirements = list(metadata.get("requirements") or [])
        if not requirements:
            continue
        if _external_plugin_dependency_install_is_current(plugin_root, metadata):
            outputs.append(f"skip {plugin_root.name}: plugin dependencies already installed")
            continue
        vendor_target = plugin_root / get_external_plugin_vendor_relative_dir()
        vendor_target.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(vendor_target),
            *requirements,
        ]
        code, output = run_cmd(cmd, cwd=bundle_dir)
        outputs.append(output)
        if code != 0:
            return False, output
        _write_external_plugin_dependency_state(plugin_root, metadata)
    return True, "\n".join(outputs)


def _scan_plugin_payloads(third_party_root: Path, filename: str) -> Dict[str, Dict[str, Any]]:
    payloads: Dict[str, Dict[str, Any]] = {}
    if not third_party_root.exists():
        return payloads

    for payload_path in sorted(third_party_root.rglob(filename)):
        try:
            payload = load_json(payload_path)
        except Exception:
            continue
        plugin = dict(payload.get("plugin") or {})
        plugin_id = str(plugin.get("id") or "").strip()
        if not plugin_id:
            continue
        payloads.setdefault(
            plugin_id,
            {
                "payload": dict(payload),
                "path": str(payload_path),
            },
        )
    return payloads


def _derive_snapshot_plugin_defaults(plugin_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    plugin = dict(payload.get("plugin") or {})
    inferred_name = str(plugin.get("name") or "").strip() or plugin_id
    inferred_config_key = str(plugin.get("config_key") or "").strip()
    if not inferred_config_key and "." in plugin_id:
        inferred_config_key = plugin_id.rsplit(".", 1)[-1]
    return {
        "id": plugin_id,
        "name": inferred_name,
        "version": str(plugin.get("version") or "").strip() or "0.0.0-snapshot",
        "config_key": inferred_config_key,
        "entrypoint": SNAPSHOT_PROVIDER_ENTRYPOINT,
    }


def _stringify_snapshot_template_list(raw_values: Any) -> List[str]:
    templates: List[str] = []
    for item in (raw_values or []):
        if isinstance(item, dict):
            value = str(item.get("path") or "").strip()
        else:
            value = str(item or "").strip()
        if value:
            templates.append(value)
    return templates


def _format_mobile_snapshot_manifest_debug(payload: Dict[str, Any]) -> str:
    plugin = dict(payload.get("plugin") or {})
    identity = dict(payload.get("identity") or {})
    storage = dict(payload.get("storage") or {})
    media_types = [str(item or "").strip() for item in (payload.get("media_types") or []) if str(item or "").strip()]
    comic_dir = dict(storage.get("comic_dir") or {})
    host_resolution = dict(storage.get("host_resolution") or {})
    comic_local_dir = dict(host_resolution.get("comic_local_dir") or {})
    comic_preview_cache_dir = dict(host_resolution.get("comic_preview_cache_dir") or {})

    comic_dir_template = str(comic_dir.get("template") or "").strip()
    comic_dir_fallbacks = _stringify_snapshot_template_list(comic_dir.get("fallback_templates") or [])
    local_templates = _stringify_snapshot_template_list(comic_local_dir.get("path_templates") or [])
    preview_templates = _stringify_snapshot_template_list(comic_preview_cache_dir.get("path_templates") or [])

    return (
        f"plugin_id={str(plugin.get('id') or '').strip()!r} "
        f"media_types={media_types!r} "
        f"host_prefix={str(identity.get('host_id_prefix') or '').strip()!r} "
        f"comic_dir_template={comic_dir_template!r} "
        f"comic_dir_fallbacks={comic_dir_fallbacks!r} "
        f"comic_local_templates={local_templates!r} "
        f"comic_preview_templates={preview_templates!r}"
    )


def summarize_mobile_protocol_snapshot_file(snapshot_path: Path) -> str:
    try:
        if not snapshot_path.exists():
            return f"missing path={snapshot_path}"
        payload = load_json(snapshot_path)
        manifests = payload.get("manifests") or payload.get("plugins") or []
        plugin_ids = []
        host_prefixes = []
        for item in manifests:
            plugin = dict(item.get("plugin") or {})
            identity = dict(item.get("identity") or {})
            plugin_id = str(plugin.get("id") or "").strip()
            host_prefix = str(identity.get("host_id_prefix") or "").strip()
            if plugin_id:
                plugin_ids.append(plugin_id)
            if host_prefix:
                host_prefixes.append(host_prefix)
        return (
            f"exists path={snapshot_path} size={snapshot_path.stat().st_size} "
            f"manifest_count={len(manifests)} plugin_ids={plugin_ids!r} host_prefixes={host_prefixes!r}"
        )
    except Exception as exc:
        return f"inspect_failed path={snapshot_path} error={exc!r}"


def inspect_android_apk_for_snapshot(apk_path: Path) -> str:
    try:
        if not apk_path.exists():
            return f"apk_missing path={apk_path}"
        matches: List[str] = []
        protocol_matches: List[str] = []
        bootstrap_matches: List[str] = []
        embedded_snapshot_bootstraps: List[str] = []
        with zipfile.ZipFile(apk_path, "r") as archive:
            names = archive.namelist()
            for name in names:
                normalized = str(name or "").replace("\\", "/")
                if normalized.endswith(f"/{MOBILE_PROTOCOL_SNAPSHOT_FILENAME}") or normalized.endswith(MOBILE_PROTOCOL_SNAPSHOT_FILENAME):
                    matches.append(normalized)
                if "/protocol/" in normalized and normalized.endswith(".json"):
                    protocol_matches.append(normalized)
                if normalized.endswith("/ultimate_android_backend.py") or normalized.endswith("ultimate_android_backend.py"):
                    bootstrap_matches.append(normalized)
                    try:
                        payload = archive.read(name).decode("utf-8", errors="replace")
                        if "EMBEDDED_PROTOCOL_SNAPSHOT_JSON =" in payload:
                            embedded_snapshot_bootstraps.append(normalized)
                    except Exception:
                        pass
        return (
            f"apk_path={apk_path} snapshot_matches={matches!r} "
            f"protocol_json_entries={protocol_matches[:20]!r} "
            f"bootstrap_matches={bootstrap_matches!r} "
            f"embedded_snapshot_bootstraps={embedded_snapshot_bootstraps!r}"
        )
    except Exception as exc:
        return f"apk_inspect_failed path={apk_path} error={exc!r}"


def build_mobile_protocol_snapshot(third_party_root: Path) -> Dict[str, Any]:
    manifest_payloads = _scan_plugin_payloads(third_party_root, "ultimate-plugin.json")
    overlay_payloads = _scan_plugin_payloads(third_party_root, HOST_OVERLAY_FILENAME)
    plugin_ids = sorted(set(manifest_payloads.keys()) | set(overlay_payloads.keys()))

    manifests: List[Dict[str, Any]] = []
    for plugin_id in plugin_ids:
        merged_payload: Dict[str, Any] = {}
        if plugin_id in manifest_payloads:
            merged_payload = _deep_merge_dict(
                merged_payload,
                manifest_payloads[plugin_id].get("payload") or {},
            )
        if plugin_id in overlay_payloads:
            merged_payload = _deep_merge_dict(
                merged_payload,
                overlay_payloads[plugin_id].get("payload") or {},
            )

        plugin = _derive_snapshot_plugin_defaults(plugin_id, merged_payload)
        merged_payload["plugin"] = plugin
        merged_payload["protocol_version"] = str(merged_payload.get("protocol_version") or "2.0").strip() or "2.0"
        media_types = merged_payload.get("media_types") or []
        if not isinstance(media_types, list):
            media_types = []
        merged_payload["media_types"] = [
            str(item or "").strip()
            for item in media_types
            if str(item or "").strip()
        ]
        manifests.append(merged_payload)

    print(f"[mobile-snapshot] source={third_party_root} manifests={len(manifests)}")
    for manifest_payload in manifests:
        print(f"[mobile-snapshot] {_format_mobile_snapshot_manifest_debug(manifest_payload)}")

    return {
        "version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifests": manifests,
    }


def collect_pyinstaller_plugin_metadata(staged_backend: Path) -> Dict[str, List[str]]:
    third_party_root = staged_backend / "third_party"
    plugin_roots = discover_packaged_plugin_roots(third_party_root)

    collect_all: List[str] = []
    hidden_imports: List[str] = []
    pip_requirements: List[str] = []

    for plugin_root in plugin_roots:
        for manifest_path in sorted(plugin_root.rglob("ultimate-plugin.json")):
            payload = load_json(manifest_path)
            packaging = dict((((payload.get("packaging") or {}).get("pyinstaller")) or {}))
            collect_all.extend(_normalize_string_list(packaging.get("collect_all") or []))
            hidden_imports.extend(_normalize_string_list(packaging.get("hidden_imports") or []))
            pip_requirements.extend(_normalize_string_list(packaging.get("pip_requirements") or []))

    return {
        "plugin_roots": [str(path) for path in plugin_roots],
        "collect_all": _normalize_string_list(collect_all),
        "hidden_imports": _normalize_string_list(hidden_imports),
        "pip_requirements": _normalize_string_list(pip_requirements),
    }


def write_pyinstaller_scripts(
    out_dir: Path,
    staged_target_dir: Path,
    target: str,
    binary_name: str,
    entry: str,
    runtime_env: Dict[str, str],
    plugin_package_mode: str = DEFAULT_PLUGIN_PACKAGE_MODE,
) -> List[str]:
    plugin_mode = normalize_plugin_package_mode(plugin_package_mode)
    dist_dir = out_dir / "dist"
    work_dir = out_dir / "build"
    spec_dir = out_dir / "spec"
    # 平台兼容的路径分隔符
    sep = ";" if os.name == "nt" else ":"
    
    # 使用绝对路径确保PyInstaller能找到文件
    staged_backend = staged_target_dir / "comic_backend"
    server_config_src = staged_target_dir / "server_config.json"
    cmd = [
        "python",
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        binary_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--collect-all", "flask",
        "--collect-all", "flask_cors",
        "--collect-all", "requests",
        "--collect-all", "yaml",
        "--collect-all", "PIL",
        "--collect-all", "bs4",
        "--hidden-import", "_multiprocessing",
        "--hidden-import", "protocol.credential_guard",
        "--hidden-import", "third_party",
        "--hidden-import", "third_party.external_api",
        "--hidden-import", "third_party.platform_service",
        "--hidden-import", "third_party.adapter",
        "--hidden-import", "third_party.credential_guard",
    ]
    append_repeated_cli_option(cmd, "--collect-submodules", DESKTOP_PLUGIN_RUNTIME_COLLECT_SUBMODULES)
    append_repeated_cli_option(cmd, "--hidden-import", DESKTOP_PLUGIN_RUNTIME_HIDDEN_IMPORTS)
    if plugin_mode == PLUGIN_PACKAGE_MODE_BUNDLED:
        plugin_metadata = collect_pyinstaller_plugin_metadata(staged_backend)
        append_repeated_cli_option(cmd, "--collect-all", list(plugin_metadata.get("collect_all") or []))
        append_repeated_cli_option(cmd, "--hidden-import", list(plugin_metadata.get("hidden_imports") or []))
        for plugin_root in plugin_metadata.get("plugin_roots") or []:
            plugin_path = Path(str(plugin_root))
            cmd.extend(
                [
                    "--add-data",
                    f"{plugin_path}{sep}comic_backend/third_party/{plugin_path.name}",
                ]
            )
    cmd.append(entry)
    
    if server_config_src.exists():
        cmd.insert(-1, f"--add-data")
        cmd.insert(-1, f"{server_config_src}{sep}.")

    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "param(\n"
        f"    [string]$StagedDir = \"{staged_target_dir}\"\n"
        ")\n"
        "Set-Location $StagedDir\n"
        f"$env:BACKEND_RUNTIME_PROFILE = \"{runtime_env.get('BACKEND_RUNTIME_PROFILE', 'full')}\"\n"
        f"$env:BACKEND_ENABLE_THIRD_PARTY = \"{runtime_env.get('BACKEND_ENABLE_THIRD_PARTY', 'true')}\"\n"
        + " ".join([f"\"{part}\"" if " " in part else part for part in cmd])
        + "\n"
    )
    write_text(out_dir / "run_pyinstaller.ps1", ps1)

    sh = (
        "#!/usr/bin/env sh\n"
        "set -e\n"
        "STAGED_DIR=\"${1:-"
        + str(staged_target_dir).replace("\\", "/")
        + "}\"\n"
        "cd \"$STAGED_DIR\"\n"
        f"export BACKEND_RUNTIME_PROFILE=\"{runtime_env.get('BACKEND_RUNTIME_PROFILE', 'full')}\"\n"
        f"export BACKEND_ENABLE_THIRD_PARTY=\"{runtime_env.get('BACKEND_ENABLE_THIRD_PARTY', 'true')}\"\n"
        + " ".join(cmd)
        + "\n"
    )
    sh_path = out_dir / "run_pyinstaller.sh"
    write_text(sh_path, sh)
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return cmd


def package_pyinstaller(
    target: str,
    staged_target_dir: Path,
    packager_cfg: Dict,
    target_out_dir: Path,
    execute: bool,
    plugin_package_mode: str = DEFAULT_PLUGIN_PACKAGE_MODE,
) -> PackageResult:
    plugin_mode = normalize_plugin_package_mode(plugin_package_mode)
    runtime_env = parse_runtime_env(staged_target_dir / "runtime.env")
    binary_name = str(packager_cfg.get("binary_name", f"ultimate_backend_{target}")).strip()
    entry = str(packager_cfg.get("entry", "comic_backend/app.py")).strip()
    frontend_dist_dir = str(packager_cfg.get("frontend_dist_dir", "comic_frontend_dist")).strip()

    cmd = write_pyinstaller_scripts(
        out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        target=target,
        binary_name=binary_name,
        entry=entry,
        runtime_env=runtime_env,
        plugin_package_mode=plugin_mode,
    )
    bundle_dir = prepare_desktop_release_bundle(
        target=target,
        target_out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        binary_name=binary_name,
        runtime_env=runtime_env,
        plugin_package_mode=plugin_mode,
    )
    external_plugin_roots = sorted((bundle_dir / "plugins").iterdir(), key=lambda item: item.name.lower()) if (bundle_dir / "plugins").exists() else []

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message=f"pyinstaller scripts generated; desktop release bundle prepared (plugin_package_mode={plugin_mode}, execution skipped)",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    vendor_ok, vendor_output = install_external_plugin_dependencies(bundle_dir, [path for path in external_plugin_roots if path.is_dir()])
    if vendor_output:
        write_text(target_out_dir / "plugin_vendor_install.log", vendor_output)
    if not vendor_ok:
        return PackageResult(
            target=target,
            status="failed",
            message="external plugin dependency installation failed; see plugin_vendor_install.log",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    host_target = current_host_target()
    if target != host_target:
        return PackageResult(
            target=target,
            status="blocked",
            message=f"packaging host mismatch: current host is {host_target}, target is {target}",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    if not is_pyinstaller_available():
        return PackageResult(
            target=target,
            status="blocked",
            message="PyInstaller not installed in current Python environment",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    code, output = run_cmd(cmd, cwd=staged_target_dir, env=runtime_env)
    build_log = target_out_dir / "pyinstaller.log"
    write_text(build_log, output)
    if code != 0:
        return PackageResult(
            target=target,
            status="failed",
            message=f"pyinstaller failed with code {code}; see {build_log}",
            output_dir=str(target_out_dir),
            command=cmd,
        )
    dist_dir = target_out_dir / "dist"
    built_binary = dist_dir / binary_name
    if target == "windows":
        built_binary = built_binary.with_suffix(".exe")
    if built_binary.exists():
        shutil.copy2(built_binary, bundle_dir / "bin" / built_binary.name)

    # Copy frontend dist if available
    frontend_source_dir = staged_target_dir / frontend_dist_dir
    if frontend_source_dir.exists():
        frontend_target_dir = bundle_dir / "frontend_dist"
        if frontend_target_dir.exists():
            shutil.rmtree(frontend_target_dir)
        shutil.copytree(frontend_source_dir, frontend_target_dir, ignore=shutil.ignore_patterns("__pycache__"))

    return PackageResult(
        target=target,
        status="built",
        message=f"pyinstaller build completed and desktop release bundle updated (plugin_package_mode={plugin_mode})",
        output_dir=str(target_out_dir),
        command=cmd,
    )


def write_android_capacitor_plan(
    target_out_dir: Path,
    staged_target_dir: Path,
    packager_cfg: Dict,
    app_version: str,
) -> Tuple[List[List[str]], Path, str]:
    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip()
    app_name = str(packager_cfg.get("app_name", "UltimateWeb")).strip()
    embed_backend = bool(packager_cfg.get("embed_backend", False))
    backend_port = int(packager_cfg.get("backend_port", 5000))
    staged_web_dir_name = str(packager_cfg.get("web_dir", "comic_frontend_dist")).strip() or "comic_frontend_dist"
    workspace_web_dir_name = str(packager_cfg.get("workspace_web_dir", "web")).strip() or "web"
    workspace_backend_dir_name = get_android_workspace_backend_dir(packager_cfg)
    gradle_task = str(packager_cfg.get("gradle_task", "assembleDebug")).strip() or "assembleDebug"
    apk_relative_path = str(
        packager_cfg.get(
            "apk_relative_path",
            "android/app/build/outputs/apk/debug/app-debug.apk",
        )
    ).strip() or "android/app/build/outputs/apk/debug/app-debug.apk"

    workspace_dir = choose_android_workspace_dir(target_out_dir, staged_target_dir, packager_cfg)
    ensure_clean_dir(workspace_dir)

    staged_web_dir = staged_target_dir / staged_web_dir_name
    if not staged_web_dir.exists():
        raise FileNotFoundError(f"android staged web dir not found: {staged_web_dir}")
    shutil.copytree(staged_web_dir, workspace_dir / workspace_web_dir_name)

    api_base_url = str(packager_cfg.get("api_base_url", "")).strip()
    if embed_backend and not api_base_url:
        api_base_url = f"http://127.0.0.1:{backend_port}/api"
    if api_base_url:
        runtime_js_path = workspace_dir / workspace_web_dir_name / "runtime-api-base.js"
        write_text(
            runtime_js_path,
            "window.__ULTIMATE_API_BASE_URL = "
            + json.dumps(api_base_url, ensure_ascii=False)
            + ";\n",
        )
        index_html = workspace_dir / workspace_web_dir_name / "index.html"
        if index_html.exists():
            raw = index_html.read_text(encoding="utf-8")
            marker = '<script src="./runtime-api-base.js"></script>'
            if marker not in raw:
                if "</head>" in raw:
                    raw = raw.replace("</head>", f"  {marker}\n</head>")
                else:
                    raw = f"{marker}\n{raw}"
                write_text(index_html, raw)

    staged_backend_dir = staged_target_dir / "comic_backend"
    if staged_backend_dir.exists():
        shutil.copytree(staged_backend_dir, workspace_dir / workspace_backend_dir_name)

    package_json = {
        "name": "ultimate-android-shell",
        "private": True,
        "version": normalize_app_version(app_version) or DEFAULT_APP_VERSION,
        "description": "Android shell build workspace for Ultimate Web",
    }
    write_text(
        workspace_dir / "package.json",
        json.dumps(package_json, ensure_ascii=False, indent=2) + "\n",
    )

    core_ver = str(packager_cfg.get("capacitor_core_version", "latest")).strip().lower()
    cli_ver = str(packager_cfg.get("capacitor_cli_version", "latest")).strip().lower()
    android_ver = str(packager_cfg.get("capacitor_android_version", "latest")).strip().lower()

    def cap_dep(name: str, version_text: str) -> str:
        if not version_text or version_text == "latest":
            return name
        return f"{name}@{version_text}"

    npm_cmd = get_npm_command()
    npx_cmd = get_npx_command()
    commands: List[List[str]] = [
        [
            npm_cmd,
            "install",
            "--no-fund",
            "--no-audit",
            cap_dep("@capacitor/core", core_ver),
            cap_dep("@capacitor/cli", cli_ver),
            cap_dep("@capacitor/android", android_ver),
        ],
        [npx_cmd, "cap", "init", app_name, app_id, "--web-dir", workspace_web_dir_name],
        [npx_cmd, "cap", "add", "android"],
        [npx_cmd, "cap", "sync", "android"],
    ]

    gradle_cmd = ["./gradlew", gradle_task]
    if os.name == "nt":
        # Execute batch wrapper through cmd on Windows for reliable process launching.
        gradle_cmd = ["cmd", "/c", "gradlew.bat", gradle_task]
    commands.append(gradle_cmd)

    pretty_commands = []
    for cmd in commands:
        pretty_commands.append(" ".join([f"\"{part}\"" if " " in part else part for part in cmd]))

    plan = [
        "# Android Packaging Plan",
        "",
        "The Android package can be built from this prepared workspace:",
        f"`{workspace_dir}`",
        "",
        "Command sequence:",
    ]
    for idx, cmd in enumerate(pretty_commands, start=1):
        plan.append(f"{idx}. `{cmd}`")
    plan.append("")
    plan.append("Notes:")
    plan.append(f"- app version: `{normalize_app_version(app_version) or DEFAULT_APP_VERSION}`")
    plan.append(f"- source staged web dir: `{staged_web_dir_name}`")
    plan.append(f"- workspace web dir: `{workspace_web_dir_name}`")
    plan.append(f"- workspace dir: `{workspace_dir}`")
    plan.append(f"- expected APK path in workspace: `{apk_relative_path}`")
    if embed_backend:
        plan.append(f"- backend build input dir: `{workspace_backend_dir_name}`")
        plan.append(f"- embedded backend api base: `http://127.0.0.1:{backend_port}/api`")
        plan.append("- embedded backend injection: enabled (Chaquopy consumes build-only backend input, not web assets)")
    plan.append("- ensure Android SDK, Java, and Gradle are available in environment.")
    write_text(target_out_dir / "android_packaging_plan.md", "\n".join(plan) + "\n")

    ps1_lines: List[str] = [
        "$ErrorActionPreference = 'Stop'",
        f"Set-Location \"{workspace_dir}\"",
    ]
    for cmd in pretty_commands:
        ps1_lines.append(cmd)
    write_text(target_out_dir / "run_capacitor.ps1", "\n".join(ps1_lines) + "\n")

    sh_lines: List[str] = [
        "#!/usr/bin/env sh",
        "set -e",
        f"cd \"{str(workspace_dir).replace('\\', '/')}\"",
    ]
    sh_lines.extend(pretty_commands)
    sh_path = target_out_dir / "run_capacitor.sh"
    write_text(sh_path, "\n".join(sh_lines) + "\n")
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return commands, workspace_dir, apk_relative_path


def package_android(
    target: str,
    staged_target_dir: Path,
    packager_cfg: Dict,
    target_out_dir: Path,
    execute: bool,
) -> PackageResult:
    app_version = resolve_app_version_from_staged(staged_target_dir)
    commands, workspace_dir, apk_relative_path = write_android_capacitor_plan(
        target_out_dir,
        staged_target_dir,
        packager_cfg,
        app_version,
    )
    embed_backend = bool(packager_cfg.get("embed_backend", False))
    android_env = resolve_android_java_env()
    sdk_dir = resolve_android_sdk_dir()
    if execute and "JAVA_HOME" not in android_env:
        return PackageResult(
            target=target,
            status="failed",
            message="android build requires Java, but JAVA_HOME/java was not detected",
            output_dir=str(target_out_dir),
            command=["java", "--version"],
        )
    if execute and not sdk_dir:
        return PackageResult(
            target=target,
            status="failed",
            message="android build requires Android SDK, but ANDROID_SDK_ROOT/ANDROID_HOME was not detected",
            output_dir=str(target_out_dir),
            command=["sdkmanager", "--version"],
        )
    if sdk_dir:
        android_env.setdefault("ANDROID_SDK_ROOT", sdk_dir)
        android_env.setdefault("ANDROID_HOME", sdk_dir)

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="android packaging workspace and scripts generated",
            output_dir=str(target_out_dir),
            command=[item for cmd in commands for item in cmd],
        )

    logs: List[str] = []
    for idx, cmd in enumerate(commands, start=1):
        cwd = workspace_dir
        if idx == len(commands):
            cwd = workspace_dir / "android"
            if not cwd.exists():
                return PackageResult(
                    target=target,
                    status="failed",
                    message=f"android project directory missing before gradle step: {cwd}",
                    output_dir=str(target_out_dir),
                    command=cmd,
                )
            write_android_local_properties(cwd, sdk_dir)
        try:
            code, output = run_cmd(cmd, cwd=cwd, env=android_env)
        except FileNotFoundError:
            log_path = target_out_dir / "android_build.log"
            logs.append(f"$ {' '.join(cmd)}\n[launcher-error] executable not found in PATH or cwd\n")
            write_text(log_path, "\n".join(logs))
            return PackageResult(
                target=target,
                status="failed",
                message=f"android build failed at step {idx}: command not found ({cmd[0]}); see {log_path}",
                output_dir=str(target_out_dir),
                command=cmd,
            )
        logs.append(f"$ {' '.join(cmd)}\n{output}\n")
        if code != 0:
            log_path = target_out_dir / "android_build.log"
            write_text(log_path, "\n".join(logs))
            return PackageResult(
                target=target,
                status="failed",
                message=f"android build failed at step {idx} with code {code}; see {log_path}",
                output_dir=str(target_out_dir),
                command=cmd,
            )
        if idx == 4:
            try:
                apply_android_launcher_icon(workspace_dir, packager_cfg)
                if str(packager_cfg.get("icon_source", "")).strip():
                    logs.append("$ [internal] apply android launcher icon\n[ok] launcher icon source applied\n")
            except Exception as ex:
                log_path = target_out_dir / "android_build.log"
                logs.append(f"$ [internal] apply android launcher icon\n[error] {ex}\n")
                write_text(log_path, "\n".join(logs))
                return PackageResult(
                    target=target,
                    status="failed",
                    message=f"android launcher icon apply failed after step {idx}; see {log_path}",
                    output_dir=str(target_out_dir),
                    command=["apply_android_launcher_icon"],
                )
        if embed_backend and idx == 4:
            try:
                inject_android_embedded_backend(workspace_dir, packager_cfg, app_version)
                logs.append("$ [internal] inject android embedded backend\n[ok] chaquopy + backend launcher injected after cap sync\n")
                snapshot_source_path = (
                    workspace_dir
                    / "android"
                    / "app"
                    / "src"
                    / "main"
                    / "python"
                    / "protocol"
                    / MOBILE_PROTOCOL_SNAPSHOT_FILENAME
                )
                logs.append(
                    "$ [internal] inspect android snapshot source\n"
                    + summarize_mobile_protocol_snapshot_file(snapshot_source_path)
                    + "\n"
                )
            except Exception as ex:
                log_path = target_out_dir / "android_build.log"
                logs.append(f"$ [internal] inject android embedded backend\n[error] {ex}\n")
                write_text(log_path, "\n".join(logs))
                return PackageResult(
                    target=target,
                    status="failed",
                    message=f"android embedded backend injection failed after step {idx}; see {log_path}",
                    output_dir=str(target_out_dir),
                    command=["inject_android_embedded_backend"],
                )

    expected_apk = workspace_dir / apk_relative_path
    if not expected_apk.exists():
        candidates = sorted((workspace_dir / "android").glob("app/build/outputs/apk/**/*.apk"))
        if candidates:
            expected_apk = candidates[-1]

    if not expected_apk.exists():
        log_path = target_out_dir / "android_build.log"
        write_text(log_path, "\n".join(logs))
        return PackageResult(
            target=target,
            status="failed",
            message=f"android build completed but APK not found; see {log_path}",
            output_dir=str(target_out_dir),
            command=["apk_lookup", apk_relative_path],
        )

    apk_out_dir = target_out_dir / "apk"
    apk_out_dir.mkdir(parents=True, exist_ok=True)
    apk_target = apk_out_dir / expected_apk.name
    shutil.copy2(expected_apk, apk_target)
    logs.append(
        "$ [internal] inspect android apk snapshot\n"
        + inspect_android_apk_for_snapshot(apk_target)
        + "\n"
    )

    log_path = target_out_dir / "android_build.log"
    write_text(log_path, "\n".join(logs))
    return PackageResult(
        target=target,
        status="built",
        message=f"android APK built: {apk_target}",
        output_dir=str(target_out_dir),
        command=[str(apk_target)],
    )


def write_summary(results: List[PackageResult], output_dir: Path) -> Path:
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "results": [
            {
                "target": item.target,
                "status": item.status,
                "message": item.message,
                "output_dir": item.output_dir,
                "command": item.command or [],
            }
            for item in results
        ],
    }
    summary_path = output_dir / "packaging_summary.json"
    write_text(summary_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare/execute package commands for multi-target staged workspaces.")
    parser.add_argument("--targets", default="all", help="Comma-separated targets or 'all'.")
    parser.add_argument("--staged", default=str(DEFAULT_STAGED_DIR), help="Staged workspaces root.")
    parser.add_argument("--output", default=str(DEFAULT_PACKAGES_DIR), help="Packaging output root.")
    parser.add_argument("--targets-config", default=str(DEFAULT_TARGETS_CONFIG), help="Path to build/targets.json.")
    parser.add_argument("--packagers-config", default=str(DEFAULT_PACKAGERS_CONFIG), help="Path to build/packagers.json.")
    parser.add_argument(
        "--plugin-package-mode",
        default=os.environ.get("ULTIMATE_PLUGIN_PACKAGE_MODE", DEFAULT_PLUGIN_PACKAGE_MODE),
        choices=PLUGIN_PACKAGE_MODES,
        help="Desktop plugin packaging mode: external keeps default plugins outside the executable; bundled compiles default plugins into the executable while keeping external plugin discovery enabled.",
    )
    parser.add_argument("--execute", action="store_true", help="Execute packaging commands when possible.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    staged_root = Path(args.staged).resolve()
    output_root = Path(args.output).resolve()
    targets_cfg = load_json(Path(args.targets_config).resolve())
    packagers_cfg = load_json(Path(args.packagers_config).resolve())

    available_targets = [str(item.get("id", "")).strip().lower() for item in targets_cfg.get("targets", []) if str(item.get("id", "")).strip()]
    selected_targets = select_targets(available_targets, args.targets)
    plugin_package_mode = normalize_plugin_package_mode(args.plugin_package_mode)

    packagers = packagers_cfg.get("packagers", {})
    if not isinstance(packagers, dict):
        raise ValueError("invalid packagers config")

    print(f"[package] targets: {', '.join(selected_targets)}")
    print(f"[package] staged root: {staged_root}")
    print(f"[package] output root: {output_root}")
    print(f"[package] plugin package mode: {plugin_package_mode}")

    results: List[PackageResult] = []
    for target in selected_targets:
        staged_target_dir = staged_root / target
        target_out_dir = output_root / target
        ensure_clean_dir(target_out_dir)

        if not staged_target_dir.exists():
            results.append(
                PackageResult(
                    target=target,
                    status="blocked",
                    message=f"staged target directory not found: {staged_target_dir}",
                    output_dir=str(target_out_dir),
                )
            )
            continue

        packager_cfg = packagers.get(target, {})
        packager_type = str(packager_cfg.get("type", "")).strip().lower()
        if packager_type == "pyinstaller":
            result = package_pyinstaller(
                target,
                staged_target_dir,
                packager_cfg,
                target_out_dir,
                execute=args.execute,
                plugin_package_mode=plugin_package_mode,
            )
        elif packager_type == "capacitor":
            result = package_android(target, staged_target_dir, packager_cfg, target_out_dir, execute=args.execute)
        else:
            result = PackageResult(
                target=target,
                status="blocked",
                message=f"unsupported packager type: {packager_type or 'empty'}",
                output_dir=str(target_out_dir),
            )

        results.append(result)
        print(f"[package] {target}: {result.status} - {result.message}")

    summary_path = write_summary(results, output_root)
    print(f"[package] summary: {summary_path}")

    has_failed = any(item.status in {"failed"} for item in results)
    return 1 if has_failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[package] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
