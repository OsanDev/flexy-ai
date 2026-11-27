from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_scene_vision_endpoint_is_authenticated_and_project_scoped():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    start = source.index('@app.post("/api/projects/{project_id}/media/{media_id}/scene-vision")')
    endpoint = source[start:start + 1800]
    assert "user=Depends(current_user)" in endpoint
    assert "storage.get_media_for_owner(user.id, media_id, project_id)" in endpoint
    assert "describe_scene(thumbnail_path)" in endpoint


def test_media_api_calls_existing_scene_vision_endpoint():
    source = (WEB / "lib" / "mediaApi.ts").read_text()
    assert "sceneVision(projectId: string, mediaId: string, timestamp: number)" in source
    assert "/scene-vision?${query}" in source
    assert "method: \"POST\"" in source


def test_scene_analysis_is_explicit_user_initiated_and_midpoint_based():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert 'onClick={() => void analyzeScene(asset)}' in source
    assert "asset.duration ?? 1" in source
    assert "AI scene analysis" in source
    assert "visionBusy" in source


def test_scene_results_show_description_objects_actions_and_editing_notes():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    for key in ("description", "objects", "actions", "editing_notes", "confidence"):
        assert f"visionResults[asset.id].{key}" in source


def test_ui_discloses_provider_configuration_and_model_uncertainty():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "FLEXY_AI_API_KEY" in source
    assert "Model descriptions can be wrong" in source
    assert "sends up to six representative frames" in source


def test_release_version_is_v4429():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source


def test_scene_detection_can_optionally_return_bounded_pixel_visual_scores():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    start = source.index('@app.post("/api/projects/{project_id}/media/{media_id}/scenes")')
    endpoint = source[start:source.index('@app.get("/api/projects/{project_id}/media/{media_id}/scene-thumbnail")')]
    assert "include_visual_scores: bool = False" in endpoint
    assert "max_scenes > 50" in endpoint
    assert 'scene["visual_interest"] = insights["visual_interest"]' in endpoint
    assert '"semantic_recognition": False' in endpoint
