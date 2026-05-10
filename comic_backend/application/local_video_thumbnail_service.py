from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List

from core.constants import PROJECT_ROOT
from core.runtime_profile import get_runtime_profile, is_mobile_core_profile


DEFAULT_LOCAL_VIDEO_THUMBNAIL_COUNT = 20
DEFAULT_LOCAL_VIDEO_THUMBNAIL_WIDTH = 480


def _current_platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _ffmpeg_binary_name() -> str:
    return "ffmpeg.exe" if _current_platform_key() == "windows" else "ffmpeg"


def _normalize_candidate_path(raw_value: str) -> str:
    candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(str(raw_value or "").strip())))
    if os.path.isdir(candidate):
        candidate = os.path.join(candidate, _ffmpeg_binary_name())
    return candidate


def _iter_ffmpeg_candidates() -> List[str]:
    binary_name = _ffmpeg_binary_name()
    platform_key = _current_platform_key()
    candidates: List[str] = []

    for env_key in ("ULTIMATE_FFMPEG_PATH", "FFMPEG_PATH"):
        env_value = str(os.environ.get(env_key, "") or "").strip()
        if env_value:
            candidates.append(_normalize_candidate_path(env_value))

    repo_relative_candidates = [
        os.path.join(PROJECT_ROOT, "tools", "ffmpeg", platform_key, binary_name),
        os.path.join(PROJECT_ROOT, "build", "runtime_tools", "ffmpeg", platform_key, binary_name),
        os.path.join(PROJECT_ROOT, "runtime_tools", "ffmpeg", platform_key, binary_name),
    ]
    candidates.extend([os.path.abspath(path) for path in repo_relative_candidates])

    frozen_exe = getattr(sys, "executable", "")
    if frozen_exe:
        exe_dir = os.path.abspath(os.path.dirname(frozen_exe))
        bundle_candidates = [
            os.path.join(exe_dir, "tools", "ffmpeg", binary_name),
            os.path.join(exe_dir, "..", "tools", "ffmpeg", binary_name),
        ]
        candidates.extend([os.path.abspath(path) for path in bundle_candidates])

    resolved_from_path = shutil.which("ffmpeg")
    if resolved_from_path:
        candidates.append(os.path.abspath(resolved_from_path))

    seen = set()
    normalized_candidates: List[str] = []
    for candidate in candidates:
        lowered = os.path.normcase(str(candidate or "").strip())
        if not lowered or lowered in seen:
            continue
        seen.add(lowered)
        normalized_candidates.append(candidate)
    return normalized_candidates


def resolve_ffmpeg_path() -> str:
    for candidate in _iter_ffmpeg_candidates():
        if os.path.isfile(candidate):
            return candidate
    return ""


def probe_local_video_thumbnail_runtime() -> Dict[str, Any]:
    runtime_profile = get_runtime_profile()
    platform_key = _current_platform_key()

    if is_mobile_core_profile():
        return {
            "supported": False,
            "provider": "ffmpeg_seek",
            "platform": platform_key,
            "runtime_profile": runtime_profile,
            "reason": "当前运行时未启用本地视频缩略图能力",
            "ffmpeg_path": "",
        }

    ffmpeg_path = resolve_ffmpeg_path()
    if not ffmpeg_path:
        return {
            "supported": False,
            "provider": "ffmpeg_seek",
            "platform": platform_key,
            "runtime_profile": runtime_profile,
            "reason": "未找到 ffmpeg 运行时",
            "ffmpeg_path": "",
        }

    return {
        "supported": True,
        "provider": "ffmpeg_seek",
        "platform": platform_key,
        "runtime_profile": runtime_profile,
        "reason": "",
        "ffmpeg_path": ffmpeg_path,
    }


class FFmpegLocalVideoThumbnailService:
    DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

    def __init__(self, ffmpeg_path: str = ""):
        self.ffmpeg_path = str(ffmpeg_path or "").strip() or resolve_ffmpeg_path()
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg executable is not available")

    def _run(self, args: List[str], allow_non_zero: bool = False) -> subprocess.CompletedProcess:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if not allow_non_zero and completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            message = stderr or stdout or "unknown ffmpeg error"
            raise RuntimeError(message)
        return completed

    def read_duration_seconds(self, video_path: str) -> float:
        completed = self._run(
            [
                self.ffmpeg_path,
                "-hide_banner",
                "-i",
                os.path.abspath(video_path),
            ],
            allow_non_zero=True,
        )
        text = "\n".join(
            part for part in ((completed.stdout or ""), (completed.stderr or "")) if str(part or "").strip()
        )
        match = self.DURATION_PATTERN.search(text)
        if not match:
            raise RuntimeError("unable to parse video duration from ffmpeg output")

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        duration = (hours * 3600) + (minutes * 60) + seconds
        if duration <= 0:
            raise RuntimeError("video duration must be positive")
        return duration

    @staticmethod
    def build_uniform_timestamps(duration_seconds: float, count: int) -> List[float]:
        normalized_count = max(1, int(count or 1))
        safe_duration = max(float(duration_seconds or 0.0), 0.1)
        timestamps: List[float] = []
        for index in range(normalized_count):
            timestamp = safe_duration * ((index + 0.5) / normalized_count)
            if safe_duration > 0.2:
                timestamp = min(max(timestamp, 0.1), safe_duration - 0.1)
            else:
                timestamp = max(0.0, min(timestamp, safe_duration))
            timestamps.append(round(timestamp, 3))
        return timestamps

    def _capture_single_thumbnail(self, video_path: str, timestamp_seconds: float, output_path: str, width: int) -> None:
        args = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-ss",
            f"{float(timestamp_seconds):.3f}",
            "-i",
            os.path.abspath(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={int(width)}:-2",
            "-q:v",
            "4",
            os.path.abspath(output_path),
        ]
        self._run(args)
        if not os.path.isfile(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(f"thumbnail was not written: {output_path}")

    def generate_thumbnails(
        self,
        *,
        video_path: str,
        output_dir: str,
        count: int = DEFAULT_LOCAL_VIDEO_THUMBNAIL_COUNT,
        width: int = DEFAULT_LOCAL_VIDEO_THUMBNAIL_WIDTH,
    ) -> Dict[str, Any]:
        normalized_video_path = os.path.abspath(str(video_path or "").strip())
        if not os.path.isfile(normalized_video_path):
            raise RuntimeError("video file does not exist")

        os.makedirs(output_dir, exist_ok=True)

        normalized_count = max(1, int(count or DEFAULT_LOCAL_VIDEO_THUMBNAIL_COUNT))
        normalized_width = max(160, int(width or DEFAULT_LOCAL_VIDEO_THUMBNAIL_WIDTH))
        duration_seconds = self.read_duration_seconds(normalized_video_path)
        timestamps = self.build_uniform_timestamps(duration_seconds, normalized_count)

        for index, timestamp_seconds in enumerate(timestamps, start=1):
            filename = f"thumb-{index:04d}.jpg"
            output_path = os.path.join(output_dir, filename)
            self._capture_single_thumbnail(
                normalized_video_path,
                timestamp_seconds,
                output_path,
                normalized_width,
            )

        default_cover_index = min(normalized_count - 1, max(0, normalized_count // 2))
        return {
            "provider": "ffmpeg_seek",
            "duration_seconds": duration_seconds,
            "timestamps": timestamps,
            "thumbnail_count": normalized_count,
            "default_cover_index": default_cover_index,
            "width": normalized_width,
        }
