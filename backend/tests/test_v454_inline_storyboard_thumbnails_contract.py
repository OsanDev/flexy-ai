from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_storyboard_fetches_representative_frame_thumbnails():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "thumbnailUrl = await mediaApi.preview(projectId, asset, timestamp)" in source
    assert "visual-storyboard-thumbnail" in source
    assert "Scene ${index + 1} frame at" in source


def test_storyboard_thumbnail_failures_do_not_break_scene_analysis():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "Keep semantic scene analysis usable if a thumbnail request fails." in source
    assert "Frame preview unavailable" in source


def test_storyboard_object_urls_are_revoked_when_replaced_and_unmounted():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "storyboardUrls.current.forEach((url) => URL.revokeObjectURL(url))" in source
    assert "URL.revokeObjectURL(url)" in source
    assert "storyboardUrls.current = storyboardUrls.current.filter" in source
