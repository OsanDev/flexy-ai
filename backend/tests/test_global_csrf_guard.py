from fastapi.testclient import TestClient

from app.main import app
from app import storage


def test_authenticated_mutation_without_csrf_is_rejected_before_route_dispatch():
    storage.init_db()
    client = TestClient(app)
    client.cookies.set("flexy_session", "present-but-not-authenticated")
    response = client.post(
        "/api/projects",
        json={"name": "CSRF probe", "project": {}, "expected_revision": 0},
        headers={"origin": "http://localhost:5173"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed."


def test_authenticated_mutation_with_matching_csrf_reaches_authentication():
    storage.init_db()
    client = TestClient(app)
    client.cookies.set("flexy_session", "present-but-not-authenticated")
    client.cookies.set("flexy_csrf", "token")
    response = client.post(
        "/api/projects",
        json={"name": "CSRF probe", "project": {}, "expected_revision": 0},
        headers={"origin": "http://localhost:5173", "x-csrf-token": "token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_safe_read_does_not_require_csrf_header():
    storage.init_db()
    client = TestClient(app)
    client.cookies.set("flexy_session", "present-but-not-authenticated")
    response = client.get(
        "/api/projects",
    )
    assert response.status_code == 401
