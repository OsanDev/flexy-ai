import pytest
from app.recommendations import build_recommendations


def test_scene_pacing_recommendation_for_dynamic_style():
    result = build_recommendations(
        scenes=[{"start": 0}, {"start": 9}, {"start": 18}], duration=30, style="dynamic"
    )
    assert any(item["id"] == "review-long-shots" for item in result["recommendations"])
    assert result["engine"] == "evidence_rules_v1"


def test_dialogue_pause_is_reported_without_auto_trimming():
    result = build_recommendations(transcript_segments=[
        {"start": 0, "end": 1, "text": "Hello"},
        {"start": 4, "end": 5, "text": "Again"},
    ])
    item = next(x for x in result["recommendations"] if x["id"] == "review-dialogue-pauses")
    assert item["evidence"]["gaps"][0]["seconds"] == 3
    assert "Listen before trimming" in item["detail"]


def test_missing_evidence_is_explicit():
    result = build_recommendations()
    ids = {item["id"] for item in result["recommendations"]}
    assert "detect-scenes-first" in ids
    assert "add-transcript" in ids


def test_invalid_style_rejected():
    with pytest.raises(ValueError):
        build_recommendations(style="viral")
