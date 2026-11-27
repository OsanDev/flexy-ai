from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_visual_inspector_uses_existing_media_preview_api():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "mediaApi.preview(projectId, asset)" in source
    assert "Visual Media Intelligence" in source or "VISUAL MEDIA INTELLIGENCE" in source
    assert "Media contact sheet" in source
    assert "URL.revokeObjectURL(url)" in source


def test_pixel_analysis_samples_brightness_contrast_and_colour():
    source = (WEB / "lib" / "visualMediaAnalysis.ts").read_text()
    for term in ("brightness", "contrast", "colorfulness", "tone", "getImageData"):
        assert term in source
    assert "No image pixels are uploaded" in source


def test_visual_inspector_is_integrated_into_timeline_composer():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'import { VisualMediaInspector } from "./VisualMediaInspector"' in source
    assert "<VisualMediaInspector assets={assets} projectId={projectId}" in source
    assert "onCreateEditPlan={(instruction)" in source


def test_visual_inspector_limits_assets_and_discloses_analysis_limits():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert ".slice(0, 12)" in source
    assert "Model descriptions can be wrong" in source
    assert "up to six representative frames" in source.lower()


def test_visual_inspector_has_responsive_contact_sheet_styles():
    source = (WEB / "styles.css").read_text()
    assert ".visual-media-grid" in source
    assert "@media(max-width:560px){.visual-media-inspector" in source


def test_release_version_is_v4428():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
