from pathlib import Path
from unittest.mock import patch
import subprocess

import pytest

from app.scene_detection import SceneDetectionError, detect_scenes


def test_detects_monotonic_scene_timestamps(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    completed = subprocess.CompletedProcess([], 0, "", "[Parsed_showinfo] n:0 pts_time:1.250\n[Parsed_showinfo] n:1 pts_time:3.500\n")
    with patch("app.scene_detection.shutil.which", return_value="ffmpeg"), \
         patch("app.scene_detection.subprocess.run", return_value=completed) as run:
        assert detect_scenes(video) == [
            {"index": 1, "start": 1.25}, {"index": 2, "start": 3.5}
        ]
        command = run.call_args.args[0]
        assert command[command.index("-frames:v") + 1] == "500"


def test_rejects_bad_threshold(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with pytest.raises(SceneDetectionError, match="Threshold"):
        detect_scenes(video, threshold=1.5)


def test_reports_missing_ffmpeg(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with patch("app.scene_detection.shutil.which", return_value=None):
        with pytest.raises(SceneDetectionError, match="FFmpeg is required"):
            detect_scenes(video)


def test_extracts_scene_thumbnail(tmp_path):
    from app.scene_detection import extract_scene_thumbnail

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "thumbs" / "scene.jpg"

    def fake_run(command, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch("app.scene_detection.shutil.which", return_value="ffmpeg"), \
         patch("app.scene_detection.subprocess.run", side_effect=fake_run):
        assert extract_scene_thumbnail(video, 2.5, output) == output
        assert output.read_bytes() == b"jpeg"


def test_rejects_negative_thumbnail_timestamp(tmp_path):
    from app.scene_detection import extract_scene_thumbnail

    with pytest.raises(SceneDetectionError, match="cannot be negative"):
        extract_scene_thumbnail(tmp_path / "clip.mp4", -1, tmp_path / "thumb.jpg")


def test_scene_detection_caps_ffmpeg_frame_work(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    completed = subprocess.CompletedProcess([], 0, "", "")
    with patch("app.scene_detection.shutil.which", return_value="ffmpeg"), \
         patch("app.scene_detection.subprocess.run", return_value=completed) as run:
        assert detect_scenes(video, max_scenes=7) == []
        command = run.call_args.args[0]
        assert command[command.index("-frames:v") + 1] == "7"


def test_rejects_out_of_range_scene_limit(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with pytest.raises(SceneDetectionError, match="max_scenes"):
        detect_scenes(video, max_scenes=2001)
