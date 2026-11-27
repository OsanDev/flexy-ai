from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "frontend-reference/apps/web/src/App.tsx"


def test_each_project_load_gets_a_distinct_session_identity():
    source = APP.read_text()
    assert "const projectSessionRef = useRef(0)" in source
    assert "const sessionId = ++projectSessionRef.current" in source
    assert "projectSessionRef.current !== sessionId" in source


def test_reopened_project_waits_for_its_previous_save_before_loading():
    source = APP.read_text()
    assert "pendingProjectSavesRef = useRef<Map<string, Promise<unknown>>>(new Map())" in source
    assert "const pendingSave = pendingProjectSavesRef.current.get(id)" in source
    assert "if (pendingSave) await pendingSave.catch(() => undefined)" in source
    assert "const saveRequest = projectApi.save(targetProjectId" in source
    assert "pendingProjectSavesRef.current.set(targetProjectId, saveRequest)" in source


def test_stale_save_responses_cannot_mutate_a_new_project_session():
    source = APP.read_text()
    assert "if (projectSessionRef.current !== sessionId || loadedProjectId !== targetProjectId || projectId.trim() !== targetProjectId) return;" in source
    assert "if (projectSessionRef.current === sessionId && loadedProjectId === targetProjectId" in source
    assert "pendingProjectSavesRef.current.get(targetProjectId) === saveRequest" in source
