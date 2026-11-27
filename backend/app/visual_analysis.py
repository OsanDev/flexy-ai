"""Lightweight, deterministic visual descriptors for scene thumbnails.

This is not semantic object recognition. It measures image properties locally and
returns transparent descriptors until a real vision model is configured.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter, ImageStat


def describe_frame(image_path: Path) -> dict[str, object]:
    if not image_path.is_file():
        raise ValueError("Scene thumbnail was not found.")
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            small = image.resize((min(160, width), max(1, round(height * min(160, width) / width))))
            stats = ImageStat.Stat(small)
            mean = stats.mean
            stddev = stats.stddev
            luminance = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
            contrast = sum(stddev) / 3
            # These are explainable pixel-level composition signals, not semantic
            # judgments about subjects, actions, or whether a shot is meaningful.
            gray = small.convert("L")
            edge_strength = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255
            channel_spread = max(mean) - min(mean)
            colorfulness = min(1.0, channel_spread / 128)
            contrast_score = min(1.0, contrast / 96)
            visual_interest = min(1.0, max(0.0,
                0.45 * contrast_score + 0.35 * edge_strength + 0.20 * colorfulness))
            brightness = "dark" if luminance < 65 else "bright" if luminance > 190 else "balanced"
            contrast_label = "low" if contrast < 35 else "high" if contrast > 75 else "medium"
            colors = [round(value) for value in mean]
            return {
                "width": width,
                "height": height,
                "brightness": brightness,
                "contrast": contrast_label,
                "average_rgb": colors,
                "edge_strength": round(edge_strength, 4),
                "colorfulness": round(colorfulness, 4),
                "visual_interest": round(visual_interest, 4),
                "analysis_type": "pixel_statistics",
                "semantic_recognition": False,
                "notice": "Visual properties only; no people, objects, or actions have been identified.",
            }
    except (OSError, ValueError) as exc:
        raise ValueError("Scene thumbnail could not be analyzed.") from exc


def representative_scene_timestamp(
    scenes: list[dict[str, float | int]], index: int, duration: float | None = None
) -> float:
    """Return a stable interior sample time for a scene, not its cut boundary."""
    if not 0 <= index < len(scenes):
        raise IndexError("Scene index is out of range.")
    start = float(scenes[index]["start"])
    if start < 0:
        raise ValueError("Scene start cannot be negative.")
    next_start = float(scenes[index + 1]["start"]) if index + 1 < len(scenes) else None
    end = next_start if next_start is not None else duration
    if end is None or end <= start:
        return start
    # Sample at 50% of the shot. For extremely short shots, stay inside the
    # detected interval while avoiding the exact transition timestamp.
    return round(start + (end - start) * 0.5, 3)
