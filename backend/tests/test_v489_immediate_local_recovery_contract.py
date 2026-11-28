from pathlib import Path


def test_timeline_edits_write_local_recovery_before_waiting_for_react_effects():
    source = (Path(__file__).parents[2] / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "function writeLocalRecoverySnapshot(accountId: string, projectId: string, document: TimelineDocument): boolean" in source
    callback = source.split("onDocumentChange={(next) => {", 1)[1].split("onGraphChange=", 1)[0]
    assert "writeLocalRecoverySnapshot(accountId, targetProjectId, next)" in callback
    assert "loadedProjectId === targetProjectId" in callback


def test_local_recovery_snapshot_handles_storage_failure_without_blocking_cloud_autosave():
    source = (Path(__file__).parents[2] / "frontend-reference/apps/web/src/App.tsx").read_text()
    helper = source.split("function writeLocalRecoverySnapshot", 1)[1].split("async function authRequest", 1)[0]
    assert "localStorage.setItem" in helper
    assert "catch" in helper
    assert "return false" in helper
