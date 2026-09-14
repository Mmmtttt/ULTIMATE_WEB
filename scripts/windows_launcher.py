"""Small Windows-only desktop launcher for the development and packaged app.

The launcher owns the backend and frontend processes so closing this window
also stops the services started by it. Its UI mirrors the web application's
blue-gray surfaces and uses the web brand image when Pillow is available.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


APP_TITLE = "Ultimate Web 控制中心"
MAX_LOG_LINES = 4000
STARTUP_TIMEOUT_SECONDS = 45

COLORS = {
    "page": "#eef2f8",
    "surface": "#ffffff",
    "surface_soft": "#f7faff",
    "text": "#111b2d",
    "text_muted": "#5e6d85",
    "text_faint": "#8b98ad",
    "brand": "#3f84ea",
    "brand_hover": "#2b6fd5",
    "brand_soft": "#eaf2ff",
    "border": "#dce5f3",
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


def _read_server_config(root: Path) -> dict:
    candidates = [root / "server_config.json", Path.cwd() / "server_config.json"]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def _frontend_url(root: Path) -> str:
    config = _read_server_config(root)
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
        self.url = _frontend_url(self.root)
        self.events: queue.Queue[tuple] = queue.Queue()
        self.processes: Dict[str, subprocess.Popen[str]] = {}
        self.specs = build_service_specs(self.root, mode, backend_exe, frontend_exe)
        self.starting = False
        self.stopping = False
        self.browser_opened = False
        self.log_lines = 0
        self.brand_image = None
        self.status_indicators = {}

        self.window = tk.Tk()
        self.window.title(APP_TITLE)
        self.window.geometry("940x660")
        self.window.minsize(760, 520)
        self.window.configure(bg=COLORS["page"])
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.status_vars = {spec.key: tk.StringVar(self.window, value="未启动") for spec in self.specs}
        self.status_labels = {}

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

        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure("Launcher.TFrame", background=COLORS["page"])
        style.configure("Header.TFrame", background=COLORS["surface"])
        style.configure("Panel.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid")
        style.configure("Header.TLabel", background=COLORS["surface"])
        style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("SubTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Brand.TLabel", background=COLORS["surface"], foreground=COLORS["brand"], font=("Segoe UI", 10, "bold"))
        style.configure("PanelTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Status.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Address.TLabel", background=COLORS["surface"], foreground=COLORS["text_faint"], font=("Cascadia Mono", 8))
        style.configure("Accent.TButton", background=COLORS["brand"], foreground="#ffffff", padding=(16, 9), borderwidth=0, font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", COLORS["brand_hover"]), ("disabled", "#b8c9e6")])
        style.configure("Ghost.TButton", background=COLORS["surface"], foreground=COLORS["text_muted"], padding=(13, 9), borderwidth=1, relief="solid", bordercolor=COLORS["border"], font=("Microsoft YaHei UI", 9))
        style.map("Ghost.TButton", background=[("active", COLORS["brand_soft"])], foreground=[("active", COLORS["brand"])])

        outer = ttk.Frame(self.window, style="Launcher.TFrame", padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer, style="Header.TFrame", padding=(16, 14, 16, 12))
        header.pack(fill="x", pady=(0, 16))
        brand_row = ttk.Frame(header, style="Header.TFrame")
        brand_row.pack(fill="x")
        if self.brand_image is not None:
            ttk.Label(brand_row, image=self.brand_image, style="Header.TLabel").pack(side="left", padx=(0, 12))
        title_box = ttk.Frame(brand_row, style="Header.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="Ultimate Web", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="本地服务控制中心  ·  关闭窗口将同时停止服务", style="SubTitle.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Label(brand_row, text="LOCAL DESKTOP", style="Brand.TLabel").pack(side="right", anchor="n", pady=5)
        accent = tk.Canvas(header, height=4, background=COLORS["surface"], highlightthickness=0, bd=0)
        accent.pack(fill="x", pady=(13, 0))

        def draw_brand_accent(event=None):
            width = max(accent.winfo_width(), 1)
            accent.delete("all")
            accent.create_rectangle(0, 0, width * 0.38, 4, fill="#ff8d16", outline="")
            accent.create_rectangle(width * 0.38, 0, width, 4, fill="#2f74ff", outline="")

        accent.bind("<Configure>", draw_brand_accent)

        cards = ttk.Frame(outer, style="Launcher.TFrame")
        cards.pack(fill="x", pady=(0, 16))
        for spec in self.specs:
            card = ttk.Frame(cards, style="Panel.TFrame", padding=(15, 13))
            card.pack(side="left", fill="x", expand=True, padx=(0, 10 if spec is self.specs[0] else 0))
            card_header = ttk.Frame(card, style="Panel.TFrame")
            card_header.pack(fill="x")
            indicator = tk.Canvas(card_header, width=11, height=11, background=COLORS["surface"], highlightthickness=0, bd=0)
            indicator.pack(side="left", padx=(0, 7), pady=2)
            indicator.create_oval(2, 2, 9, 9, fill=COLORS["text_faint"], outline="")
            self.status_indicators[spec.key] = indicator
            ttk.Label(card_header, text=spec.title, style="PanelTitle.TLabel").pack(side="left")
            status_label = ttk.Label(card, textvariable=self.status_vars[spec.key], style="Status.TLabel")
            status_label.pack(anchor="w", pady=(6, 0))
            self.status_labels[spec.key] = status_label

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        log_panel.pack(fill="both", expand=True)
        log_header = ttk.Frame(log_panel, style="Panel.TFrame")
        log_header.pack(fill="x", pady=(0, 8))
        ttk.Label(log_header, text="运行日志", style="PanelTitle.TLabel").pack(side="left")
        self.address_label = ttk.Label(log_header, text=self.url, style="Address.TLabel")
        self.address_label.pack(side="right")
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

        actions = ttk.Frame(outer, style="Launcher.TFrame")
        actions.pack(fill="x", pady=(16, 0))
        self.open_button = ttk.Button(actions, text="打开网页", style="Accent.TButton", command=self.open_browser_page)
        self.open_button.pack(side="left")
        ttk.Button(actions, text="重启服务", style="Ghost.TButton", command=self.restart).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="清空日志", style="Ghost.TButton", command=self.clear_log).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="退出并停止服务", style="Ghost.TButton", command=self.close).pack(side="right")

        self.log_line("控制中心已启动")
        self.log_line(f"访问地址: {self.url}")
        self.window.after(100, self.process_events)
        self.window.after(300, self.start_services)

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
        if indicator is None:
            return
        color = COLORS["text_faint"]
        if value == "运行中":
            color = COLORS["success"]
        elif value == "启动中":
            color = COLORS["warning"]
        elif value in {"启动失败", "已退出"}:
            color = COLORS["danger"]
        indicator.itemconfigure(1, fill=color)

    def start_services(self) -> None:
        if self.starting or self.stopping:
            return
        self.starting = True
        for spec in self.specs:
            executable = Path(spec.command[0])
            executable_available = executable.exists() or shutil.which(spec.command[0]) is not None
            if not spec.cwd.exists() or not executable_available:
                self.set_status(spec.key, "启动失败")
                self.log_line(f"{spec.title}路径不存在: {spec.cwd}")
                continue
            try:
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
            except OSError as exc:
                self.set_status(spec.key, "启动失败")
                self.log_line(f"{spec.title}启动失败: {exc}")
        self.starting = False
        threading.Thread(target=self._wait_for_frontend, daemon=True).start()

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

    def process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    key, line = event[1], event[2]
                    self.set_status(key, "运行中")
                    if line:
                        self.log_line(f"{key}: {line}")
                elif kind == "exit":
                    key, code = event[1], event[2]
                    if not self.stopping:
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
        except queue.Empty:
            pass
        if self.window.winfo_exists():
            self.window.after(100, self.process_events)

    def open_browser_page(self) -> None:
        self.browser_opened = True
        webbrowser.open(self.url)

    def restart(self) -> None:
        if self.stopping:
            return
        self.log_line("正在重启服务...")
        self.stop_services()
        self.stopping = False
        self.window.after(500, self.start_services)

    def stop_services(self) -> None:
        self.stopping = True
        for key, process in list(self.processes.items()):
            if process.poll() is not None:
                continue
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
        self.processes.clear()

    def close(self) -> None:
        if self.stopping:
            return
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
