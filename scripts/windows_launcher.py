"""Small Windows-only desktop launcher for the development and packaged app.

The launcher owns the backend and frontend processes so closing this window
also stops the services started by it. Its UI mirrors the web application's
blue-gray surfaces and uses the web brand image when Pillow is available.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import tempfile
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


APP_TITLE = "Ultimate Web 控制中心"
MAX_LOG_LINES = 4000
STARTUP_TIMEOUT_SECONDS = 45
HEALTH_CHECK_INTERVAL_SECONDS = 3

COLORS = {
    "page": "#eef2f8",
    "surface": "#ffffff",
    "surface_soft": "#f7faff",
    "surface_tint": "#edf4ff",
    "text": "#111b2d",
    "text_muted": "#5e6d85",
    "text_faint": "#8b98ad",
    "brand": "#3f84ea",
    "brand_hover": "#2b6fd5",
    "brand_soft": "#eaf2ff",
    "border": "#dce5f3",
    "border_strong": "#b9cce9",
    "log": "#0a1220",
    "log_text": "#bcd0e6",
    "success": "#00a875",
    "warning": "#f59a22",
    "danger": "#de5b6d",
}


@dataclass
class ServiceSpec:
    key: str
    title: str
    command: list[str]
    cwd: Path
    env: Dict[str, str]


def _read_runtime_env(root: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    path = root / "runtime.env"
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _default_config_dir(env: Optional[Dict[str, str]] = None) -> Path:
    values = env or os.environ
    configured = str(values.get("ULTIMATE_CONFIG_DIR", "")).strip()
    if configured:
        return Path(os.path.expandvars(os.path.expanduser(configured))).resolve()
    if os.name == "nt":
        base = values.get("APPDATA") or values.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "ULTIMATE_WEB"
    return Path(values.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ULTIMATE_WEB"


def _active_config_path(root: Path, env: Optional[Dict[str, str]] = None) -> Path:
    values = env or os.environ
    explicit = str(values.get("SERVER_CONFIG_PATH", "")).strip()
    if explicit:
        return Path(os.path.expandvars(os.path.expanduser(explicit))).resolve()

    config_dir = _default_config_dir(values)
    override = config_dir / "config_dir.override.json"
    try:
        payload = json.loads(override.read_text(encoding="utf-8"))
        persisted = str((payload or {}).get("config_dir", "")).strip()
        if persisted:
            config_dir = Path(os.path.expandvars(os.path.expanduser(persisted))).resolve()
    except (OSError, ValueError, TypeError):
        pass

    active = config_dir / "server_config.json"
    if active.exists():
        return active
    for legacy in (root / "server_config.json", root / "comic_backend" / "server_config.json", Path.cwd() / "server_config.json"):
        if legacy.exists():
            return legacy.resolve()
    return active


def _read_server_config(root: Path, env: Optional[Dict[str, str]] = None) -> dict:
    candidates = [_active_config_path(root, env), root / "server_config.json", Path.cwd() / "server_config.json"]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def _frontend_url(root: Path, env: Optional[Dict[str, str]] = None) -> str:
    config = _read_server_config(root, env)
    frontend = config.get("frontend") or {}
    port = int(frontend.get("port") or 5173)
    host = str(frontend.get("host") or "127.0.0.1")
    protocol = "https" if frontend.get("ssl_enabled", True) is not False else "http"
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    return f"{protocol}://{host}:{port}/"


def _service_port(url: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or "127.0.0.1", int(parsed.port or (443 if parsed.scheme == "https" else 80))


def _port(value: object, fallback: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return parsed if 1 <= parsed <= 65535 else fallback


def _config_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _resolve_data_path(root: Path, configured: object) -> Path:
    raw = os.path.expandvars(os.path.expanduser(str(configured or "").strip()))
    if not raw:
        raw = "./../UltimateData"
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _resolve_private_data_path(root: Path, config: dict) -> Path:
    normal = _resolve_data_path(root, (config.get("storage") or {}).get("data_dir"))
    configured = str((config.get("auth") or {}).get("private_data_dir", "")).strip()
    if not configured:
        return normal.parent / f"{normal.name}_private"
    normalized = configured.replace("\\", "/").strip()
    if normalized in {"../UltimateData_private", "./../UltimateData_private"}:
        return (normal.parent / "UltimateData_private").resolve()
    raw = Path(os.path.expandvars(os.path.expanduser(configured)))
    return raw.resolve() if raw.is_absolute() else (normal.parent / raw).resolve()


def _space_ports(config: dict) -> dict[str, Optional[int]]:
    backend = config.get("backend") or {}
    auth = config.get("auth") or {}
    auth_enabled = _config_bool(auth.get("enabled")) and bool(str(auth.get("password", "")).strip())
    if not auth_enabled:
        return {"private": None, "normal": _port(backend.get("port"), 5000)}
    return {
        "private": _port(auth.get("private_port"), 5000),
        "normal": _port(auth.get("normal_port"), 5001),
    }


def _config_protocol(section: object) -> str:
    return "https" if _config_bool((section or {}).get("ssl_enabled"), True) else "http"


def _health_url(host: str, port: Optional[int], protocol: str) -> Optional[str]:
    if port is None:
        return None
    normalized_host = host or "127.0.0.1"
    if normalized_host in {"0.0.0.0", "::", "[::]"}:
        normalized_host = "127.0.0.1"
    return f"{protocol}://{normalized_host}:{port}/health"


def _is_health_log_line(line: str) -> bool:
    normalized = str(line or "")
    return '"GET /health ' in normalized or '"HEAD /health ' in normalized


def _fit_window(window, preferred_width: int, preferred_height: int, minimum_width: int, minimum_height: int) -> None:
    """Size and center a window without exceeding the current display."""
    window.update_idletasks()
    screen_width = max(int(window.winfo_screenwidth()), 640)
    screen_height = max(int(window.winfo_screenheight()), 480)
    available_width = max(320, screen_width - 64)
    available_height = max(240, screen_height - 96)
    width = min(preferred_width, available_width)
    height = min(preferred_height, available_height)
    width = max(minimum_width if available_width >= minimum_width else available_width, width)
    height = max(minimum_height if available_height >= minimum_height else available_height, height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(min(minimum_width, available_width), min(minimum_height, available_height))


def _paths_overlap(path_a: Path, path_b: Path) -> bool:
    try:
        return os.path.commonpath([str(path_a), str(path_b)]) in {str(path_a), str(path_b)}
    except ValueError:
        return False


def _copy_tree_without_symlinks(source: Path, target: Path, progress=None) -> tuple[int, int]:
    """Copy real files only; symlinks are deliberately excluded from migration."""
    if not source.exists():
        target.mkdir(parents=True, exist_ok=True)
        return 0, 0
    if _paths_overlap(source, target):
        raise ValueError("源目录和目标目录不能互相包含")
    target.mkdir(parents=True, exist_ok=True)
    files = 0
    copied_bytes = 0
    for directory, dirnames, filenames in os.walk(source, followlinks=False):
        current = Path(directory)
        dirnames[:] = [name for name in dirnames if not (current / name).is_symlink()]
        relative = current.relative_to(source)
        output_dir = target / relative
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            source_file = current / filename
            if source_file.is_symlink() or not source_file.is_file():
                continue
            destination = output_dir / filename
            shutil.copy2(source_file, destination)
            files += 1
            copied_bytes += destination.stat().st_size
            if progress:
                progress(files, copied_bytes)
    return files, copied_bytes


def _brand_image_path(root: Path) -> Optional[Path]:
    """Find the web brand image in both development and PyInstaller layouts."""
    bundled_root = Path(getattr(sys, "_MEIPASS", ""))
    candidates = (
        root / "comic_frontend" / "public" / "vite.jpg",
        root / "assets" / "vite.jpg",
        bundled_root / "assets" / "vite.jpg",
        Path(__file__).resolve().parents[1] / "comic_frontend" / "public" / "vite.jpg",
    )
    return next((path for path in candidates if path.is_file()), None)


def _launcher_icon_path(root: Path) -> Optional[Path]:
    """Find the Windows icon in source and PyInstaller layouts."""
    bundled_root = Path(getattr(sys, "_MEIPASS", ""))
    candidates = (
        root / "comic_frontend" / "public" / "ultimate_web.ico",
        bundled_root / "assets" / "ultimate_web.ico",
        Path(__file__).resolve().parents[1] / "comic_frontend" / "public" / "ultimate_web.ico",
    )
    return next((path for path in candidates if path.is_file()), None)


def _configure_windows_app_identity() -> None:
    """Set the app identity before Tk creates its first native window."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.ultimateweb.controlcenter")
    except (AttributeError, OSError):
        pass


