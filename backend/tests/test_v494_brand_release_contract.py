from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

def test_release_versions_are_aligned():
    main = (ROOT / "backend/app/main.py").read_text()
    package = json.loads((ROOT / "frontend-reference/apps/web/package.json").read_text())
    app = (ROOT / "frontend-reference/apps/web/src/App.tsx").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
    assert package["version"] == "4.6.0"
    assert "VIDEO EDITOR / v4.6.0" in app

def test_official_brand_palette_is_declared_and_used():
    css = (ROOT / "frontend-reference/apps/web/src/styles.css").read_text()
    for token in ("#FFFFFF", "#4B5563", "#718096", "#75CDD8"):
        assert token in css
    assert ".brand-mark" in css and ".primary" in css

def test_document_title_matches_video_editor_product():
    html = (ROOT / "frontend-reference/apps/web/index.html").read_text()
    assert "FLEXY AI | Video Editor" in html
