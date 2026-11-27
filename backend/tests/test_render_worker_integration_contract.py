from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_render_worker_has_progress_cancel_and_atomic_completion():
    source = (ROOT / "app" / "main.py").read_text()
    assert "def run_render_job(" in source
    assert "render_mp4(graph, output_path, progress_callback=progress, cancel_check=cancelled)" in source
    assert "storage.complete_job_if_processing(job_id, output_name)" in source
    assert 'status="failed"' in source
    assert 'status="cancelled"' in source

def test_all_render_http_handlers_require_authenticated_owner():
    source = (ROOT / "app" / "main.py").read_text()
    required = (
        "user=Depends(current_user)",
        "storage.create_job_for_owner(user.id, job_id, project_id)",
        "storage.get_job_for_owner(user.id, job_id)",
        "storage.request_job_cancel_for_owner(user.id, job_id)",
        "storage.delete_terminal_job_for_owner(user.id, job_id)",
    )
    assert all(item in source for item in required)

def test_render_routes_are_not_left_behind_global_503_gate():
    source = (ROOT / "app" / "main.py").read_text()
    assert '"/render-preflight" in path' in source
    assert 'path.endswith("/renders")' in source
    assert 'path.startswith("/api/renders/")' in source
