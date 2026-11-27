from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_ai_plan_adapter_validates_project_assets_and_media_types():
    source = (WEB / "lib" / "aiPlanAdapter.ts").read_text()
    assert "new Map(assets.map((asset) => [asset.id, asset]))" in source
    assert "assetById.get(raw.assetId)" in source
    assert "video/" in source and "image/" in source and "audio/" in source
    assert "sourceStart + duration > asset.duration" in source
    assert "validateTimelineDocument(nextDocument)" in source


def test_ai_plan_adapter_rejects_invalid_ranges_and_audio_settings():
    source = (WEB / "lib" / "aiPlanAdapter.ts").read_text()
    assert "Number.isFinite(value)" in source
    assert "fadeIn + fadeOut > duration" in source
    assert 'transition !== "crossfade"' in source
    assert 'volume > 2' in source


def test_timeline_composer_requires_explicit_apply_and_discard():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "adaptDirectorDraftToTimeline(plan.timeline_draft, doc, assets)" in source
    assert "Discard timeline" in source
    assert "Apply timeline" in source
    assert "update(directorTimelinePreview.nextDocument)" in source
    assert "Keep all ${current.captions.length} existing caption(s) unchanged." in (
        WEB / "lib" / "aiPlanAdapter.ts"
    ).read_text()


def test_ai_timeline_apply_uses_existing_undoable_update_path():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    update_start = source.index("const update = (next: TimelineDocument)")
    update_end = source.index("const addVideo", update_start)
    update_block = source[update_start:update_end]
    assert "setHistory" in update_block
    assert "setFuture([])" in update_block
    assert "onDocumentChange?.(next)" in update_block
    assert "onGraphChange(buildRenderGraph(next), nextErrors)" in update_block


def test_release_version_tracks_current_release():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
