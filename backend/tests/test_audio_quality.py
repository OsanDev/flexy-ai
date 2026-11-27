from pathlib import Path
from unittest.mock import patch

import pytest

from app.audio_quality import AudioAnalysisError, analyze_loudness, analyze_beats


def test_parses_ebu_r128_summary(tmp_path: Path):
    source = tmp_path / "tone.wav"
    source.write_bytes(b"audio")
    completed = type("Completed", (), {
        "returncode": 0,
        "stdout": "",
        "stderr": """[Parsed_ebur128_0 @ 0x1]\nIntegrated loudness:\n  I:         -18.4 LUFS\n  Threshold: -28.5 LUFS\nLoudness range:\n  LRA:         3.2 LU\n  Threshold: -38.0 LUFS\nTrue peak:\n  Peak:       -1.1 dBFS\n""",
    })()
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", return_value=completed
    ):
        result = analyze_loudness(source)
    assert result["integrated_lufs"] == -18.4
    assert result["loudness_range_lu"] == 3.2
    assert result["true_peak_dbfs"] == -1.1
    assert result["standard"] == "EBU R128"


def test_reports_missing_ffmpeg(tmp_path: Path):
    with patch("app.audio_quality.shutil.which", return_value=None):
        with pytest.raises(AudioAnalysisError, match="FFmpeg is required"):
            analyze_loudness(tmp_path / "tone.wav")


def test_reports_timeout(tmp_path: Path):
    import subprocess
    source = tmp_path / "tone.wav"
    source.write_bytes(b"audio")
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 180)
    ):
        with pytest.raises(AudioAnalysisError, match="timed out"):
            analyze_loudness(source)


def test_uses_final_summary_not_periodic_live_readings(tmp_path: Path):
    source = tmp_path / "tone.wav"
    source.write_bytes(b"audio")
    completed = type("Completed", (), {
        "returncode": 0,
        "stdout": "",
        "stderr": """[Parsed_ebur128_0 @ 0x1]
 t: 1.0  M: -20.0 S: -18.0 I: -19.0 LUFS
 t: 2.0  M: -17.0 S: -16.0 I: -18.0 LUFS
 Summary:
 Integrated loudness:
   I: -14.2 LUFS
 Loudness range:
   LRA: 5.6 LU
 True peak:
   Peak: -0.8 dBFS
""",
    })()
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", return_value=completed
    ):
        result = analyze_loudness(source)
    assert result["integrated_lufs"] == -14.2
    assert result["loudness_range_lu"] == 5.6
    assert result["true_peak_dbfs"] == -0.8


def test_uses_last_summary_when_ffmpeg_emits_multiple_summaries(tmp_path: Path):
    source = tmp_path / "tone.wav"
    source.write_bytes(b"audio")
    completed = type("Completed", (), {
        "returncode": 0,
        "stdout": "",
        "stderr": """Summary:
Integrated loudness:
 I: -20.0 LUFS
Loudness range:
 LRA: 2.0 LU
True peak:
 Peak: -3.0 dBFS
Summary:
Integrated loudness:
 I: -15.0 LUFS
Loudness range:
 LRA: 4.0 LU
True peak:
 Peak: -1.0 dBFS
""",
    })()
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", return_value=completed
    ):
        result = analyze_loudness(source)
    assert result["integrated_lufs"] == -15.0
    assert result["loudness_range_lu"] == 4.0
    assert result["true_peak_dbfs"] == -1.0


def test_detects_regular_energy_onsets_and_estimates_tempo(tmp_path: Path):
    import array
    import subprocess
    source = tmp_path / "music.wav"
    source.write_bytes(b"audio")
    sample_rate = 11025
    samples = array.array("h", [0] * (sample_rate * 5))
    # Repeated percussive blocks at 120 BPM, beginning at 0.25 seconds.
    for start in (0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75, 4.25, 4.75):
        offset = int(start * sample_rate)
        samples[offset:offset + 220] = array.array("h", [12000] * 220)
    completed = subprocess.CompletedProcess([], 0, samples.tobytes(), b"")
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", return_value=completed
    ):
        result = analyze_beats(source)
    assert result["detector"] == "energy-onset-v1"
    assert result["beats"]
    assert abs(result["estimated_bpm"] - 120.0) <= 1.0
    assert result["confidence"] >= 0.35


def test_beat_detector_returns_no_tempo_for_silence(tmp_path: Path):
    import array
    import subprocess
    source = tmp_path / "silence.wav"
    source.write_bytes(b"audio")
    completed = subprocess.CompletedProcess([], 0, array.array("h", [0] * 33075).tobytes(), b"")
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", return_value=completed
    ):
        result = analyze_beats(source)
    assert result["beats"] == []
    assert result["estimated_bpm"] is None
    assert result["confidence"] == 0.0


def test_beat_detector_requires_ffmpeg(tmp_path: Path):
    with patch("app.audio_quality.shutil.which", return_value=None):
        with pytest.raises(AudioAnalysisError, match="FFmpeg is required"):
            analyze_beats(tmp_path / "missing.wav")


def test_beat_detector_reports_timeout(tmp_path: Path):
    import subprocess
    source = tmp_path / "music.wav"
    source.write_bytes(b"audio")
    with patch("app.audio_quality.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "app.audio_quality.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 240)
    ):
        with pytest.raises(AudioAnalysisError, match="timed out"):
            analyze_beats(source)
