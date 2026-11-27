from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_scene_detection_api_uses_authenticated_project_scoped_route():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    start = source.index('@app.post("/api/projects/{project_id}/media/{media_id}/scenes")')
    endpoint = source[start:start + 1000]
    assert "user=Depends(current_user)" in endpoint
    assert "storage.get_media_for_owner(user.id, media_id, project_id)" in endpoint
    assert "detect_scenes(path" in endpoint


def test_frontend_media_api_exposes_scene_detection():
    source = (WEB / "lib" / "mediaApi.ts").read_text()
    assert "detectScenes(projectId: string, mediaId: string, maxScenes = 50, includeVisualScores = true)" in source
    assert "include_visual_scores: String(includeVisualScores)" in source
    assert "Math.min(50" in source
    assert "/scenes?${query}" in source
    assert "SceneDetectionResult" in source


def test_storyboard_uses_detected_scene_boundaries_and_caps_six_frames():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "mediaApi.detectScenes(projectId, asset.id, 50, true)" in source
    assert "measuredScene.visual_interest" in source
    assert "Pixel visual-interest" in source or "pixel visual-interest" in source
    assert "detected.scenes.map((scene) => scene.start)" in source
    assert "length: 6" in source
    assert "detected.scenes.length" in source
    assert "Math.ceil(duration / 5)" in source
    assert "mediaApi.sceneVision(projectId, asset.id" in source


def test_storyboard_is_user_initiated_and_only_for_video_assets():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert 'onClick={() => void buildStoryboard(asset)}' in source
    assert 'asset.mime_type.startsWith("video/") && <>' in source
    assert "Building storyboard…" in source


def test_storyboard_displays_timestamps_and_scene_descriptions():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "Scene storyboard" in source
    assert "scene.timestamp.toFixed(1)" in source
    assert "scene.description" in source
    assert "scene.objects.join" in source
    assert "scene.actions.join" in source


def test_storyboard_has_responsive_visual_cards():
    source = (WEB / "styles.css").read_text()
    assert ".visual-storyboard" in source
    assert ".visual-storyboard>article" in source


def test_release_version_is_v4250():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
