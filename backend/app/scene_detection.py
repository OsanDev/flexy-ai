"""FFmpeg-backed scene boundary detection for uploaded video assets."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class SceneDetectionError(ValueError):
    """Raised when scene detection cannot be completed safely."""


_TIME_RE = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


def detect_scenes(path: Path, *, threshold: float = 0.35, max_scenes: int = 500) -> list[dict[str, float | int]]:
    if not 0.05 <= threshold <= 0.95:
        raise SceneDetectionError("Threshold must be between 0.05 and 0.95.")
    if not 1 <= max_scenes <= 2000:
        raise SceneDetectionError("max_scenes must be between 1 and 2000.")
    if not path.is_file():
        raise SceneDetectionError("Video file was not found.")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise SceneDetectionError("FFmpeg is required for scene detection on this server.")

    # showinfo emits one pts_time for every frame selected by the scene filter.
    expression = f"select='gt(scene,{threshold:.3f})',showinfo"
    # Bound both the returned list and FFmpeg's diagnostic output. Without the
    # frame cap, a long video with frequent cuts can produce unbounded showinfo
    # output even though the API only returns max_scenes entries.
    command = [executable, "-hide_banner", "-nostats", "-i", str(path),
               "-vf", expression, "-an", "-frames:v", str(max_scenes),
               "-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SceneDetectionError("Scene detection timed out after 5 minutes.") from exc
    # FFmpeg may return non-zero for some container formats even after emitting
    # useful frames; only accept a successful exit to avoid partial results.
    if result.returncode != 0:
        raise SceneDetectionError("FFmpeg could not analyze this video.")

    timestamps: list[float] = []
    for match in _TIME_RE.finditer(result.stderr):
        value = float(match.group(1))
        if value >= 0 and (not timestamps or value > timestamps[-1]):
            timestamps.append(value)
        if len(timestamps) >= max_scenes:
            break
    return [{"index": index + 1, "start": timestamp}
            for index, timestamp in enumerate(timestamps)]


def extract_scene_thumbnail(video_path: Path, timestamp: float, output_path: Path) -> Path:
    """Extract one small JPEG preview frame at a scene timestamp."""
    if timestamp < 0:
        raise SceneDetectionError("Thumbnail timestamp cannot be negative.")
    if not video_path.is_file():
        raise SceneDetectionError("Video file was not found.")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise SceneDetectionError("FFmpeg is required for scene thumbnails on this server.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, "-hide_banner", "-loglevel", "error", "-y",
               "-ss", f"{timestamp:.3f}", "-i", str(video_path), "-frames:v", "1",
               "-vf", "scale=480:-2", "-q:v", "4", str(output_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SceneDetectionError("Scene thumbnail extraction timed out.") from exc
    if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise SceneDetectionError("FFmpeg could not extract a thumbnail at this timestamp.")
    return output_path