def _apply_windows_window_icon(window, icon_path: Optional[Path]) -> None:
    """Apply both Tk and native Win32 icons for development and packaged runs."""
    if os.name != "nt" or icon_path is None:
        return
    if icon_path is not None:
        try:
            window.iconbitmap(default=str(icon_path))
        except Exception:
            pass
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        hwnd = ctypes.c_void_p(window.winfo_id())
        load_from_file = 0x00000010
        image_icon = 1
        for icon_kind, size in ((1, 32), (0, 16)):
            handle = user32.LoadImageW(None, str(icon_path), image_icon, size, size, load_from_file)
            if handle:
                user32.SendMessageW(hwnd, 0x0080, icon_kind, handle)
    except (AttributeError, OSError, TypeError):
        pass


def _hidden_popen_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _package_env(root: Path) -> Dict[str, str]:
    env = os.environ.copy()
    env.update(_read_runtime_env(root))
    env["BACKEND_DEBUG"] = "false"
    env["BACKEND_HOST"] = "127.0.0.1"
    env["BACKEND_SERVE_FRONTEND"] = "false"
    env["FRONTEND_DIST_DIR"] = str(root / "frontend_dist")
    env["ULTIMATE_PLUGIN_ROOTS"] = str(root / "plugins")
    env["ULTIMATE_USER_PLUGIN_ROOT"] = str(root / "plugins")
    dependency_root = root / "runtime_deps" / "python"
    dependency_candidates = sorted(
        (path for path in dependency_root.glob("py*/*") if path.is_dir()),
        key=lambda path: path.as_posix(),
    )
    env["ULTIMATE_PLUGIN_DEP_ROOTS"] = str(dependency_candidates[0] if dependency_candidates else dependency_root)
    env["BACKEND_PLUGIN_DEP_ROOTS"] = env["ULTIMATE_PLUGIN_DEP_ROOTS"]
    env["ULTIMATE_PLUGIN_DEP_MANIFEST"] = str(root / "runtime_deps" / "dependency_pool_manifest.json")

    path_parts = []
    for candidate in (root / "tools" / "archive", root / "tools" / "ffmpeg"):
        if candidate.exists():
            path_parts.append(str(candidate))
    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts + [env.get("PATH", "")])
    return env


def _dev_env(root: Path) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("BACKEND_RUNTIME_PROFILE", "full")
    env.setdefault("BACKEND_ENABLE_THIRD_PARTY", "true")
    env["BACKEND_HOST"] = "127.0.0.1"
    env["PYTHONUNBUFFERED"] = "1"
    local_ffmpeg = root / "tools" / "ffmpeg" / "windows" / "ffmpeg.exe"
    if not env.get("ULTIMATE_FFMPEG_PATH") and local_ffmpeg.exists():
        env["ULTIMATE_FFMPEG_PATH"] = str(local_ffmpeg)
    return env


def _resolve_python() -> str:
    if sys.executable:
        return sys.executable
    return "python"


def build_service_specs(root: Path, mode: str, backend_exe: str = "", frontend_exe: str = "") -> list[ServiceSpec]:
    if mode == "packaged":
        env = _package_env(root)
        backend_path = root / "bin" / (backend_exe or "ultimate_backend_windows.exe")
        frontend_path = root / "bin" / (frontend_exe or "ultimate_frontend_windows.exe")
        return [
            ServiceSpec("backend", "后端服务", [str(backend_path)], root, env.copy()),
            ServiceSpec("frontend", "前端服务", [str(frontend_path)], root, env.copy()),
        ]

    env = _dev_env(root)
    return [
        ServiceSpec("backend", "后端服务", [_resolve_python(), "-u", "app.py"], root / "comic_backend", env.copy()),
        ServiceSpec(
            "frontend",
            "前端服务",
            ["cmd.exe", "/d", "/s", "/c", "npm.cmd run dev"],
            root / "comic_frontend",
            env.copy(),
        ),
    ]


