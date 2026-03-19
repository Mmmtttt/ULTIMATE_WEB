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
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STAGED_DIR = ROOT_DIR / "output" / "multi_target"
DEFAULT_PACKAGES_DIR = ROOT_DIR / "output" / "packages"
DEFAULT_TARGETS_CONFIG = ROOT_DIR / "build" / "targets.json"
DEFAULT_PACKAGERS_CONFIG = ROOT_DIR / "build" / "packagers.json"


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
    if 'android:usesCleartextTraffic="true"' not in patched and "<application" in patched:
        patched = patched.replace("<application", '<application\n        android:usesCleartextTraffic="true"', 1)
    if patched != raw:
        write_text(manifest, patched)


def ensure_android_project_chaquopy_app(
    android_project_dir: Path,
    workspace_dir: Path,
    packager_cfg: Dict,
) -> None:
    workspace_web_dir = str(packager_cfg.get("workspace_web_dir", "web")).strip() or "web"
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

    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip() or "com.ultimate.web"
    backend_port = int(packager_cfg.get("backend_port", 5000))
    third_party_enabled = str(packager_cfg.get("android_backend_enable_third_party", "false")).strip().lower()
    java_rel = Path(*app_id.split(".")) / "MainActivity.java"
    java_path = android_project_dir / "app" / "src" / "main" / "java" / java_rel
    java_source = f"""package {app_id};

import android.os.Bundle;
import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.BridgeActivity;

import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends BridgeActivity {{
    private static final String TAG = "UltimateEmbeddedBackend";
    private static final AtomicBoolean BACKEND_STARTED = new AtomicBoolean(false);

    @Override
    public void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        startEmbeddedBackend();
    }}

    private void startEmbeddedBackend() {{
        if (!BACKEND_STARTED.compareAndSet(false, true)) {{
            return;
        }}
        final String filesDir = getApplicationContext().getFilesDir().getAbsolutePath();
        final int backendPort = {backend_port};
        new Thread(() -> {{
            try {{
                if (!Python.isStarted()) {{
                    Python.start(new AndroidPlatform(getApplicationContext()));
                }}
                PyObject module = Python.getInstance().getModule("ultimate_android_backend");
                module.callAttr("start_backend", filesDir, "127.0.0.1", backendPort, "{third_party_enabled}");
                Log.i(TAG, "Embedded backend startup invoked on port " + backendPort);
            }} catch (Throwable ex) {{
                Log.e(TAG, "Failed to start embedded backend", ex);
            }}
        }}, "ultimate-backend-thread").start();
    }}
}}
"""
    write_text(java_path, java_source)

    py_dir = android_project_dir / "app" / "src" / "main" / "python"
    py_dir.mkdir(parents=True, exist_ok=True)
    source_backend_dir = workspace_dir / workspace_web_dir / "backend_source"
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

    py_bootstrap = py_dir / "ultimate_android_backend.py"
    bootstrap_build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    py_source = """import os
import sys
import threading
import importlib
import importlib.util
from datetime import datetime


_started = False
_lock = threading.Lock()
BOOTSTRAP_BUILD_ID = "__BOOTSTRAP_BUILD_ID__"


def _write_boot_log(files_dir, message):
    try:
        target_dir = str(files_dir or "").strip() or "."
        os.makedirs(target_dir, exist_ok=True)
        log_path = os.path.join(target_dir, "ultimate_backend_boot.log")
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(f"{datetime.utcnow().isoformat()}Z {message}\\n")
    except Exception:
        pass


def start_backend(files_dir, host="127.0.0.1", port=5000, third_party_enabled="false"):
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
) -> None:
    android_project_dir = workspace_dir / "android"
    if not android_project_dir.exists():
        raise FileNotFoundError(f"android project dir not found: {android_project_dir}")
    min_sdk = int(packager_cfg.get("chaquopy_min_sdk", 24))
    chaquopy_version = str(packager_cfg.get("chaquopy_version", "17.0.0")).strip() or "17.0.0"
    patch_android_min_sdk(android_project_dir, min_sdk)
    ensure_android_project_chaquopy_root(android_project_dir, chaquopy_version)
    ensure_android_manifest_network(android_project_dir)
    ensure_android_project_chaquopy_app(android_project_dir, workspace_dir, packager_cfg)


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
        "start \"\" \"%SCRIPT_DIR%start_backend.bat\"\n"
        "timeout /t 2 >nul\n"
        "start \"\" \"http://127.0.0.1:5000/\"\n"
    )
    write_text(bundle_dir / "start_app.bat", app_bat)

    app_ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "Start-Process -FilePath (Join-Path $scriptDir 'start_backend.ps1') -NoNewWindow\n"
        "Start-Sleep -Seconds 2\n"
        "Start-Process 'http://127.0.0.1:5000/'\n"
    )
    write_text(bundle_dir / "start_app.ps1", app_ps1)


def prepare_desktop_release_bundle(
    target: str,
    target_out_dir: Path,
    staged_target_dir: Path,
    binary_name: str,
    runtime_env: Dict[str, str],
) -> Path:
    bundle_dir = target_out_dir / "release_bundle"
    ensure_clean_dir(bundle_dir)

    backend_src = staged_target_dir / "comic_backend"
    frontend_dist = staged_target_dir / "comic_frontend_dist"

    if backend_src.exists():
        shutil.copytree(backend_src, bundle_dir / "backend_source")
    if frontend_dist.exists():
        shutil.copytree(frontend_dist, bundle_dir / "frontend_dist")

    runtime_env_src = staged_target_dir / "runtime.env"
    if runtime_env_src.exists():
        shutil.copy2(runtime_env_src, bundle_dir / "runtime.env")

    server_config_src = staged_target_dir / "server_config.json"
    if server_config_src.exists():
        shutil.copy2(server_config_src, bundle_dir / "server_config.json")

    manifest_src = staged_target_dir / "package_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, bundle_dir / "stage_manifest.json")

    notes = [
        "# Desktop Release Bundle",
        "",
        f"- target: `{target}`",
        "- `backend_source/`: fallback Python source runtime",
        "- `frontend_dist/`: frontend static assets",
        "- `bin/`: packaged backend executable (if packaging executed successfully)",
        "",
        "Start commands:",
        "- Windows cmd: `start_backend.bat`",
        "- Windows PowerShell: `start_backend.ps1`",
        "- Linux/macOS: `start_backend.sh`",
    ]
    write_text(bundle_dir / "README.md", "\n".join(notes) + "\n")

    (bundle_dir / "bin").mkdir(parents=True, exist_ok=True)
    write_desktop_bundle_scripts(bundle_dir, binary_name=binary_name, runtime_env=runtime_env)
    return bundle_dir


def write_pyinstaller_scripts(
    out_dir: Path,
    staged_target_dir: Path,
    target: str,
    binary_name: str,
    entry: str,
    runtime_env: Dict[str, str],
) -> List[str]:
    dist_dir = out_dir / "dist"
    work_dir = out_dir / "build"
    spec_dir = out_dir / "spec"
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
        entry,
    ]

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
) -> PackageResult:
    runtime_env = parse_runtime_env(staged_target_dir / "runtime.env")
    binary_name = str(packager_cfg.get("binary_name", f"ultimate_backend_{target}")).strip()
    entry = str(packager_cfg.get("entry", "comic_backend/app.py")).strip()

    cmd = write_pyinstaller_scripts(
        out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        target=target,
        binary_name=binary_name,
        entry=entry,
        runtime_env=runtime_env,
    )
    bundle_dir = prepare_desktop_release_bundle(
        target=target,
        target_out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        binary_name=binary_name,
        runtime_env=runtime_env,
    )

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="pyinstaller scripts generated; desktop release bundle prepared (execution skipped)",
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

    return PackageResult(
        target=target,
        status="built",
        message="pyinstaller build completed and desktop release bundle updated",
        output_dir=str(target_out_dir),
        command=cmd,
    )


def write_android_capacitor_plan(
    target_out_dir: Path,
    staged_target_dir: Path,
    packager_cfg: Dict,
) -> Tuple[List[List[str]], Path, str]:
    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip()
    app_name = str(packager_cfg.get("app_name", "UltimateWeb")).strip()
    embed_backend = bool(packager_cfg.get("embed_backend", False))
    backend_port = int(packager_cfg.get("backend_port", 5000))
    staged_web_dir_name = str(packager_cfg.get("web_dir", "comic_frontend_dist")).strip() or "comic_frontend_dist"
    workspace_web_dir_name = str(packager_cfg.get("workspace_web_dir", "web")).strip() or "web"
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
        shutil.copytree(staged_backend_dir, workspace_dir / workspace_web_dir_name / "backend_source")
        if embed_backend:
            bootstrap_payload = {
                "enabled": True,
                "runtime_profile": "android",
                "backend_entry": "backend_source/app.py",
                "backend_port": backend_port,
                "android_data_env_key": "ANDROID_APP_FILES_DIR",
                "default_data_subdir": "app_data",
            }
            write_text(
                workspace_dir / workspace_web_dir_name / "backend_bootstrap.json",
                json.dumps(bootstrap_payload, ensure_ascii=False, indent=2) + "\n",
            )

    runtime_env = staged_target_dir / "runtime.env"
    if runtime_env.exists():
        shutil.copy2(runtime_env, workspace_dir / workspace_web_dir_name / "runtime.env")

    package_json = {
        "name": "ultimate-android-shell",
        "private": True,
        "version": "1.0.0",
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
    plan.append(f"- source staged web dir: `{staged_web_dir_name}`")
    plan.append(f"- workspace web dir: `{workspace_web_dir_name}`")
    plan.append(f"- workspace dir: `{workspace_dir}`")
    plan.append(f"- expected APK path in workspace: `{apk_relative_path}`")
    if embed_backend:
        plan.append(f"- embedded backend api base: `http://127.0.0.1:{backend_port}/api`")
        plan.append("- embedded backend injection: enabled (Chaquopy + MainActivity backend bootstrap)")
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
    commands, workspace_dir, apk_relative_path = write_android_capacitor_plan(
        target_out_dir,
        staged_target_dir,
        packager_cfg,
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
        if embed_backend and idx == 4:
            try:
                inject_android_embedded_backend(workspace_dir, packager_cfg)
                logs.append("$ [internal] inject android embedded backend\n[ok] chaquopy + backend launcher injected\n")
            except Exception as ex:
                log_path = target_out_dir / "android_build.log"
                logs.append(f"$ [internal] inject android embedded backend\n[error] {ex}\n")
                write_text(log_path, "\n".join(logs))
                return PackageResult(
                    target=target,
                    status="failed",
                    message=f"android embedded backend injection failed before step {idx}; see {log_path}",
                    output_dir=str(target_out_dir),
                    command=["inject_android_embedded_backend"],
                )
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

    packagers = packagers_cfg.get("packagers", {})
    if not isinstance(packagers, dict):
        raise ValueError("invalid packagers config")

    print(f"[package] targets: {', '.join(selected_targets)}")
    print(f"[package] staged root: {staged_root}")
    print(f"[package] output root: {output_root}")

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
            result = package_pyinstaller(target, staged_target_dir, packager_cfg, target_out_dir, execute=args.execute)
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
