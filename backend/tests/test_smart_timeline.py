import pytest
from app.smart_timeline import build_smart_timeline


def test_builds_scene_aware_dynamic_first_cut_with_dialogue_evidence():
    result = build_smart_timeline(
        assets=[{"id": "v1", "type": "video", "duration": 12},
                {"id": "a1", "type": "audio", "duration": 20}],
        scenes=[{"index": 1, "start": 0}, {"index": 2, "start": 4}, {"index": 3, "start": 8}],
        transcript_segments=[{"start": 4.2, "end": 5.5, "text": "Here we go"}],
        target_duration=7, style="dynamic")
    assert result["engine"] == "scene_dialogue_rules_v1"
    assert len(result["clips"]) == 3
    assert result["clips"][1]["sourceStart"] == 4.2
    assert result["clips"][1]["evidence"]["contains_transcript"] is True
    assert result["audio_clips"][0]["volume"] == 0.35
    assert result["duration"] == 7


def test_no_video_returns_actionable_warning():
    result = build_smart_timeline([], [], [], 10)
    assert result["clips"] == []
    assert "Import at least one video" in result["warnings"][0]


def test_missing_scene_data_uses_explicit_fallback_warning():
    result = build_smart_timeline([{"id": "v", "type": "video", "duration": 6}], [], [], 10)
    assert result["clips"][0]["sourceStart"] == 0
    assert any("No scene boundaries" in warning for warning in result["warnings"])
    assert any("No valid transcript" in warning for warning in result["warnings"])


def test_invalid_duration_and_style_rejected():
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 0)
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 10, "viral")


def test_clips_are_non_overlapping_and_chronological():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 6}, {"start": 13}], [], 12, "balanced")
    for left, right in zip(result["clips"], result["clips"][1:]):
        assert left["start"] + left["duration"] <= right["start"]
        assert left["sourceStart"] < right["sourceStart"]


def test_dialogue_late_in_scene_anchors_selected_shot_near_speech():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 30}],
        [{"start": 0}, {"start": 10}],
        [{"start": 17.5, "end": 19.0, "text": "Important line"}],
        8, "balanced")
    selected = result["clips"][1]
    assert selected["sourceStart"] == 17.5
    assert selected["sourceStart"] + selected["duration"] <= 30
    assert selected["evidence"]["contains_transcript"] is True
    assert selected["evidence"]["dialogue_overlap_seconds"] == 1.5
    assert "anchored to supplied dialogue" in selected["reason"]


def test_non_finite_timing_values_are_ignored_or_rejected():
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], float("nan"))
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 10}],
        [{"start": float("nan")}, {"start": 0}],
        [{"start": float("nan"), "end": 2, "text": "bad timing"}],
        5)
    assert result["clips"][0]["sourceStart"] == 0
    assert result["transcript_segment_count"] == 0


def test_ranker_prefers_dialogue_relevant_scene_when_target_is_short():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 30}],
        [{"start": 0}, {"start": 5}, {"start": 10}, {"start": 15}],
        [{"start": 11.0, "end": 14.0, "text": "Key explanation"}],
        5, "balanced")
    assert len(result["clips"]) == 1
    assert result["clips"][0]["sourceStart"] == 10.0
    assert result["clips"][0]["evidence"]["shot_score"] > 0
    assert result["clips"][0]["evidence"]["dialogue_density"] > 0


def test_ranked_selection_restores_source_chronology():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 5}, {"start": 10}],
        [{"start": 11.0, "end": 13.0, "text": "Later dialogue"}],
        10, "balanced")
    source_starts = [clip["sourceStart"] for clip in result["clips"]]
    assert source_starts == sorted(source_starts)


def test_visual_analysis_signals_influence_ranking_and_are_reported():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [
            {"start": 0, "visual_interest": 0.1, "subject_presence": 0.2,
             "motion_suitability": 0.1},
            {"start": 5, "visual_interest": 0.95, "subject_presence": 0.9,
             "motion_suitability": 0.8},
        ], [], 5, "balanced")
    assert result["clips"][0]["sourceStart"] == 5
    evidence = result["clips"][0]["evidence"]
    assert evidence["visual_score"] == pytest.approx(0.883, abs=0.001)
    assert evidence["visual_signals"]["visual_interest"] == 0.95


