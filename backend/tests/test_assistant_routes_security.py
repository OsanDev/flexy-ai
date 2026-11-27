from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_recommendation_and_smart_timeline_routes_are_allowlisted():
    source = (ROOT / "app" / "main.py").read_text()
    assert 'path == "/api/assistant/recommendations" and method == "POST"' in source
    assert 'path == "/api/assistant/smart-timeline" and method == "POST"' in source


def test_recommendation_and_smart_timeline_routes_require_auth_and_csrf():
    source = (ROOT / "app" / "main.py").read_text()
    assert "def edit_recommendations(request: RecommendationRequest, http_request: Request, user=Depends(current_user))" in source
    assert "def smart_timeline(request: SmartTimelineRequest, http_request: Request, user=Depends(current_user))" in source
    assert source.count("_csrf_check(http_request)") >= 4
