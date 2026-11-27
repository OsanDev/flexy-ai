from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_quality_engine_reports_metadata_checks():
    source = (WEB / "lib" / "timelineQuality.ts").read_text()
    for token in ["analyzeTimelineQuality", "Source ranges", "Timeline continuity",
                  "Audio ending", "Caption timing", "Opening alignment"]:
        assert token in source


def test_quality_engine_detects_source_bounds_and_short_shots():
    source = (WEB / "lib" / "timelineQuality.ts").read_text()
    assert "clip.sourceStart + clip.duration > asset.duration" in source
    assert "clip.duration < 0.75" in source
    assert "clip.duration > 15" in source


def test_quality_engine_checks_gaps_audio_and_caption_ends():
    source = (WEB / "lib" / "timelineQuality.ts").read_text()
    assert "Visual gap" in source
    assert "Audio outlasts visuals" in source
    assert "Caption outlasts visuals" in source


def test_quality_score_is_explicitly_limited_to_metadata():
    source = (WEB / "lib" / "timelineQuality.ts").read_text()
    assert "does not listen to audio" in source
    assert 'grade: "Excellent" | "Good" | "Needs review" | "Incomplete"' in source


def test_quality_panel_shows_score_findings_and_review_navigation():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'aria-label="Editing quality report"' in source
    assert "timelineQuality.score" in source
    assert "timelineQuality.findings.map" in source
    assert "Review" in source
    assert "timelineQuality.checks.map" in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
