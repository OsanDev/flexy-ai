"""Lightweight point tracking for compositing overlays.

Tracks a user-selected image patch between sampled frames using local template
matching. This is an assistive 2D tracker, not semantic object recognition.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


class MotionTrackingError(ValueError):
    """Raised when point tracking cannot be completed."""


def _gray_pixels(path: Path, width: int = 320) -> tuple[list[list[int]], int, int]:
    with Image.open(path) as source:
        image = source.convert("L")
        if image.width > width:
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        pixels = list(image.getdata())
        return ([pixels[y * image.width:(y + 1) * image.width]
                 for y in range(image.height)], image.width, image.height)


def _patch_error(frame: list[list[int]], template: list[list[int]],
                 x: int, y: int) -> float:
    radius_y = len(template) // 2
    radius_x = len(template[0]) // 2
    total = 0
    count = 0
    for dy in range(-radius_y, radius_y + 1):
        row = frame[y + dy]
        target = template[dy + radius_y]
        for dx in range(-radius_x, radius_x + 1):
            total += abs(row[x + dx] - target[dx + radius_x])
            count += 1
    return total / max(1, count)


def track_point(video_path: Path, *, x: float, y: float, start: float = 0.0,
                duration: float = 8.0, sample_fps: float = 2.0,
                max_frames: int = 120) -> dict[str, Any]:
    """Track a normalized point and return source-time normalized keyframes."""
    if not video_path.is_file():
        raise MotionTrackingError("Video file was not found.")
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise MotionTrackingError("Tracking point coordinates must be between 0 and 1.")
    if not (0 <= start <= 3600 and 0.5 <= duration <= 60):
        raise MotionTrackingError("Tracking range must start within one hour and last 0.5 to 60 seconds.")
    if not (0.5 <= sample_fps <= 5):
        raise MotionTrackingError("Tracking sample rate must be between 0.5 and 5 frames per second.")
    if not (2 <= max_frames <= 120):
        raise MotionTrackingError("Tracking is limited to 2 to 120 sampled frames.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MotionTrackingError("FFmpeg is required for motion tracking.")
    frame_count = min(max_frames, int(duration * sample_fps) + 1)
    with tempfile.TemporaryDirectory(prefix="flexy-track-") as directory:
        pattern = str(Path(directory) / "frame-%04d.jpg")
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(video_path),
            "-vf", f"fps={sample_fps},scale=320:-2",
            "-frames:v", str(frame_count), "-q:v", "4", pattern,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise MotionTrackingError("Motion tracking frame extraction timed out.") from exc
        if result.returncode != 0:
            raise MotionTrackingError("FFmpeg could not extract tracking frames.")
        paths = sorted(Path(directory).glob("frame-*.jpg"))
        if len(paths) < 2:
            raise MotionTrackingError("At least two video frames are required for tracking.")

        first, width, height = _gray_pixels(paths[0])
        px = min(width - 8, max(7, round(x * (width - 1))))
        py = min(height - 8, max(7, round(y * (height - 1))))
        radius = 5
        template = [row[px-radius:px+radius+1]
                    for row in first[py-radius:py+radius+1]]
        keyframes = [{"time": round(start, 3), "x": round(px / (width - 1), 6),
                      "y": round(py / (height - 1), 6), "confidence": 1.0}]
        previous_x, previous_y = px, py
        search_radius = 24
        for index, frame_path in enumerate(paths[1:], start=1):
            frame, current_width, current_height = _gray_pixels(frame_path)
            if current_width != width or current_height != height:
                break
            best = (float("inf"), previous_x, previous_y)
            for candidate_y in range(max(radius, previous_y-search_radius),
                                     min(height-radius, previous_y+search_radius+1), 2):
                for candidate_x in range(max(radius, previous_x-search_radius),
                                         min(width-radius, previous_x+search_radius+1), 2):
                    error = _patch_error(frame, template, candidate_x, candidate_y)
                    if error < best[0]:
                        best = (error, candidate_x, candidate_y)
            confidence = max(0.0, min(1.0, 1.0 - best[0] / 96.0))
            if confidence < 0.25:
                break
            _, previous_x, previous_y = best
            template = [row[previous_x-radius:previous_x+radius+1]
                        for row in frame[previous_y-radius:previous_y+radius+1]]
            keyframes.append({
                "time": round(start + index / sample_fps, 3),
                "x": round(previous_x / (width - 1), 6),
                "y": round(previous_y / (height - 1), 6),
                "confidence": round(confidence, 4),
            })
        return {
            "tracking_method": "local_patch_matching",
            "semantic_recognition": False,
            "sample_fps": sample_fps,
            "frame_count": len(keyframes),
            "complete": len(keyframes) == len(paths),
            "keyframes": keyframes,
            "notice": "Tracks a selected visual patch. Fast motion, occlusion, scene cuts, or similar-looking areas can reduce accuracy; review keyframes before applying.",
        }
