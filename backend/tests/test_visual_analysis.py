from pathlib import Path

from PIL import Image

from app.visual_analysis import describe_frame


def test_describe_frame_returns_transparent_pixel_metadata(tmp_path: Path):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (320, 180), (220, 220, 220)).save(frame)
    result = describe_frame(frame)
    assert result["width"] == 320
    assert result["height"] == 180
    assert result["brightness"] == "bright"
    assert result["analysis_type"] == "pixel_statistics"
    assert result["semantic_recognition"] is False


def test_describe_frame_rejects_missing_file(tmp_path: Path):
    try:
        describe_frame(tmp_path / "missing.jpg")
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("missing thumbnail should fail")


def test_visual_interest_is_bounded_and_uses_only_pixel_evidence(tmp_path: Path):
    flat = tmp_path / "flat.png"
    textured = tmp_path / "textured.png"
    Image.new("RGB", (160, 90), (120, 120, 120)).save(flat)
    image = Image.new("RGB", (160, 90))
    pixels = image.load()
    for y in range(90):
        for x in range(160):
            pixels[x, y] = (240, 30, 30) if (x // 8 + y // 8) % 2 else (20, 40, 220)
    image.save(textured)

    flat_result = describe_frame(flat)
    textured_result = describe_frame(textured)
    assert 0 <= flat_result["visual_interest"] <= 1
    assert 0 <= textured_result["visual_interest"] <= 1
    assert textured_result["visual_interest"] > flat_result["visual_interest"]
    assert flat_result["semantic_recognition"] is False
    assert "subject_presence" not in textured_result
    assert "motion_suitability" not in textured_result


def test_representative_scene_timestamp_samples_inside_shot():
    from app.visual_analysis import representative_scene_timestamp

    scenes = [{"start": 2.0}, {"start": 6.0}, {"start": 10.0}]
    assert representative_scene_timestamp(scenes, 0, 14.0) == 4.0
    assert representative_scene_timestamp(scenes, 1, 14.0) == 8.0
    assert representative_scene_timestamp(scenes, 2, 14.0) == 12.0


def test_representative_scene_timestamp_handles_unknown_or_tiny_duration():
    from app.visual_analysis import representative_scene_timestamp

    assert representative_scene_timestamp([{"start": 3.0}], 0, None) == 3.0
    assert representative_scene_timestamp([{"start": 3.0}, {"start": 3.0}], 0, 4.0) == 3.0


def test_representative_scene_timestamp_rejects_invalid_index():
    from app.visual_analysis import representative_scene_timestamp

    try:
        representative_scene_timestamp([], 0, 10.0)
    except IndexError:
        pass
    else:
        raise AssertionError("invalid scene index should fail")
