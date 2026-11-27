"""Generate lightweight media-bin previews using FFmpeg."""
from __future__ import annotations

import array
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MediaPreviewError(ValueError):
    pass


def audio_waveform(path: Path, *, points: int = 128, max_seconds: int = 900) -> dict[str, Any]:
    """Return normalized peak buckets from at most 15 minutes of decoded audio."""
    if not path.is_file():
        raise MediaPreviewError("Stored media file is missing.")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise MediaPreviewError("FFmpeg is required to generate audio waveforms.")
    command = [executable, "-hide_banner", "-loglevel", "error", "-i", str(path),
               "-t", str(max_seconds), "-vn", "-ac", "1", "-ar", "8000",
               "-f", "s16le", "pipe:1"]
    try:
        result = subprocess.run(command, capture_output=True, timeout=45, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaPreviewError("Audio waveform generation timed out.") from exc
    if result.returncode != 0 or not result.stdout:
        raise MediaPreviewError("FFmpeg could not decode audio from this file.")
    usable = len(result.stdout) - (len(result.stdout) % 2)
    samples = array.array("h")
    samples.frombytes(result.stdout[:usable])
    if not samples:
        raise MediaPreviewError("No audio samples were decoded.")
    bucket_count = min(points, len(samples))
    peaks: list[float] = []
    for index in range(bucket_count):
        start = index * len(samples) // bucket_count
        end = max(start + 1, (index + 1) * len(samples) // bucket_count)
        peak = max(abs(value) for value in samples[start:end])
        peaks.append(round(peak / 32768.0, 4))
    return {"points": peaks, "sample_rate": 8000,
            "analyzed_seconds": round(len(samples) / 8000, 2),
            "truncated": len(samples) >= max_seconds * 8000}
