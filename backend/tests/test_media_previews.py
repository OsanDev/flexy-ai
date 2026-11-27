from __future__ import annotations

import array
from pathlib import Path
from unittest.mock import patch

import pytest

from app.media_previews import MediaPreviewError, audio_waveform


def test_audio_waveform_returns_bounded_normalized_peak_buckets(tmp_path: Path):
    media = tmp_path / "audio.wav"
    media.write_bytes(b"fixture")
    samples = array.array("h", [0, 8192, -16384, 32767] * 100)
    completed = type("Completed", (), {"returncode": 0, "stdout": samples.tobytes(), "stderr": b""})()
    with patch("app.media_previews.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.media_previews.subprocess.run", return_value=completed
    ):
        result = audio_waveform(media, points=8)
    assert len(result["points"]) == 8
    assert max(result["points"]) == 1.0
    assert all(0 <= value <= 1 for value in result["points"])
    assert result["sample_rate"] == 8000
    assert result["truncated"] is False


def test_audio_waveform_rejects_missing_file(tmp_path: Path):
    with pytest.raises(MediaPreviewError, match="missing"):
        audio_waveform(tmp_path / "missing.wav")


def test_audio_waveform_reports_missing_ffmpeg(tmp_path: Path):
    media = tmp_path / "audio.wav"
    media.write_bytes(b"fixture")
    with patch("app.media_previews.shutil.which", return_value=None):
        with pytest.raises(MediaPreviewError, match="FFmpeg"):
            audio_waveform(media)


def test_audio_waveform_rejects_decode_failure(tmp_path: Path):
    media = tmp_path / "audio.wav"
    media.write_bytes(b"fixture")
    completed = type("Completed", (), {"returncode": 1, "stdout": b"", "stderr": b"bad"})()
    with patch("app.media_previews.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.media_previews.subprocess.run", return_value=completed
    ):
        with pytest.raises(MediaPreviewError, match="decode"):
            audio_waveform(media)
