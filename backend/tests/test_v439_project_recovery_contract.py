from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_project_editor_has_local_recovery_snapshot_and_restore():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "flexy:recovery:" in source
    assert "restoreLocalRecovery" in source
    assert "discardLocalRecovery" in source
    assert "Restore draft" in source
    assert "setTimelineMount" in source


def test_project_settings_can_rename_current_project():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "renameCurrentProject" in source
    assert "projectApi.rename(projectId.trim(), next)" in source
    assert "Project name" in source


def test_local_recovery_is_cleared_after_successful_cloud_save():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'localStorage.removeItem(recoveryStorageKey(accountId, targetProjectId))' in source
    assert "setSaveStatus(\"All changes saved\")" in source
