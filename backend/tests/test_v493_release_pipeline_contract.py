import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_and_frontend_versions_are_aligned():
    main = (ROOT / "backend/app/main.py").read_text()
    package = json.loads((ROOT / "frontend-reference/apps/web/package.json").read_text())
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
    assert package["version"] == "4.6.0"


def test_browser_workflows_disclose_mocked_and_live_coverage():
    mocked = (ROOT / "frontend-reference/apps/web/e2e/editor-workflow.spec.ts").read_text()
    live = (ROOT / "frontend-reference/apps/web/e2e/live-editor-workflow.spec.ts").read_text()
    assert 'test("mocked browser workflow:' in mocked
    assert 'test("live browser workflow:' in live
    assert "uploads a real video" in live or "setInputFiles(source)" in live
    assert "downloads the resulting MP4" in live or 'toBe("ftyp")' in live
    readme = (ROOT / "README.md").read_text()
    assert "Mocked browser workflow" in readme
    assert "Live browser workflow" in readme


def test_export_ui_requires_successful_preflight_before_queueing():
    panel = (ROOT / "frontend-reference/apps/web/src/components/ExportPanel.tsx").read_text()
    assert "disabled={busy || preflight?.ready !== true}" in panel
    assert "if (report.ready !== true)" in panel
    assert "await renderApi.create(projectId, exportGraph)" in panel
    assert panel.index("if (report.ready !== true)") < panel.index("await renderApi.create(projectId, exportGraph)")


def test_health_readiness_requires_ffmpeg_for_media_operations():
    main = (ROOT / "backend/app/main.py").read_text()
    assert "ready = database_available and storage_available and ffmpeg_available" in main
