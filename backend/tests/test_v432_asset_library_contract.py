from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"
def test_media_client_uses_project_scoped_upload_and_csrf():
    s=(SRC/"lib/mediaApi.ts").read_text()
    assert "body.append(\"file\", file)" in s and "X-CSRF-Token" in s and "credentials: \"include\"" in s
    assert "/api/projects/${encodeURIComponent(projectId)}/media" in s
def test_asset_library_supports_upload_preview_and_waveform():
    s=(SRC/"components/AssetLibrary.tsx").read_text()
    for token in ("mediaApi.upload","mediaApi.list","mediaApi.preview","mediaApi.waveform"):
        assert token in s
    assert 'accept="video/*,audio/*,image/*"' in s
def test_timeline_selects_project_assets():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "assets: MediaAsset[]" in s
    assert 'a.mime_type.startsWith("video/") || a.mime_type.startsWith("image/")' in s
def test_app_connects_library_and_timeline():
    s=(SRC/"App.tsx").read_text()
    assert "<AssetLibrary projectId=" in s and "<TimelineComposer assets={assets}" in s
