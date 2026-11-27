from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_restores_cookie_session_through_auth_me_endpoint():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })' in source
    assert "setAccount(session.email)" in source
    assert "setSignedIn(true)" in source


def test_frontend_waits_for_session_check_before_showing_sign_in():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "const [authChecking, setAuthChecking] = useState(true)" in source
    assert "Restoring your workspace" in source
    assert "authChecking ? (" in source


def test_session_restore_does_not_read_httponly_session_cookie():
    source = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert "The session token never needs to be read by JavaScript" in source
    assert 'fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })' in source