def test_visual_analysis_signals_are_clamped_and_invalid_values_ignored():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 10}],
        [{"start": 0, "visual_interest": 8, "subject_presence": float("nan"),
          "motion_suitability": -2}], [], 3)
    evidence = result["clips"][0]["evidence"]
    assert evidence["visual_signals"] == {"visual_interest": 1.0, "motion_suitability": 0.0}
    assert evidence["visual_score"] == 0.5


def test_max_shot_duration_caps_each_generated_clip():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 8}, {"start": 16}], [], 12,
        "balanced", max_shot_duration=2.5)
    assert result["max_shot_duration"] == 2.5
    assert all(clip["duration"] <= 2.5 for clip in result["clips"])
    assert sum(clip["duration"] for clip in result["clips"]) == 7.5


def test_max_shot_duration_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 10, max_shot_duration=0.1)
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 10, max_shot_duration=16)


def test_min_shot_duration_prevents_unnecessarily_short_selected_shots():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 8}, {"start": 16}], [], 12,
        "balanced", max_shot_duration=5, min_shot_duration=3)
    assert result["min_shot_duration"] == 3
    assert all(clip["duration"] >= 3 for clip in result["clips"])
    assert [clip["duration"] for clip in result["clips"]] == [5, 5, 2] or sum(c["duration"] for c in result["clips"]) <= 12


def test_min_shot_duration_warns_when_source_scene_is_too_short():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 4}],
        [{"start": 0}, {"start": 0.7}], [], 4,
        "balanced", min_shot_duration=1.5)
    assert any("skipped because they could not meet the 1.5s minimum" in warning for warning in result["warnings"])


def test_min_shot_duration_rejects_invalid_or_inconsistent_limits():
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 10, min_shot_duration=0.2)
    with pytest.raises(ValueError):
        build_smart_timeline([], [], [], 10, max_shot_duration=2, min_shot_duration=3)


def test_pacing_distribution_gives_dialogue_dense_shots_more_time():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 12}],
        [{"start": 0, "end": 10, "text": "Long spoken passage"}],
        18, "calm")
    clips = result["clips"]
    assert len(clips) == 2
    assert clips[0]["duration"] > clips[1]["duration"]
    assert clips[0]["evidence"]["pacing_factor"] > clips[1]["evidence"]["pacing_factor"]


def test_dynamic_pacing_shortens_high_motion_shots_when_motion_evidence_exists():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [
            {"start": 0, "motion_suitability": 0.0},
            {"start": 5, "motion_suitability": 1.0},
        ], [], 10, "dynamic")
    by_source = {clip["sourceStart"]: clip for clip in result["clips"]}
    assert by_source[5.0]["duration"] < by_source[0.0]["duration"]


def test_pacing_factor_stays_within_guardrails_and_respects_shot_cap():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0, "visual_interest": 1, "motion_suitability": 1}, {"start": 5}],
        [{"start": 0, "end": 5, "text": "Dialogue"}],
        8, "calm", max_shot_duration=2.5)
    assert all(0.75 <= c["evidence"]["pacing_factor"] <= 1.25 for c in result["clips"])
    assert all(c["duration"] <= 2.5 for c in result["clips"])


def test_supplied_beat_markers_snap_shot_lengths_to_whole_beats():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 20}],
        [{"start": 0}, {"start": 8}, {"start": 16}], [], 10,
        "balanced", max_shot_duration=5, min_shot_duration=1,
        beat_times=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
    assert result["beat_sync"] is True
    assert result["beat_interval_seconds"] == pytest.approx(0.5)
    for clip in result["clips"]:
        assert clip["duration"] / 0.5 == pytest.approx(round(clip["duration"] / 0.5))
        assert clip["evidence"]["beat_aligned"] is True
        assert clip["evidence"]["beats_per_shot"] >= 1


def test_beat_sync_ignores_invalid_or_insufficient_markers():
    result = build_smart_timeline(
        [{"id": "v", "type": "video", "duration": 10}],
        [{"start": 0}], [], 4, beat_times=[0.0, float("nan"), 1.0])
    assert result["beat_sync"] is False
    assert result["clips"][0]["evidence"]["beat_aligned"] is False
    assert any("at least three valid" in warning for warning in result["warnings"])
