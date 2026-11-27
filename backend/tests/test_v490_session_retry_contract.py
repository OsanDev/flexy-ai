from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_session_service_failure_shows_retry_instead_of_sign_in_form():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "const [authUnavailable, setAuthUnavailable] = useState(false)" in source
    assert "setAuthUnavailable(true)" in source
    assert "Can’t reach your workspace" in source
    assert "Retry connection" in source
    assert "setAuthRetry((value) => value + 1)" in source


def test_session_retry_repeats_cookie_authenticated_session_check():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })' in source
    assert "}, [authRetry]);" in source


def test_expired_session_still_returns_to_sign_in_without_network_error():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "if (response.status === 401) return null;" in source
    assert ") : !signedIn ? (" in source
