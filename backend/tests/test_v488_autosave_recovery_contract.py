from pathlib import Path


def test_frontend_warns_before_leaving_with_unsaved_project_edits():
    source = (Path(__file__).parents[2] / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'window.addEventListener("beforeunload", warnBeforeLeave)' in source
    assert 'event.returnValue = ""' in source
    assert 'if (!projectLoaded || loadedProjectId !== projectId.trim() || !projectDirty) return;' in source


def test_frontend_exposes_manual_retry_for_failed_autosave():
    source = (Path(__file__).parents[2] / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'Retry save' in source
    assert 'setSavePulse((value) => value + 1)' in source
    assert 'disabled={!projectDirty || !projectLoaded}' in source
