from pathlib import Path
from unittest.mock import patch

import pytest

from app.rendering import (
    RenderValidationError, probe_video_encoders, select_video_encoder,
)


def test_auto_uses_portable_cpu_encoder_when_available():
    result = select_video_encoder(capabilities={"available": ["h264_nvenc", "libx264"]})
    assert result["encoder"] == "libx264"
    assert result["mode"] == "software"


def test_explicit_nvenc_is_selected_only_when_ffmpeg_lists_it():
    result = select_video_encoder("h264_nvenc", {"available": ["libx264", "h264_nvenc"]})
    assert result["encoder"] == "h264_nvenc"
    assert result["mode"] == "hardware"
    assert result["preset"] == "p4"


def test_explicit_missing_hardware_encoder_fails_with_available_list():
    with pytest.raises(RenderValidationError, match="not listed"):
        select_video_encoder("h264_nvenc", {"available": ["libx264"]})


def test_unknown_encoder_setting_is_rejected():
    with pytest.raises(RenderValidationError, match="FLEXY_VIDEO_ENCODER"):
        select_video_encoder("h264_magic", {"available": ["libx264"]})


def test_probe_parses_encoder_names_from_ffmpeg_output():
    fake = type("Result", (), {
        "returncode": 0,
        "stdout": " V....D libx264 H.264 / AVC\n V....D h264_nvenc NVIDIA NVENC",
        "stderr": "",
    })()
    with patch("app.rendering.shutil.which", return_value="/usr/bin/ffmpeg") as which_mock:
        with patch("app.rendering.subprocess.run", return_value=fake):
            result = probe_video_encoders()
    assert result["available"] == ["h264_nvenc", "libx264"]
    assert result["hardware"] == ["h264_nvenc"]


def test_preflight_reports_encoder_and_hardware_caveat():
    source = (Path(__file__).resolve().parents[1] / "app/render_preflight.py").read_text()
    assert "encoder_capabilities" in source
    assert "actual device/driver support" in source


def test_release_version_is_updated():
    root = Path(__file__).resolve().parents[2]
    main = (root / "backend/app/main.py").read_text()
    package = (root / "frontend-reference/apps/web/package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
