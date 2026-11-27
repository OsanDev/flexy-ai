from app.main import APP_VERSION, configured_cors_origins, health


def test_cors_origins_parse_multiple_deployed_hosts():
    assert configured_cors_origins(" https://studio.example.com/ , https://www.example.com ") == [
        "https://studio.example.com",
        "https://www.example.com",
    ]


def test_cors_origins_keep_local_defaults_when_empty():
    assert configured_cors_origins(" , ") == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_health_reports_current_release_version():
    assert health()["version"] == APP_VERSION == "4.6.0"


def test_frontend_package_version_matches_api_release():
    import json
    from pathlib import Path

    package = Path(__file__).resolve().parents[2] / "frontend-reference" / "apps" / "web" / "package.json"
    assert json.loads(package.read_text())["version"] == APP_VERSION == "4.6.0"
