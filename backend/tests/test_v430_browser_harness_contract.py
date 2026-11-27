from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web"

def test_harness_mounts_export_panel_and_has_vite_entrypoint():
    source = (APP / "src/App.tsx").read_text()
    assert 'import { ExportPanel } from "./components/ExportPanel"' in source
    assert '<ExportPanel projectId={projectId.trim()} graph={graphMode === "timeline" ? timelineGraph : graph!} />' in source
    assert (APP / "index.html").exists()
    assert (APP / "vite.config.ts").exists()

def test_harness_supports_registration_login_and_csrf_logout():
    source = (APP / "src/App.tsx").read_text()
    assert 'authRequest(mode, email, password)' in source
    assert '/api/auth/logout' in source
    assert '"X-CSRF-Token": csrf' in source

def test_harness_requires_real_project_and_valid_graph():
    source = (APP / "src/App.tsx").read_text()
    assert 'placeholder="Paste an existing project ID"' in source
    assert "JSON.parse(graphText)" in source
    assert "Add media IDs that already belong to this project." in source
