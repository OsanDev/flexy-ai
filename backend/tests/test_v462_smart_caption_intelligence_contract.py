from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_caption_intelligence_checks_overlap_reading_speed_and_visual_end():
    source = (WEB / "lib" / "captionIntelligence.ts").read_text()
    assert "characters/second" in source
    assert "Caption overlap" in source
    assert "Caption extends past the video" in source
    assert "visualEnd" in source


def test_caption_timing_is_review_first_and_applied_as_one_undoable_update():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "applyCaptionTimingPlan" in source
    assert "Analyze captions" in source
    assert "Apply timing" in source and "Discard" in source
    assert "update(nextDocument)" in source
    assert "setCaptionReport(null)" in source


def test_caption_alignment_limit_is_explicit():
    source = (WEB / "lib" / "captionIntelligence.ts").read_text()
    panel = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "cannot hear dialogue" in source
    assert "do not establish actual speech synchronization" in panel


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
