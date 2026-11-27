from pathlib import Path

CLIENT = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src/lib/renderApi.ts"

def test_client_uses_cookie_credentials_and_csrf_header():
    source = CLIENT.read_text()
    assert 'credentials: "include"' in source
    assert 'headers.set("X-CSRF-Token", token)' in source
    assert 'const CSRF_COOKIE = "flexy_csrf"' in source

def test_client_exposes_all_render_workflow_operations():
    source = CLIENT.read_text()
    for method in ("preflight(", "create(", "list(", "status(", "cancel(", "remove(", "download("):
        assert method in source

def test_download_uses_authenticated_fetch_not_public_url():
    source = CLIENT.read_text()
    assert "async download(jobId: string): Promise<Blob>" in source
    assert "{ credentials: \"include\" }" in source