class LauncherApp:
    def __init__(self, root: Path, mode: str, *, open_browser: bool, backend_exe: str = "", frontend_exe: str = ""):
        import tkinter as tk
        from tkinter import scrolledtext, ttk

        self.tk = tk
        self.root = root.resolve()
        self.mode = mode
        self.open_browser = open_browser
        self.runtime_env = _read_runtime_env(self.root)
        self.config_path = _active_config_path(self.root, self.runtime_env)
        self.config = _read_server_config(self.root, self.runtime_env)
        self.url = _frontend_url(self.root, self.runtime_env)
        self.events: queue.Queue[tuple] = queue.Queue()
        self.processes: Dict[str, subprocess.Popen[str]] = {}
        self.specs = build_service_specs(self.root, mode, backend_exe, frontend_exe)
        self.starting = False
        self.stopping = False
        self.closing = False
        self.browser_opened = False
        self.log_lines = 0
        self.brand_image = None
        self.status_indicators = {}
        self.space_status_vars = {}
        self.space_indicators = {}
        self.health_polling = True
        self.action_buttons = {}
        self.suppressed_exit_keys = set()

        self.window_icon_path = _launcher_icon_path(self.root)
        _configure_windows_app_identity()
        self.window = tk.Tk()
        self.window.title(APP_TITLE)
        _fit_window(self.window, 940, 660, 760, 520)
        self.window.configure(bg=COLORS["page"])
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.backdrop = tk.Canvas(
            self.window,
            background=COLORS["page"],
            highlightthickness=0,
            bd=0,
        )
        self.backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self.backdrop.bind("<Configure>", self._draw_backdrop)
        self.status_vars = {spec.key: tk.StringVar(self.window, value="未启动") for spec in self.specs}
        self.status_labels = {}
        self.service_meta_vars = {}

        image_path = _brand_image_path(self.root)
        if image_path:
            try:
                from PIL import Image, ImageTk

                image = Image.open(image_path).convert("RGB")
                resampling = getattr(Image, "Resampling", Image)
                image.thumbnail((52, 52), resampling.LANCZOS)
                self.brand_image = ImageTk.PhotoImage(image, master=self.window)
                self.window.iconphoto(True, self.brand_image)
            except (ImportError, OSError, AttributeError):
                # The launcher remains usable if an optional image dependency is absent.
                self.brand_image = None
        _apply_windows_window_icon(self.window, self.window_icon_path)

        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure("Launcher.TFrame", background=COLORS["page"])
        style.configure("Header.TFrame", background=COLORS["surface"], borderwidth=0, relief="flat")
        style.configure("HeaderInner.TFrame", background=COLORS["surface"], borderwidth=0, relief="flat")
        style.configure("Panel.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        style.configure("ServiceCard.TFrame", background=COLORS["surface"], borderwidth=0, relief="flat")
        style.configure("ServiceInner.TFrame", background=COLORS["surface"], borderwidth=0, relief="flat")
        style.configure("LogPanel.TFrame", background=COLORS["log"], borderwidth=0)
        style.configure("LogHeader.TFrame", background=COLORS["log"])
        style.configure("Header.TLabel", background=COLORS["surface"])
        style.configure("DialogHeader.TFrame", background=COLORS["surface"], borderwidth=0, relief="flat")
        style.configure("DialogCard.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        style.configure("DialogFooter.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid", bordercolor=COLORS["border"])
        style.configure("DialogTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("DialogKicker.TLabel", background=COLORS["surface"], foreground=COLORS["brand"], font=("Segoe UI", 8, "bold"))
        style.configure("DialogSection.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("DialogMeta.TLabel", background=COLORS["surface"], foreground=COLORS["text_faint"], font=("Cascadia Mono", 8))
        style.configure("DialogBadge.TLabel", background=COLORS["brand_soft"], foreground=COLORS["brand"], font=("Segoe UI", 8, "bold"), padding=(7, 3))
        style.configure("DialogField.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9))
        style.configure("DialogHint.TLabel", background=COLORS["surface"], foreground=COLORS["text_faint"], font=("Microsoft YaHei UI", 8))
        style.configure("Dialog.TEntry", fieldbackground=COLORS["surface_soft"], foreground=COLORS["text"], bordercolor=COLORS["border"], lightcolor=COLORS["border_strong"], darkcolor=COLORS["border"], padding=(9, 7), font=("Microsoft YaHei UI", 9))
        style.map("Dialog.TEntry", fieldbackground=[("focus", "#ffffff")], bordercolor=[("focus", COLORS["brand"])], lightcolor=[("focus", COLORS["brand"])])
        style.configure("Dialog.TCheckbutton", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9), padding=(0, 2))
        style.map("Dialog.TCheckbutton", foreground=[("active", COLORS["brand"])], background=[("active", COLORS["surface"])])
        style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("SubTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Brand.TLabel", background=COLORS["surface"], foreground=COLORS["brand"], font=("Segoe UI", 9, "bold"))
        style.configure("Kicker.TLabel", background=COLORS["surface"], foreground=COLORS["brand"], font=("Segoe UI", 8, "bold"))
        style.configure("SectionTitle.TLabel", background=COLORS["page"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("SectionMeta.TLabel", background=COLORS["page"], foreground=COLORS["text_faint"], font=("Microsoft YaHei UI", 8))
        style.configure("PanelTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("CardKicker.TLabel", background=COLORS["surface"], foreground=COLORS["text_faint"], font=("Segoe UI", 8, "bold"))
        style.configure("Status.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Address.TLabel", background=COLORS["log"], foreground="#aec5e8", font=("Cascadia Mono", 8))
        style.configure("Meta.TLabel", background=COLORS["surface"], foreground=COLORS["text_faint"], font=("Cascadia Mono", 8))
        style.configure("Space.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 8))
        style.configure("LogTitle.TLabel", background=COLORS["log"], foreground="#f0f6ff", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("LogMeta.TLabel", background=COLORS["log"], foreground="#8da4c5", font=("Microsoft YaHei UI", 8))
        style.configure("LogAction.TButton", background="#293752", foreground="#c8daf5", padding=(7, 3), borderwidth=0, font=("Microsoft YaHei UI", 8))
        style.map("LogAction.TButton", background=[("active", "#35486b")], foreground=[("active", "#ffffff")])
        style.configure("Accent.TButton", background=COLORS["brand"], foreground="#ffffff", padding=(16, 9), borderwidth=0, font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", COLORS["brand_hover"]), ("disabled", "#b8c9e6")])
        style.configure("Small.TButton", background=COLORS["surface"], foreground=COLORS["brand"], padding=(9, 6), borderwidth=1, relief="solid", bordercolor=COLORS["border"], font=("Microsoft YaHei UI", 8))
        style.map("Small.TButton", background=[("active", COLORS["brand_soft"])], bordercolor=[("active", COLORS["border_strong"])])
        style.configure("Danger.TButton", background=COLORS["surface"], foreground=COLORS["danger"], padding=(9, 6), borderwidth=1, relief="solid", bordercolor="#f0c7cf", font=("Microsoft YaHei UI", 8))
        style.map("Danger.TButton", background=[("active", "#fff1f3")])
        style.configure("Ghost.TButton", background=COLORS["surface"], foreground=COLORS["text_muted"], padding=(13, 9), borderwidth=1, relief="solid", bordercolor=COLORS["border"], font=("Microsoft YaHei UI", 9))
        style.map("Ghost.TButton", background=[("active", COLORS["brand_soft"])], foreground=[("active", COLORS["brand"])])
        style.configure("ServiceStart.TButton", background=COLORS["brand"], foreground="#ffffff", padding=(8, 7), borderwidth=0, font=("Microsoft YaHei UI", 8, "bold"))
        style.map("ServiceStart.TButton", background=[("active", COLORS["brand_hover"]), ("disabled", "#b8c9e6")])
        style.configure("ServiceRestart.TButton", background=COLORS["surface_tint"], foreground=COLORS["brand"], padding=(8, 7), borderwidth=0, font=("Microsoft YaHei UI", 8))
        style.map("ServiceRestart.TButton", background=[("active", COLORS["brand_soft"])])
        style.configure("ServiceStop.TButton", background="#fff7f8", foreground=COLORS["danger"], padding=(8, 7), borderwidth=0, font=("Microsoft YaHei UI", 8))
        style.map("ServiceStop.TButton", background=[("active", "#ffebef")])

        outer = ttk.Frame(self.window, style="Launcher.TFrame", padding=(24, 22))
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer, style="Header.TFrame", padding=(20, 16, 20, 14))
        header.pack(fill="x", pady=(0, 14))
        brand_row = ttk.Frame(header, style="HeaderInner.TFrame")
        brand_row.pack(fill="x")
        if self.brand_image is not None:
            ttk.Label(brand_row, image=self.brand_image, style="Header.TLabel").pack(side="left", padx=(0, 14))
        title_box = ttk.Frame(brand_row, style="HeaderInner.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="ULTIMATE WEB  /  DESKTOP", style="Kicker.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Ultimate Web", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="本地服务控制中心  ·  关闭窗口将同时停止服务", style="SubTitle.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(brand_row, text="LOCAL · SECURE", style="Brand.TLabel").pack(side="right", anchor="n", pady=5)
        self.config_button = ttk.Button(brand_row, text="服务配置", style="Small.TButton", command=self.open_config_dialog)
        self.config_button.pack(side="right", anchor="n", padx=(0, 12), pady=1)
        accent = tk.Canvas(header, height=3, background=COLORS["surface"], highlightthickness=0, bd=0)
        accent.pack(fill="x", pady=(15, 0))

        def draw_brand_accent(event=None):
            width = max(accent.winfo_width(), 1)
            accent.delete("all")
            accent.create_rectangle(0, 0, width * 0.22, 3, fill="#ff9d2b", outline="")
            accent.create_rectangle(width * 0.22, 0, width, 3, fill=COLORS["brand"], outline="")

        accent.bind("<Configure>", draw_brand_accent)

        services_header = ttk.Frame(outer, style="Launcher.TFrame")
        services_header.pack(fill="x", pady=(0, 8))
        ttk.Label(services_header, text="服务状态", style="SectionTitle.TLabel").pack(side="left")
        ttk.Label(services_header, text="每 3 秒刷新 · 后端仅本机访问", style="SectionMeta.TLabel").pack(side="right")

        cards = ttk.Frame(outer, style="Launcher.TFrame")
        cards.pack(fill="x", pady=(0, 14))
        cards.columnconfigure(0, weight=1, uniform="service")
        cards.columnconfigure(1, weight=1, uniform="service")
        for index, spec in enumerate(self.specs):
            card = ttk.Frame(cards, style="ServiceCard.TFrame", padding=(16, 14))
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 7 if index == 0 else 0))
            card_header = ttk.Frame(card, style="ServiceInner.TFrame")
            card_header.pack(fill="x")
            indicator = tk.Canvas(card_header, width=11, height=11, background=COLORS["surface"], highlightthickness=0, bd=0)
            indicator.pack(side="left", padx=(0, 7), pady=2)
            indicator.create_oval(2, 2, 9, 9, fill=COLORS["text_faint"], outline="")
            self.status_indicators[spec.key] = indicator
            ttk.Label(card_header, text=spec.title, style="PanelTitle.TLabel").pack(side="left")
            kind = "WEB GATEWAY" if spec.key == "frontend" else "LOCAL API"
            ttk.Label(card_header, text=kind, style="CardKicker.TLabel").pack(side="right")
            status_label = ttk.Label(card, textvariable=self.status_vars[spec.key], style="Status.TLabel")
            status_label.pack(anchor="w", pady=(8, 0))
            self.status_labels[spec.key] = status_label
            meta_var = tk.StringVar(self.window, value=self._service_meta(spec.key))
            ttk.Label(card, textvariable=meta_var, style="Meta.TLabel").pack(anchor="w", pady=(2, 0))
            self.service_meta_vars = getattr(self, "service_meta_vars", {})
            self.service_meta_vars[spec.key] = meta_var

            details = ttk.Frame(card, style="ServiceInner.TFrame", height=64)
            details.pack(fill="x", pady=(10, 0))
            details.pack_propagate(False)

            if spec.key == "backend":
                spaces = ttk.Frame(details, style="ServiceInner.TFrame")
                spaces.pack(fill="x")
                for space_key, title in (("private", "隐私空间"), ("normal", "正常空间")):
                    row = ttk.Frame(spaces, style="ServiceInner.TFrame")
                    row.pack(fill="x", pady=(0, 5))
                    indicator = tk.Canvas(row, width=9, height=9, background=COLORS["surface"], highlightthickness=0, bd=0)
                    indicator.pack(side="left", padx=(0, 6), pady=2)
                    indicator.create_oval(2, 2, 7, 7, fill=COLORS["text_faint"], outline="")
                    self.space_indicators[space_key] = indicator
                    value = tk.StringVar(self.window, value="未检测")
                    self.space_status_vars[space_key] = value
                    ttk.Label(row, text=title, style="Space.TLabel").pack(side="left")
                    ttk.Label(row, textvariable=value, style="Space.TLabel").pack(side="right")

            if spec.key == "frontend":
                entry_header = ttk.Frame(details, style="ServiceInner.TFrame")
                entry_header.pack(fill="x")
                ttk.Label(entry_header, text="浏览器入口", style="Space.TLabel").pack(side="left")
                self.open_button = ttk.Button(entry_header, text="打开网页", style="Accent.TButton", command=self.open_browser_page)
                self.open_button.pack(side="right")
                ttk.Label(details, text=self.url, style="Meta.TLabel").pack(anchor="w", pady=(4, 0))

            action_row = ttk.Frame(card, style="ServiceInner.TFrame")
            action_row.pack(fill="x", pady=(12, 0))
            for column in range(3):
                action_row.columnconfigure(column, weight=1, uniform="service-action")
            for action, label, callback, style_name in (
                ("start", "启动", lambda key=spec.key: self.start_service(key), "ServiceStart.TButton"),
                ("restart", "重启", lambda key=spec.key: self.restart_service(key), "ServiceRestart.TButton"),
                ("stop", "停止", lambda key=spec.key: self.stop_service(key), "ServiceStop.TButton"),
            ):
                button = ttk.Button(action_row, text=label, style=style_name, command=callback)
                button.grid(row=0, column=("start", "restart", "stop").index(action), sticky="ew", padx=(0 if action == "start" else 4, 0))
                self.action_buttons[(spec.key, action)] = button

        log_panel = ttk.Frame(outer, style="LogPanel.TFrame", padding=(14, 12))
        log_panel.pack(fill="both", expand=True)
        log_header = ttk.Frame(log_panel, style="LogHeader.TFrame")
        log_header.pack(fill="x", pady=(0, 8))
        ttk.Label(log_header, text="运行日志", style="LogTitle.TLabel").pack(side="left")
        ttk.Label(log_header, text="控制中心输出", style="LogMeta.TLabel").pack(side="left", padx=(9, 0))
        ttk.Button(log_header, text="清空", style="LogAction.TButton", command=self.clear_log).pack(side="right")
        self.address_label = ttk.Label(log_header, text=self.url, style="Address.TLabel")
        self.address_label.pack(side="right", padx=(0, 10))
        self.log = scrolledtext.ScrolledText(
            log_panel,
            background=COLORS["log"],
            foreground=COLORS["log_text"],
            insertbackground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Cascadia Mono", 9),
            wrap="word",
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self.log_line("控制中心已启动")
        self.log_line(f"访问地址: {self.url}")
        self.window.after(100, self.process_events)
        self.window.after(300, self.start_services)
        self.window.after(1200, self.poll_health)

    def _draw_backdrop(self, event=None) -> None:
        canvas = self.backdrop
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill=COLORS["page"], outline="")
        canvas.create_oval(-width * 0.22, -height * 0.28, width * 0.42, height * 0.48, fill="#dceaff", outline="")
        canvas.create_oval(width * 0.58, -height * 0.18, width * 1.18, height * 0.48, fill="#deefe9", outline="")
        canvas.create_oval(width * 0.48, height * 0.58, width * 1.2, height * 1.22, fill="#f2e7db", outline="")
        for offset in range(-height, width + height, 34):
            canvas.create_line(offset, height, offset + height, 0, fill="#e4ebf6", width=1)
        # Canvas redraws raise this widget; explicitly keep the ambient layer behind all controls.
        canvas.tk.call("lower", canvas._w)

    def _service_meta(self, key: str) -> str:
        if key == "frontend":
            section = self.config.get("frontend") or {}
            port = _port(section.get("port"), 5173)
            return f"{_config_protocol(section).upper()}  ·  :{port}"
        section = self.config.get("backend") or {}
        ports = _space_ports(self.config)
        active = [f"{name}:{port}" for name, port in ports.items() if port is not None]
        return f"端口  ·  {', '.join(active)}"

    def log_line(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log_lines += 1
        if self.log_lines > MAX_LOG_LINES:
            self.log.delete("1.0", "2.0")
            self.log_lines -= 1
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.log_lines = 0

    def set_status(self, key: str, value: str) -> None:
        self.status_vars[key].set(value)
        indicator = self.status_indicators.get(key)
        color = COLORS["text_faint"]
        if value == "运行中":
            color = COLORS["success"]
        elif value == "启动中":
            color = COLORS["warning"]
        elif value in {"启动失败", "已退出"}:
            color = COLORS["danger"]
        if indicator is not None:
            indicator.itemconfigure(1, fill=color)
        label = self.status_labels.get(key)
        if label is not None:
            label.configure(foreground=color)

    def start_service(self, key: str) -> None:
        if self.stopping or self.closing:
            return
        if key in self.processes and self.processes[key].poll() is None:
            self.log_line(f"{key}已经在运行")
            return
        spec = next((item for item in self.specs if item.key == key), None)
        if spec is None:
            return
        executable = Path(spec.command[0])
        executable_available = executable.exists() or shutil.which(spec.command[0]) is not None
        if not spec.cwd.exists() or not executable_available:
            self.set_status(spec.key, "启动失败")
            self.log_line(f"{spec.title}路径不存在或不可执行: {spec.cwd}")
            return
        try:
            self.suppressed_exit_keys.discard(key)
            process = subprocess.Popen(
                spec.command,
                cwd=str(spec.cwd),
                env=spec.env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **_hidden_popen_kwargs(),
            )
            self.processes[spec.key] = process
            self.set_status(spec.key, "启动中")
            self.log_line(f"{spec.title}已启动，PID={process.pid}")
            threading.Thread(target=self._read_output, args=(spec.key, process), daemon=True).start()
            if key == "frontend":
                threading.Thread(target=self._wait_for_frontend, daemon=True).start()
        except OSError as exc:
            self.set_status(spec.key, "启动失败")
            self.log_line(f"{spec.title}启动失败: {exc}")

    def start_services(self) -> None:
        if self.starting or self.stopping or self.closing:
            return
        self.starting = True
        for spec in self.specs:
            self.start_service(spec.key)
        self.starting = False

    def stop_service(self, key: str) -> None:
        process = self.processes.pop(key, None)
        if process is None or process.poll() is not None:
            self.set_status(key, "已停止")
            return
        self.suppressed_exit_keys.add(key)
        self.log_line(f"正在停止{key}，PID={process.pid}")
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    **_hidden_popen_kwargs(),
                )
            except OSError:
                process.terminate()
        else:
            process.terminate()
        self.set_status(key, "已停止")

    def stop_services(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        for spec in self.specs:
            self.stop_service(spec.key)
        self.stopping = False

    def restart_service(self, key: str) -> None:
        if self.stopping or self.closing:
            return
        self.log_line(f"正在重启{key}...")
        self.stop_service(key)
        self.window.after(350, lambda: self.start_service(key))

    def _read_output(self, key: str, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            if key == "frontend":
                match = re.search(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?/", line)
                if match:
                    self.events.put(("url", match.group(0)))
            self.events.put(("log", key, line.rstrip()))
        self.events.put(("exit", key, process.poll()))

    def _wait_for_frontend(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline and not self.stopping:
            host, port = _service_port(self.url)
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    self.events.put(("ready",))
                    return
            except OSError:
                time.sleep(0.25)
        self.events.put(("timeout",))

    @staticmethod
    def _probe_url(url: Optional[str]) -> tuple[bool, str]:
        if not url:
            return False, "未启用"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "UltimateWebLauncher/1.0"})
            context = None
            if url.startswith("https://"):
                import ssl

                context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=1.5, context=context) as response:
                return 200 <= int(response.status) < 500, f"可用 · {response.status}"
        except Exception as exc:
            return False, "未连接"

    def _set_space_status(self, key: str, ok: bool, text: str) -> None:
        value = self.space_status_vars.get(key)
        if value is not None:
            value.set(text)
        indicator = self.space_indicators.get(key)
        if indicator is not None:
            color = COLORS["success"] if ok else COLORS["danger"]
            if text == "未启用":
                color = COLORS["text_faint"]
            indicator.itemconfigure(1, fill=color)

    def poll_health(self) -> None:
        if self.closing:
            return
        config = self.config
        backend = config.get("backend") or {}
        backend_host = "127.0.0.1"
        backend_protocol = _config_protocol(backend)
        ports = _space_ports(config)
        checks = {
            "frontend": self.url.rstrip("/") + "/health",
            "private": _health_url(backend_host, ports.get("private"), backend_protocol),
            "normal": _health_url(backend_host, ports.get("normal"), backend_protocol),
        }
        for key, url in checks.items():
            threading.Thread(
                target=lambda check_key=key, check_url=url: self.events.put(
                    ("health", check_key, *self._probe_url(check_url))
                ),
                daemon=True,
            ).start()
        self.window.after(HEALTH_CHECK_INTERVAL_SECONDS * 1000, self.poll_health)

    def process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    key, line = event[1], event[2]
                    self.set_status(key, "运行中")
                    if line and not _is_health_log_line(line):
                        self.log_line(f"{key}: {line}")
                elif kind == "exit":
                    key, code = event[1], event[2]
                    if key in self.suppressed_exit_keys:
                        self.suppressed_exit_keys.discard(key)
                    elif not self.stopping and not self.closing:
                        self.set_status(key, "已退出")
                        self.log_line(f"{key}已退出，代码={code}")
                elif kind == "ready":
                    self.set_status("frontend", "运行中")
                    self.log_line("前端服务已就绪")
                    if self.open_browser and not self.browser_opened:
                        self.open_browser_page()
                elif kind == "url":
                    self.url = event[1]
                    self.address_label.configure(text=self.url)
                    self.log_line(f"前端实际地址: {self.url}")
                elif kind == "timeout":
                    self.log_line("等待前端服务超时，请查看上方日志")
                elif kind == "health":
                    key, ok, text = event[1], event[2], event[3]
                    if key == "frontend":
                        if ok:
                            self.set_status("frontend", "运行中")
                        self.address_label.configure(text=self.url)
                    else:
                        self._set_space_status(key, ok, text)
                elif kind == "config_progress":
                    label = getattr(self, "config_progress_label", None)
                    if label is not None and label.winfo_exists():
                        label.configure(text=event[1])
                elif kind == "config_result":
                    self._finish_config_save(event)
        except queue.Empty:
            pass
        if self.window.winfo_exists():
            self.window.after(100, self.process_events)

    def open_browser_page(self) -> None:
        self.browser_opened = True
        webbrowser.open(self.url)

    def restart(self) -> None:
        if self.stopping or self.closing:
            return
        self.log_line("正在重启全部服务...")
        self.stop_services()
        self.window.after(500, self.start_services)

    def _write_config(self, config: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix="server_config.", suffix=".tmp", dir=str(self.config_path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(config, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.config_path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def _finish_config_save(self, event: tuple) -> None:
        _, success, config, restart_now, error, copied = event
        progress = getattr(self, "config_progress_window", None)
        if progress is not None and progress.winfo_exists():
            progress.destroy()
        self.config_progress_window = None
        self.config_progress_label = None
        if not success:
            self.log_line(f"配置迁移失败: {error}")
            from tkinter import messagebox

            messagebox.showerror("配置未保存", f"数据迁移失败，配置没有修改。\n\n{error}", parent=self.window)
            return
        try:
            self._write_config(config)
        except OSError as exc:
            self.log_line(f"配置保存失败: {exc}")
            from tkinter import messagebox

            messagebox.showerror("配置未保存", str(exc), parent=self.window)
            return
        self.config = config
        self.url = _frontend_url(self.root, self.runtime_env)
        self.address_label.configure(text=self.url)
        for key, variable in self.service_meta_vars.items():
            variable.set(self._service_meta(key))
        self.log_line(f"配置已保存: {self.config_path}")
        if copied:
            self.log_line(f"数据迁移完成: {copied} 个文件")
        if restart_now:
            self.log_line("配置需要重启服务，正在重新启动...")
            self.window.after(300, self.start_services)

    def _migrate_config_data(self, config: dict, migrations: list[tuple[Path, Path, str]], restart_now: bool) -> None:
        copied = 0
        try:
            for source, target, label in migrations:
                self.events.put(("config_progress", f"正在迁移{label}: {source} → {target}"))
                files, _ = _copy_tree_without_symlinks(source, target)
                copied += files
            self.events.put(("config_result", True, config, restart_now, "", copied))
        except Exception as exc:
            self.events.put(("config_result", False, config, restart_now, str(exc), copied))

    def _save_config_from_dialog(self, dialog, fields: dict, restart_now: bool) -> None:
        from tkinter import messagebox

        try:
            ports = {}
            for key in ("frontend_port", "backend_port", "private_port", "normal_port"):
                value = int(fields[key].get().strip())
                if not 1 <= value <= 65535:
                    raise ValueError(f"端口必须在 1 到 65535 之间: {value}")
                ports[key] = value
        except ValueError as exc:
            messagebox.showerror("配置无效", str(exc), parent=dialog)
            return

        config = copy.deepcopy(self.config)
        backend = config.setdefault("backend", {})
        frontend = config.setdefault("frontend", {})
        auth = config.setdefault("auth", {})
        # The backend is an internal service. Keep its host and TLS settings
        # under program control; only its listening ports are user-configurable.
        backend["host"] = "127.0.0.1"
        backend["port"] = ports["backend_port"]
        frontend.update({
            "host": fields["frontend_host"].get().strip() or "0.0.0.0",
            "port": ports["frontend_port"],
            "ssl_enabled": bool(fields["frontend_ssl"].get()),
            "ssl_cert_path": fields["frontend_cert"].get().strip(),
            "ssl_key_path": fields["frontend_key"].get().strip(),
        })
        auth["private_port"] = ports["private_port"]
        auth["normal_port"] = ports["normal_port"]
        config.setdefault("storage", {})["data_dir"] = fields["data_dir"].get().strip()
        auth["private_data_dir"] = fields["private_data_dir"].get().strip()

        old_normal = _resolve_data_path(self.root, (self.config.get("storage") or {}).get("data_dir"))
        new_normal = _resolve_data_path(self.root, (config.get("storage") or {}).get("data_dir"))
        old_private = _resolve_private_data_path(self.root, self.config)
        new_private = _resolve_private_data_path(self.root, config)
        migrations = []
        if fields["migrate_data"].get() and old_normal != new_normal:
            migrations.append((old_normal, new_normal, "正常空间数据"))
        if fields["migrate_data"].get() and old_private != new_private:
            migrations.append((old_private, new_private, "隐私空间数据"))
        if migrations and not restart_now:
            messagebox.showerror("需要重启服务", "迁移数据前后必须重启服务，请使用“保存并重启”。", parent=dialog)
            return
        targets = [target for _, target, _ in migrations]
        if len(targets) != len(set(targets)) or (new_normal == new_private):
            messagebox.showerror("配置无效", "正常空间和隐私空间不能使用同一个目录。", parent=dialog)
            return
        for source, target, _ in migrations:
            if _paths_overlap(source, target):
                messagebox.showerror("配置无效", "源目录和目标目录不能互相包含。", parent=dialog)
                return

        dialog.destroy()
        if migrations:
            self.stop_services()
            progress = self.tk.Toplevel(self.window)
            progress.title("正在迁移数据")
            _fit_window(progress, 520, 150, 400, 120)
            progress.resizable(False, False)
            progress.configure(bg=COLORS["page"])
            self.config_progress_window = progress
            label = self.tk.Label(progress, text="正在迁移数据，请不要关闭控制中心。", bg=COLORS["page"], fg=COLORS["text"], font=("Microsoft YaHei UI", 10))
            label.pack(anchor="w", padx=24, pady=(24, 8))
            self.config_progress_label = label
            self.tk.Label(progress, text="源目录会保留，软链接不会被复制。", bg=COLORS["page"], fg=COLORS["text_muted"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=24)
            threading.Thread(target=self._migrate_config_data, args=(config, migrations, restart_now), daemon=True).start()
            return
        if restart_now:
            self.stop_services()
        self._finish_config_save(("config_result", True, config, restart_now, "", 0))

    def open_config_dialog(self) -> None:
        from tkinter import filedialog, ttk

        dialog = self.tk.Toplevel(self.window)
        dialog.title("服务配置")
        _fit_window(dialog, 760, 700, 620, 420)
        dialog.configure(bg=COLORS["page"])
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(True, True)

        config = self.config
        backend = config.get("backend") or {}
        frontend = config.get("frontend") or {}
        auth = config.get("auth") or {}
        storage = config.get("storage") or {}
        fields = {}

        body = ttk.Frame(dialog, style="Launcher.TFrame", padding=(18, 18, 18, 14))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        header = ttk.Frame(body, style="DialogHeader.TFrame", padding=(18, 15, 18, 14))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="ULTIMATE WEB  /  SETTINGS", style="DialogKicker.TLabel").pack(anchor="w")
        ttk.Label(header, text="服务配置", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(header, text="调整服务入口、端口与数据空间。保存后可按需重启服务。", style="DialogHint.TLabel").pack(anchor="w", pady=(4, 3))
        ttk.Label(header, text=f"当前生效配置：{self.config_path}", style="DialogMeta.TLabel").pack(anchor="w")
        accent = self.tk.Canvas(header, height=3, background=COLORS["surface"], highlightthickness=0, bd=0)
        accent.pack(fill="x", pady=(13, 0))

        def draw_dialog_accent(event=None):
            width = max(accent.winfo_width(), 1)
            accent.delete("all")
            accent.create_rectangle(0, 0, width * 0.22, 3, fill="#ff9d2b", outline="")
            accent.create_rectangle(width * 0.22, 0, width, 3, fill=COLORS["brand"], outline="")

        accent.bind("<Configure>", draw_dialog_accent)

        content = ttk.Frame(body, style="Launcher.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        canvas = self.tk.Canvas(content, background=COLORS["page"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        form = ttk.Frame(canvas, style="Launcher.TFrame", padding=(0, 12, 8, 0))
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_form(event):
            canvas.itemconfigure(form_window, width=event.width)

        form.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_form)
        canvas.bind("<Enter>", lambda event: canvas.bind_all("<MouseWheel>", lambda wheel: canvas.yview_scroll(int(-wheel.delta / 120), "units")))
        canvas.bind("<Leave>", lambda event: canvas.unbind_all("<MouseWheel>"))

        section_number = 0

        def section(title: str, subtitle: str):
            nonlocal section_number
            section_number += 1
            card = ttk.Frame(form, style="DialogCard.TFrame", padding=(16, 14))
            card.pack(fill="x", pady=(0, 10))
            section_header = ttk.Frame(card, style="DialogCard.TFrame")
            section_header.pack(fill="x", pady=(0, 10))
            ttk.Label(section_header, text=f"{section_number:02d}", style="DialogBadge.TLabel").pack(side="left")
            section_text = ttk.Frame(section_header, style="DialogCard.TFrame")
            section_text.pack(side="left", padx=(10, 0))
            ttk.Label(section_text, text=title, style="DialogSection.TLabel").pack(anchor="w")
            ttk.Label(section_text, text=subtitle, style="DialogHint.TLabel").pack(anchor="w", pady=(2, 0))
            return card

        def row(parent, label: str, key: str, value: str, browse: bool = False, hint: str = ""):
            line = ttk.Frame(parent, style="DialogCard.TFrame")
            line.pack(fill="x", pady=4)
            line.columnconfigure(1, weight=1)
            ttk.Label(line, text=label, width=15, style="DialogField.TLabel").grid(row=0, column=0, sticky="nw", padx=(0, 12), pady=7)
            variable = self.tk.StringVar(dialog, value=value)
            fields[key] = variable
            ttk.Entry(line, textvariable=variable, style="Dialog.TEntry").grid(row=0, column=1, sticky="ew")
            if browse:
                ttk.Button(line, text="选择目录", style="Small.TButton", command=lambda var=variable: var.set(filedialog.askdirectory() or var.get())).grid(row=0, column=2, padx=(8, 0))
            if hint:
                ttk.Label(line, text=hint, style="DialogHint.TLabel").grid(row=1, column=1, columnspan=2, sticky="w", pady=(3, 0))

        def check(parent, variable, text: str, hint: str = ""):
            option = ttk.Frame(parent, style="DialogCard.TFrame")
            option.pack(fill="x", pady=(4, 5))
            ttk.Checkbutton(option, text=text, variable=variable, style="Dialog.TCheckbutton").pack(anchor="w")
            if hint:
                ttk.Label(option, text=hint, style="DialogHint.TLabel").pack(anchor="w", padx=(24, 0), pady=(1, 0))

        frontend_card = section("前端代理", "局域网访问入口与 HTTPS 设置")
        row(frontend_card, "监听地址", "frontend_host", str(frontend.get("host", "0.0.0.0")), hint="0.0.0.0 表示允许局域网设备访问")
        row(frontend_card, "端口", "frontend_port", str(_port(frontend.get("port"), 5173)))
        fields["frontend_ssl"] = self.tk.BooleanVar(dialog, value=_config_bool(frontend.get("ssl_enabled"), True))
        check(frontend_card, fields["frontend_ssl"], "启用 HTTPS", "开启后，浏览器入口将使用 HTTPS；证书为空时由程序自动生成")
        row(frontend_card, "证书路径", "frontend_cert", str(frontend.get("ssl_cert_path", "")), True, "可留空，使用程序自动生成的自签名证书")
        row(frontend_card, "私钥路径", "frontend_key", str(frontend.get("ssl_key_path", "")), True)

        backend_card = section("后端服务", "数据服务仅监听本机，由前端代理统一转发")
        ttk.Label(
            backend_card,
            text="无需配置 IP 或证书；下面仅调整本机服务端口。",
            style="DialogHint.TLabel",
        ).pack(anchor="w", pady=(0, 7))
        row(backend_card, "单空间端口", "backend_port", str(_port(backend.get("port"), 5000)))
        row(backend_card, "隐私空间端口", "private_port", str(_port(auth.get("private_port"), 5000)))
        row(backend_card, "正常空间端口", "normal_port", str(_port(auth.get("normal_port"), 5001)))

        storage_card = section("数据目录", "正常空间与隐私空间使用相互独立的文件目录")
        row(storage_card, "正常空间目录", "data_dir", str(storage.get("data_dir", "./../UltimateData")), True)
        row(storage_card, "隐私空间目录", "private_data_dir", str(auth.get("private_data_dir", "UltimateData_private")), True)
        fields["migrate_data"] = self.tk.BooleanVar(dialog, value=False)
        check(storage_card, fields["migrate_data"], "迁移现有数据到新目录", "源目录保留，软链接跳过；迁移完成后需要重启服务")

        footer = ttk.Frame(body, style="DialogFooter.TFrame", padding=(14, 10))
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(footer, text="修改端口或目录后，建议使用保存并重启。", style="DialogHint.TLabel").pack(side="left")
        actions = ttk.Frame(footer, style="DialogFooter.TFrame")
        actions.pack(side="right")
        ttk.Button(actions, text="取消", style="Ghost.TButton", command=dialog.destroy).pack(side="left")
        ttk.Button(actions, text="仅保存", style="Ghost.TButton", command=lambda: self._save_config_from_dialog(dialog, fields, False)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="保存并重启", style="Accent.TButton", command=lambda: self._save_config_from_dialog(dialog, fields, True)).pack(side="left", padx=(8, 0))

    def close(self) -> None:
        if self.stopping or self.closing:
            return
        self.closing = True
        self.stop_services()
        self.log_line("服务已停止，正在退出")
        self.window.after(150, self.window.destroy)

    def run(self) -> int:
        self.window.mainloop()
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ultimate Web Windows control center")
    parser.add_argument("--root", default=".", help="Project or package root")
    parser.add_argument("--mode", choices=("dev", "packaged"), default="dev")
    parser.add_argument("--backend-exe", default="")
    parser.add_argument("--frontend-exe", default="")
    parser.add_argument("--open-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = LauncherApp(Path(args.root), args.mode, open_browser=args.open_browser, backend_exe=args.backend_exe, frontend_exe=args.frontend_exe)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
