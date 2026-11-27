"""FFmpeg EBU R128 loudness and true-peak analysis for uploaded audio/video."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class AudioAnalysisError(ValueError):
    """Raised when loudness analysis cannot be completed."""


def _metric(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


def analyze_loudness(path: Path) -> dict[str, Any]:
    """Measure integrated LUFS, loudness range and true peak using ebur128.

    FFmpeg writes the EBU R128 summary to stderr. Values may be unavailable for
    extremely short or silent files; those are returned as null, not fabricated.
    """
    executable = shutil.which("ffmpeg")
    if not executable:
        raise AudioAnalysisError("FFmpeg is required for EBU R128 loudness analysis.")
    if not path.is_file():
        raise AudioAnalysisError("The media file is missing.")
    command = [executable, "-hide_banner", "-nostats", "-i", str(path),
               "-filter_complex", "ebur128=peak=true", "-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioAnalysisError("Audio loudness analysis timed out.") from exc
    output = (result.stderr or "") + "\n" + (result.stdout or "")
    if result.returncode != 0 and "Integrated loudness:" not in output:
        raise AudioAnalysisError("FFmpeg could not analyse this media's audio stream.")

    # ebur128 emits periodic live measurements as well as a final summary.
    # Restrict parsing to the final summary so a mid-stream reading is never
    # mistaken for the whole-file integrated loudness or true peak.
    summary_markers = list(re.finditer(r"^\s*Summary:\s*$", output, flags=re.IGNORECASE | re.MULTILINE))
    if summary_markers:
        output = output[summary_markers[-1].end():]
    else:
        integrated_markers = list(re.finditer(r"^\s*Integrated loudness:\s*$", output, flags=re.IGNORECASE | re.MULTILINE))
        if integrated_markers:
            output = output[integrated_markers[-1].start():]

    integrated = _metric(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", output)
    loudness_range = _metric(r"^\s*LRA:\s*(\d+(?:\.\d+)?)\s*LU", output)
    true_peak = _metric(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", output)
    if integrated is None and true_peak is None and "Integrated loudness:" not in output:
        raise AudioAnalysisError("FFmpeg returned no EBU R128 measurements.")

    return {
        "standard": "EBU R128",
        "integrated_lufs": integrated,
        "loudness_range_lu": loudness_range,
        "true_peak_dbfs": true_peak,
        "measurements_available": any(v is not None for v in (integrated, loudness_range, true_peak)),
        "notice": "Measurements describe the source. No normalization or audio changes were applied.",
    }


_BEAT_SAMPLE_RATE = 11025
_BEAT_WINDOW_SAMPLES = 220  # approximately 20 ms


def analyze_beats(path: Path, *, max_duration_seconds: int = 1800) -> dict[str, Any]:
    """Detect candidate musical beats from decoded audio using onset strength.

    This is a lightweight signal-processing detector, not an ML music model.
    It reports candidate beat timestamps and an estimated tempo only when the
    onset spacing supports a plausible, reasonably stable pulse.
    """
    executable = shutil.which("ffmpeg")
    if not executable:
        raise AudioAnalysisError("FFmpeg is required for automatic beat detection.")
    if not path.is_file():
        raise AudioAnalysisError("The media file is missing.")
    if not 1 <= max_duration_seconds <= 1800:
        raise AudioAnalysisError("Beat analysis duration must be between 1 and 1800 seconds.")

    command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin",
               "-i", str(path), "-t", str(max_duration_seconds), "-vn",
               "-ac", "1", "-ar", str(_BEAT_SAMPLE_RATE), "-f", "s16le", "pipe:1"]
    try:
        result = subprocess.run(command, capture_output=True, timeout=240, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioAnalysisError("Automatic beat detection timed out.") from exc
    if result.returncode != 0 or not result.stdout:
        raise AudioAnalysisError("FFmpeg could not decode an audio stream for beat detection.")

    import array
    import math
    import statistics
    samples = array.array("h")
    usable = len(result.stdout) - (len(result.stdout) % 2)
    samples.frombytes(result.stdout[:usable])
    if not samples:
        raise AudioAnalysisError("The decoded audio contains no usable samples.")

    window = _BEAT_WINDOW_SAMPLES
    energies: list[float] = []
    for offset in range(0, len(samples) - window + 1, window):
        block = samples[offset:offset + window]
        energies.append(math.sqrt(sum(value * value for value in block) / window))
    if len(energies) < 25:
        return {"detector": "energy-onset-v1", "beats": [], "estimated_bpm": None,
                "confidence": 0.0, "duration_analyzed": len(samples) / _BEAT_SAMPLE_RATE,
                "notice": "Audio was too short to estimate a reliable beat grid."}

    # Positive energy changes approximate percussive onsets. Require a local
    # peak, a global noise-aware threshold, and a minimum 220 ms separation.
    novelty = [max(0.0, current - previous) for previous, current in zip(energies, energies[1:])]
    mean = statistics.fmean(novelty)
    deviation = statistics.pstdev(novelty)
    threshold = mean + 0.65 * deviation
    candidates: list[tuple[int, float]] = []
    for index in range(1, len(novelty) - 1):
        strength = novelty[index]
        if strength < threshold or strength <= novelty[index - 1] or strength < novelty[index + 1]:
            continue
        if candidates and (index - candidates[-1][0]) * (window / _BEAT_SAMPLE_RATE) < 0.22:
            if strength > candidates[-1][1]:
                candidates[-1] = (index, strength)
            continue
        candidates.append((index, strength))

    beat_times = [round(index * window / _BEAT_SAMPLE_RATE, 3) for index, _ in candidates]
    intervals = [right - left for left, right in zip(beat_times, beat_times[1:])
                 if 0.25 <= right - left <= 1.5]
    bpm = None
    confidence = 0.0
    if len(intervals) >= 3:
        median_interval = statistics.median(intervals)
        bpm = round(60.0 / median_interval, 1)
        spread = statistics.median(abs(value - median_interval) for value in intervals)
        confidence = round(max(0.0, min(1.0, 1.0 - spread / max(median_interval, 0.001))), 2)
        if confidence < 0.35 or not 40 <= bpm <= 240:
            bpm = None

    return {
        "detector": "energy-onset-v1",
        "beats": beat_times[:2000],
        "estimated_bpm": bpm,
        "confidence": confidence if bpm is not None else 0.0,
        "duration_analyzed": round(len(samples) / _BEAT_SAMPLE_RATE, 3),
        "truncated": len(samples) / _BEAT_SAMPLE_RATE >= max_duration_seconds - 0.05,
        "notice": "Beat timestamps are signal-based candidates. Tempo is omitted when the pulse is unclear; review before applying synchronization.",
    }
