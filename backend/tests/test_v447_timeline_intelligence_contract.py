from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_timeline_analyzer_reports_structural_timing_insights():
    source = (WEB / "lib" / "timelineIntelligence.ts").read_text()
    for phrase in (
        "Opening gap", "Visual gap", "Clip overlap", "Audio extends past video",
        "Caption outside visual sequence", "No audio track", "No captions",
    ):
        assert phrase in source


def test_timeline_analyzer_uses_asset_metadata_and_clip_map():
    source = (WEB / "lib" / "timelineIntelligence.ts").read_text()
    assert "new Map(assets.map((asset) => [asset.id, asset.filename]))" in source
    assert "clipNotes" in source
    assert "visualCoverage" in source
    assert "does not inspect image pixels or decode audio" in source


def test_composer_shows_live_insights_and_clip_inspection_actions():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "analyzeTimeline(doc, assets)" in source
    assert "TIMELINE INTELLIGENCE" in source
    assert "Editing insights" in source
    assert 'setSelectedClip({ id: clip.id, type: "video" })' in source
    assert "Inspect" in source
    assert "setPlayhead(target)" in source


def test_timeline_intelligence_panel_has_mobile_layout():
    source = (ROOT / "frontend-reference" / "apps" / "web" / "src" / "styles.css").read_text()
    assert ".timeline-intelligence" in source
    assert "@media(max-width:560px){.timeline-intelligence" in source


def test_release_version_is_v4427():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
