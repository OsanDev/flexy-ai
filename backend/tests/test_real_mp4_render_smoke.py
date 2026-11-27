"""A small real-FFmpeg integration check for the MP4 render path."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.rendering import probe_video_encoders, render_mp4


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are not installed")
def test_real_ffmpeg_render_produces_probeable_mp4(tmp_path: Path):
    capabilities = probe_video_encoders()
    if "libx264" not in capabilities.get("available", []):
        pytest.skip("This FFmpeg build does not include the libx264 encoder")

    source = tmp_path / "source.mp4"
    output = tmp_path / "flexy-export.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    progress: list[int] = []
    render_mp4(
        {
            "clips": [{
                "path": str(source), "source_start": 0.0, "duration": 1.0,
                "timeline_start": 0.0, "track_index": 0,
                "transition": "none", "is_image": False,
            }],
            "audio_clips": [], "captions": [], "video_duration": 1.0,
            "width": 320, "height": 240, "frame_rate": 24,
            "video_bitrate": "2M",
        },
        output,
        progress_callback=progress.append,
    )

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=format_name,duration,size:stream=codec_name,width,height,r_frame_rate",
            "-of", "json", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    report = json.loads(probe.stdout)
    video = next(stream for stream in report["streams"] if stream.get("codec_name"))
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (320, 240)
    assert video["r_frame_rate"] == "24/1"
    assert "mp4" in report["format"]["format_name"]
    assert output.stat().st_size > 1_000
    assert progress[-1] == 100


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are not installed")
def test_real_ffmpeg_render_applies_configurable_dialogue_ducking(tmp_path: Path):
    if "libx264" not in probe_video_encoders().get("available", []):
        pytest.skip("This FFmpeg build does not include the libx264 encoder")
    video = tmp_path / "picture.mp4"
    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.wav"
    output = tmp_path / "ducked-export.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True, timeout=30)
    for path, frequency in ((voice, 440), (music, 220)):
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=2:sample_rate=48000",
            "-c:a", "pcm_s16le", str(path),
        ], check=True, capture_output=True, timeout=30)

    render_mp4({
        "clips": [{
            "path": str(video), "source_start": 0.0, "duration": 2.0,
            "timeline_start": 0.0, "track_index": 0,
            "transition": "none", "is_image": False,
        }],
        "audio_clips": [
            {"path": str(voice), "source_start": 0.0, "duration": 2.0,
             "timeline_start": 0.0, "volume": 1.0, "fade_in": 0.0, "fade_out": 0.0, "role": "dialogue"},
            {"path": str(music), "source_start": 0.0, "duration": 2.0,
             "timeline_start": 0.0, "volume": 0.5, "fade_in": 0.0, "fade_out": 0.0, "role": "music"},
        ],
        "captions": [], "video_duration": 2.0,
        "width": 320, "height": 240, "frame_rate": 24,
        "video_bitrate": "2M", "ducking": True,
        "ducking_settings": {"threshold_db": -30, "ratio": 5, "attack_ms": 35, "release_ms": 700},
    }, output)

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
        "-of", "json", str(output),
    ], check=True, capture_output=True, text=True, timeout=15)
    streams = json.loads(probe.stdout)["streams"]
    assert any(stream.get("codec_type") == "video" and stream.get("codec_name") == "h264" for stream in streams)
    assert any(stream.get("codec_type") == "audio" and stream.get("codec_name") == "aac" for stream in streams)
    assert output.stat().st_size > 1_000


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are not installed")
def test_real_ffmpeg_render_applies_audio_volume_keyframes(tmp_path: Path):
    if "libx264" not in probe_video_encoders().get("available", []):
        pytest.skip("This FFmpeg build does not include the libx264 encoder")
    video = tmp_path / "picture.mp4"
    audio = tmp_path / "music.wav"
    output = tmp_path / "automated-volume.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True, timeout=30)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=48000",
        "-c:a", "pcm_s16le", str(audio),
    ], check=True, capture_output=True, timeout=30)
    render_mp4({
        "clips": [{"path": str(video), "source_start": 0.0, "duration": 2.0,
                   "timeline_start": 0.0, "track_index": 0, "transition": "none", "is_image": False}],
        "audio_clips": [{"path": str(audio), "source_start": 0.0, "duration": 2.0,
                         "timeline_start": 0.0, "volume": 0.8, "fade_in": 0.0, "fade_out": 0.0,
                         "role": "music", "volume_keyframes": [
                             {"time": 0.0, "volume": 0.2}, {"time": 1.0, "volume": 1.0},
                             {"time": 2.0, "volume": 0.4},
                         ]}],
        "captions": [], "video_duration": 2.0, "width": 320, "height": 240,
        "frame_rate": 24, "video_bitrate": "2M",
    }, output)
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
        "-of", "json", str(output),
    ], check=True, capture_output=True, text=True, timeout=15)
    streams = json.loads(probe.stdout)["streams"]
    assert any(stream.get("codec_type") == "audio" and stream.get("codec_name") == "aac" for stream in streams)
    assert output.stat().st_size > 1_000


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are not installed")
def test_real_ffmpeg_render_applies_audio_bus_and_master_mutes(tmp_path: Path):
    if "libx264" not in probe_video_encoders().get("available", []):
        pytest.skip("This FFmpeg build does not include the libx264 encoder")
    video = tmp_path / "picture.mp4"
    audio = tmp_path / "music.wav"
    output = tmp_path / "muted-bus.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc2=size=320x240:rate=24:duration=1", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True, timeout=30)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1:sample_rate=48000", "-c:a", "pcm_s16le",
                    str(audio)], check=True, capture_output=True, timeout=30)
    render_mp4({
        "clips": [{"path": str(video), "source_start": 0, "duration": 1, "timeline_start": 0,
                   "track_index": 0, "transition": "none", "is_image": False}],
        "audio_clips": [{"path": str(audio), "source_start": 0, "duration": 1, "timeline_start": 0,
                         "volume": 1, "fade_in": 0, "fade_out": 0, "role": "music", "bus": "music"}],
        "audio_mixer": {"music": {"gain": 1, "muted": True}, "master": {"gain": 1, "muted": False}},
        "captions": [], "video_duration": 1, "width": 320, "height": 240,
        "frame_rate": 24, "video_bitrate": "2M",
    }, output)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
                            "-of", "json", str(output)], check=True, capture_output=True, text=True, timeout=15)
    streams = json.loads(probe.stdout)["streams"]
    assert any(stream.get("codec_type") == "audio" and stream.get("codec_name") == "aac" for stream in streams)
    # The stream remains present, but the muted bus is silent in the encoded output.
    measured = subprocess.run(["ffmpeg", "-hide_banner", "-v", "info", "-i", str(output), "-vn", "-af", "volumedetect",
                              "-f", "null", "-"], capture_output=True, text=True, timeout=15)
    import re
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", measured.stderr)
    assert match and float(match.group(1)) <= -90
