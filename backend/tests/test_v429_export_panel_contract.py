from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src/components/ExportPanel.tsx"

def test_export_panel_covers_core_render_actions():
    source = COMPONENT.read_text()
    for token in ("renderApi.preflight", "renderApi.create", "renderApi.status",
                  "renderApi.cancel", "renderApi.download", "renderApi.remove"):
        assert token in source

def test_export_panel_polls_and_stops_at_terminal_states():
    source = COMPONENT.read_text()
    assert "setTimeout(poll, 1500)" in source
    assert "TERMINAL.has(latest.status)" in source
    assert "clearTimeout(timer)" in source

def test_export_panel_has_accessible_status_and_error_regions():
    source = COMPONENT.read_text()
    assert 'role="alert"' in source
    assert 'aria-live="polite"' in source
    assert '<progress max={100}' in source
