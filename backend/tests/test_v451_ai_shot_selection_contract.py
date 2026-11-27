from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_shot_ranking_is_transparent_and_bounded():
    source = (WEB / "lib" / "visualShotRanking.ts").read_text()
    assert "export function scoreShot" in source
    assert "Math.min(100" in source
    assert "description.length" in source
    assert "objectCount" in source
    assert "actionCount" in source
    assert "noteCount" in source
    assert "confidence * 11" in source
    assert "visual_interest?: number" in source


def test_ranking_sorts_by_score_then_timestamp():
    source = (WEB / "lib" / "visualShotRanking.ts").read_text()
    assert "export function rankShots" in source
    assert "b.score - a.score || a.timestamp - b.timestamp" in source


def test_unavailable_ai_results_are_not_given_a_fake_score():
    source = (WEB / "lib" / "visualShotRanking.ts").read_text()
    assert 'if (!candidate.available)' in source
    assert 'semanticScore: 0' in source
    assert 'visualScore: null' in source


def test_storyboard_preserves_editing_notes_and_confidence_for_ranking():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "editing_notes: string[]" in source
    assert "confidence?: number" in source
    assert "response.analysis.editing_notes" in source
    assert "response.analysis.confidence" in source
    assert "rankShots(storyboards[asset.id], { visualWeight })" in source


def test_ui_explains_score_and_no_automatic_timeline_changes():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "Semantic AI detail" in source
    assert "Pixel evidence influence" in source
    assert "Pixel evidence" in source
    assert "FLEXY does not rearrange your timeline" in source
    assert "Shot review ranking" in source


def test_ranking_styles_are_present():
    source = (WEB / "styles.css").read_text()
    assert ".visual-shot-ranking" in source


def test_release_version_is_v4251():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source


def test_visual_weight_is_bounded_and_missing_visual_evidence_keeps_semantic_score():
    source = (WEB / "lib" / "visualShotRanking.ts").read_text()
    assert "visualWeight?: number" in source
    assert "Math.max(0, Math.min(100, options.visualWeight ?? 25))" in source
    assert "Missing pixel evidence never penalizes a shot" in source
    assert "semanticScore * (1 - visualWeight) + visualScore * visualWeight" in source
