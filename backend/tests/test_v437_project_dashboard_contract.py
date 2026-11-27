from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "frontend-reference/apps/web/src"
def test_dashboard_has_create_search_open_rename_duplicate_delete():
    s=(SRC/"components/ProjectDashboard.tsx").read_text()
    for token in ("projectApi.create","projectApi.list","projectApi.rename","projectApi.duplicate","projectApi.remove","onOpen"):
        assert token in s
def test_project_api_exposes_dashboard_actions():
    s=(SRC/"lib/projectApi.ts").read_text()
    for token in ("list(search","create(name","rename(projectId","duplicate(projectId","remove(projectId"):
        assert token in s
def test_dashboard_is_mounted_for_signed_in_workspace():
    s=(SRC/"App.tsx").read_text()
    assert "<ProjectDashboard" in s
    assert 'PROJECT DASHBOARD / v4.2.37' in s
def test_duplicate_route_is_authenticated_and_owner_scoped():
    s=(ROOT/"app/main.py").read_text()
    assert 'path.endswith("/duplicate") and method == "POST"' in s
    assert 'def duplicate_project(project_id: str, request: DuplicateProjectRequest, user=Depends(current_user))' in s
    assert 'storage.get_project_for_owner(user.id, project_id)' in s
    assert 'storage.duplicate_project_for_owner(user.id' in s
def test_storage_duplicate_checks_owner_and_preserves_owner_id():
    s=(ROOT/"app/storage.py").read_text()
    assert 'def duplicate_project_for_owner(owner_id: str' in s
    assert 'WHERE id=? AND owner_id=?' in s
    assert 'INSERT INTO projects(id,owner_id,name,project_json,revision)' in s
