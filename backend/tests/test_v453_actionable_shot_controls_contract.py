from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_video_preview_api_accepts_a_timestamp():
    source = (WEB / "lib" / "mediaApi.ts").read_text()
    assert "preview(projectId: string, asset: MediaAsset, timestamp = 0.5)" in source
    assert "timestamp=${encodeURIComponent(String(Math.max(0, timestamp)))}" in source


def test_storyboard_has_source_frame_preview_control():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "const previewShot = async (asset: MediaAsset, timestamp: number)" in source
    assert "Preview source frame" in source
    assert "framePreview.timestamp.toFixed(1)" in source
    assert "Source frame preview" in source


def test_storyboard_can_offer_an_explicit_add_shot_action():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "onAddShotToTimeline?: (asset: MediaAsset, sourceStart: number) => void" in source
    assert "Add 3s shot to timeline" in source
    assert "onAddShotToTimeline(asset, scene.timestamp)" in source


def test_inserted_shot_is_clamped_and_uses_existing_undoable_update():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "const available = asset.duration === null ? 3 : Math.max(0, asset.duration - sourceStart)" in source
    assert "const shotDuration = Math.min(3, available)" in source
    assert "videoClips: [...doc.videoClips, clip]" in source
    assert "update({ ...doc, videoClips:" in source
    assert "setSelectedClip({ id: clip.id, type: \"video\" })" in source
    assert "setPlayhead(clip.timelineStart)" in source


def test_shot_controls_are_styled_and_release_version_is_current():
    styles = (WEB / "styles.css").read_text()
    assert ".visual-shot-actions" in styles
    assert ".visual-frame-preview" in styles
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
