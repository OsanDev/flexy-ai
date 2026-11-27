from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "frontend-reference/apps/web/src"
def test_project_read_route_is_owner_scoped():
    main=(ROOT/"app/main.py").read_text()
    assert 'method == "GET" and path.count("/") == 3' in main
    assert 'def read_project(project_id: str, user=Depends(current_user))' in main
    assert 'storage.get_project_for_owner(user.id, project_id)' in main
def test_project_api_loads_and_saves_with_revision():
    s=(SRC/"lib/projectApi.ts").read_text()
    assert 'encodeURIComponent(projectId)' in s
    assert 'expected_revision: expectedRevision' in s
    assert 'X-CSRF-Token' in s
def test_app_loads_cloud_document_and_autosaves_debounced():
    s=(SRC/"App.tsx").read_text()
    assert "projectApi.load(id)" in s and "projectApi.save(" in s
    assert "timeline_document: projectDocument" in s
    assert "window.setTimeout" in s and "window.clearTimeout" in s
    assert "savePulse" in s
def test_timeline_document_is_rehydrated_and_dirty_state_tracks_edits():
    s=(SRC/"App.tsx").read_text()
    c=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "initialDocument={projectDocument}" in s
    assert "onDocumentChange" in c
    assert "projectDocumentRef.current = next" in s
def test_autosave_preserves_other_project_payload_fields():
    s=(SRC/"App.tsx").read_text()
    assert "...projectPayload, timeline_document: projectDocument" in s
