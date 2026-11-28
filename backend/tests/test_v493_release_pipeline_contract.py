import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_and_frontend_versions_are_aligned():
    main = (ROOT / "backend/app/main.py").read_text()
    package = json.loads((ROOT / "frontend-reference/apps/web/package.json").read_text())
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
    assert package["version"] == "4.6.0"


def test_ci_installs_ffmpeg_and_runs_real_backend_mp4_smoke_test():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "sudo apt-get install -y ffmpeg" in workflow
    assert "python -m pytest -q -rs" in workflow
    assert (ROOT / "backend/tests/test_real_mp4_render_smoke.py").is_file()


def test_ci_runs_frontend_typecheck_build_and_browser_workflow():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "npm run typecheck" in workflow
    assert "npm run build" in workflow
    assert "npm run test:e2e" in workflow
    assert "playwright diagnostics" in workflow.lower()


def test_browser_workflow_discloses_mocked_api():
    test_source = (ROOT / "frontend-reference/apps/web/e2e/editor-workflow.spec.ts").read_text()
    assert 'test("mocked browser workflow:' in test_source
    readme = (ROOT / "README.md").read_text()
    assert "It is **not** a live-backend end-to-end test." in readme


def test_export_ui_requires_successful_preflight_before_queueing():
    panel = (ROOT / "frontend-reference/apps/web/src/components/ExportPanel.tsx").read_text()
    assert "disabled={busy || preflight?.ready !== true}" in panel
    assert "if (report.ready !== true)" in panel
    assert "await renderApi.create(projectId, exportGraph)" in panel
    assert panel.index("if (report.ready !== true)") < panel.index("await renderApi.create(projectId, exportGraph)")


def test_health_readiness_requires_ffmpeg_for_media_operations():
    main = (ROOT / "backend/app/main.py").read_text()
    assert "ready = database_available and storage_available and ffmpeg_available" in main
