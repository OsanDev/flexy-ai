from pathlib import Path
from unittest.mock import patch

import pytest

from app.rendering import RenderValidationError, _captions_to_ass, validate_render_graph

ROOT = Path(__file__).resolve().parents[2]


def _validate(style):
    media_dir = Path("/tmp/flexy-v469-animation")
    media_dir.mkdir(exist_ok=True)
    (media_dir / "clip.mp4").write_bytes(b"video")
    try:
        with patch("app.rendering.storage.get_media", return_value={"stored_name": "clip.mp4", "mime_type": "video/mp4"}), patch("app.rendering.storage.MEDIA_DIR", media_dir):
            return validate_render_graph({"clips": [{"media_id": "v", "duration": 4}],
                "captions": [{"text": "One two three", "start": 1, "duration": 3, "style": style}]})
    finally:
        (media_dir / "clip.mp4").unlink(missing_ok=True)
        media_dir.rmdir()


def _ass(animation):
    return _captions_to_ass([{"text": "One two three", "start": 1, "duration": 3,
        "style": {"alignment": "center", "position": "bottom", "vertical_offset": 7,
            "font_size": 30, "color": "#ffffff", "background_color": "#000000b8",
            "outline_color": "#000000", "outline_width": 1, "shadow_color": "#000000",
            "shadow_blur": 2, "bold": True, "animation": animation, "animation_duration": 0.6}}], 1080, 1920)


def test_render_validation_preserves_supported_animation_and_duration():
    style = _validate({"animation": "pop", "animationDuration": 0.8})["captions"][0]["style"]
    assert style["animation"] == "pop"
    assert style["animation_duration"] == 0.8


def test_invalid_animation_and_duration_are_rejected():
    with pytest.raises(RenderValidationError):
        _validate({"animation": "spin"})
    with pytest.raises(RenderValidationError):
        _validate({"animation": "fade", "animationDuration": 4})


def test_word_reveal_exports_progressive_timed_dialogue_events():
    ass = _ass("word")
    events = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 3
    assert "0:00:01.00,0:00:04.00" in events[0]
    assert "One" in events[0] and "One two" in events[1]
    assert "One two three" in events[2]


def test_word_reveal_uses_animation_duration_then_holds_full_caption():
    ass = _ass("word")
    events = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert "0:00:01.00,0:00:04.00" in events[0]
    assert "0:00:01.20,0:00:04.00" in events[1]
    assert "0:00:01.40,0:00:04.00" in events[2]


def test_karaoke_exports_word_timing_tags():
    ass = _ass("karaoke")
    events = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 1
    assert "&H006de6ff&" in ass
    assert r"{\kf100}One {\kf100}two {\kf100}three" in events[0]


@pytest.mark.parametrize("animation,tag", [
    ("fade", r"\fad(60,0)"),
    ("pop", r"\fscx70\fscy70\t(0,60,\fscx100\fscy100)"),
    ("slide", r"\move(540,1671,540,1786,0,60)"),
])
def test_entrance_animations_export_ass_override_tags(animation, tag):
    assert tag in _ass(animation)


def test_static_caption_remains_static_and_uses_no_animation_override():
    ass = _ass("none")
    event = next(line for line in ass.splitlines() if line.startswith("Dialogue:"))
    assert r"\fad(" not in event and r"\move(" not in event and r"\fscx70" not in event


def test_render_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (ROOT / "frontend-reference" / "apps" / "web" / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
