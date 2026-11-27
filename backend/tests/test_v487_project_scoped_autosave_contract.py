from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "frontend-reference/apps/web/src/App.tsx"


def test_autosave_requires_the_requested_project_to_be_the_loaded_project():
    source = APP.read_text()
    assert 'const [loadedProjectId, setLoadedProjectId] = useState("")' in source
    assert 'loadedProjectId !== targetProjectId' in source
    assert 'setLoadedProjectId(id)' in source


def test_autosave_requests_are_tracked_per_project_and_ignore_stale_responses():
    source = APP.read_text()
    assert 'useRef<Set<string>>(new Set())' in source
    assert 'savingProjectsRef.current.add(targetProjectId)' in source
    assert 'savingProjectsRef.current.delete(targetProjectId)' in source
    assert 'loadedProjectId !== targetProjectId || projectId.trim() !== targetProjectId' in source
    assert "const sessionId = projectSessionRef.current" in source
    assert "projectSessionRef.current !== sessionId" in source


def test_local_recovery_snapshot_is_only_written_for_loaded_project():
    source = APP.read_text()
    assert 'loadedProjectId !== projectId.trim()' in source
