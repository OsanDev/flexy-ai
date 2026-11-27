from app.main import app


def test_every_non_public_api_route_requires_authenticated_user_or_auth_guard():
    public = {("GET", "/api/health")}
    auth_guards = {
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
    }
    uncovered = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/"):
            continue
        for method in route.methods or set():
            key = (method, path)
            if key in public or key in auth_guards:
                continue
            dependency_names = {
                getattr(dependency.call, "__name__", "")
                for dependency in route.dependant.dependencies
            }
            if "current_user" not in dependency_names:
                uncovered.append(key)
    assert uncovered == []


def test_mutating_auth_routes_keep_explicit_origin_or_csrf_guards():
    from app.auth_api import login, logout, register

    assert "_origin_check" in register.__code__.co_names
    assert "_origin_check" in login.__code__.co_names
    assert "_csrf_check" in logout.__code__.co_names

