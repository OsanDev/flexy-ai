"""Extract trustworthy media metadata with ffprobe after upload."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MediaProbeError(ValueError):
    """Raised when an uploaded file cannot be inspected as media."""


class MediaProbeUnavailable(RuntimeError):
    """Raised when the server cannot validate uploads because ffprobe is missing."""


def probe_media(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise MediaProbeUnavailable("Media inspection is unavailable because FFprobe is not installed.")
    command = [
        executable, "-v", "error", "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError("Media inspection timed out.") from exc
    if result.returncode != 0:
        raise MediaProbeError("The uploaded file could not be read as valid media.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("Media inspection returned invalid metadata.") from exc
    streams = payload.get("streams") or []
    if not streams:
        raise MediaProbeError("The uploaded file contains no readable media stream.")
    fmt = payload.get("format") or {}
    try:
        duration = float(fmt.get("duration")) if fmt.get("duration") is not None else None
    except (TypeError, ValueError):
        duration = None
    summary: dict[str, Any] = {
        "probe_available": True,
        "format_name": str(fmt.get("format_name", ""))[:120],
        "duration": duration if duration is not None and duration >= 0 else None,
        "streams": [],
    }
    for stream in streams[:8]:
        item = {key: stream[key] for key in (
            "codec_type", "codec_name", "width", "height", "avg_frame_rate", "sample_rate", "channels"
        ) if key in stream}
        summary["streams"].append(item)
    return summary
