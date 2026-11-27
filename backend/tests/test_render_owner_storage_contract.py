from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_owner_scoped_render_storage_contract_exists():
    source = (ROOT / "app" / "storage.py").read_text()
    for name in ("create_job_for_owner", "get_job_for_owner",
                 "list_project_renders_for_owner", "request_job_cancel_for_owner",
                 "delete_terminal_job_for_owner"):
        assert f"def {name}(" in source

def test_render_preflight_can_enforce_project_and_media_owner():
    source = (ROOT / "app" / "render_preflight.py").read_text()
    assert "storage.get_project_for_owner(owner_id, project_id)" in source
    assert "storage.get_media_for_owner(owner_id, media_id, project_id)" in source
