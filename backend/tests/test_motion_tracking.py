from pathlib import Path
from unittest.mock import patch
import subprocess

import pytest
from PIL import Image, ImageDraw

from app.motion_tracking import MotionTrackingError, track_point


def _frame(path: Path, left: int) -> None:
    image = Image.new("RGB", (96, 64), "black")
    draw = ImageDraw.Draw(image)
    draw.rectangle((left, 24, left + 12, 36), fill="white")
    draw.rectangle((left + 2, 26, left + 4, 32), fill="red")
    image.save(path)


def test_tracks_a_moving_visual_patch(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")

    def fake_run(command, **kwargs):
        pattern = command[-1]
        folder = Path(pattern).parent
        _frame(folder / "frame-0001.jpg", 24)
        _frame(folder / "frame-0002.jpg", 30)
        _frame(folder / "frame-0003.jpg", 36)
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch("app.motion_tracking.shutil.which", return_value="ffmpeg"), \
         patch("app.motion_tracking.subprocess.run", side_effect=fake_run):
        result = track_point(video, x=24 / 95, y=30 / 63, duration=1, sample_fps=1)

    assert result["tracking_method"] == "local_patch_matching"
    assert result["semantic_recognition"] is False
    assert result["frame_count"] == 3
    assert result["complete"] is True
    assert result["keyframes"][-1]["x"] > result["keyframes"][0]["x"]
    assert all(0 <= point["confidence"] <= 1 for point in result["keyframes"])


def test_rejects_invalid_point_coordinates(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with pytest.raises(MotionTrackingError, match="coordinates"):
        track_point(video, x=1.2, y=0.5)


def test_requires_ffmpeg(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with patch("app.motion_tracking.shutil.which", return_value=None):
        with pytest.raises(MotionTrackingError, match="FFmpeg is required"):
            track_point(video, x=0.5, y=0.5)


def test_rejects_missing_video(tmp_path):
    with pytest.raises(MotionTrackingError, match="not found"):
        track_point(tmp_path / "missing.mp4", x=0.5, y=0.5)
