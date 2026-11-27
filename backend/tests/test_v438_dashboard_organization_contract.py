from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_organization_endpoint_requires_authenticated_owner():
    source = (ROOT / "backend/app/main.py").read_text()
    route = source.split('@app.patch("/api/projects/{project_id}/organization")', 1)[1].split(
        '@app.post("/api/projects/{project_id}/duplicate")', 1
    )[0]
    assert "user=Depends(current_user)" in route
    assert "update_project_organization_for_owner" in route
    assert "storage.update_project_organization(" not in route


def test_owner_scoped_organization_storage_filters_by_owner():
    source = (ROOT / "backend/app/storage.py").read_text()
    method = source.split("def update_project_organization_for_owner", 1)[1].split(
        "# Owner-scoped methods", 1
    )[0]
    assert "WHERE id=? AND owner_id=?" in method
    assert "folder_name" in method
    assert "is_favorite" in method


def test_dashboard_exposes_folders_favorites_sort_and_real_media_preview():
    dashboard = (ROOT / "frontend-reference/apps/web/src/components/ProjectDashboard.tsx").read_text()
    api = (ROOT / "frontend-reference/apps/web/src/lib/projectApi.ts").read_text()
    assert "favoritesOnly" in dashboard
    assert "Folder" in dashboard
    assert "Recently updated" in dashboard
    assert "mediaApi.list(project.id)" in dashboard
    assert "mediaApi.preview(project.id,candidate)" in dashboard
    assert "favorites_only" in api
    assert "organize(projectId" in api


def test_organization_route_is_allowed_by_fail_closed_middleware():
    source = (ROOT / "backend/app/main.py").read_text()
    assert 'path.endswith("/organization") and method == "PATCH"' in source
