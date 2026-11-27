from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_dialogue_plan_is_connected_to_caption_workspace():
    api = (ROOT / "frontend-reference/apps/web/src/lib/mediaApi.ts").read_text()
    composer = (ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx").read_text()
    assert '"/api/assistant/dialogue-edit-plan"' in api
    assert "dialogueEditPlan(transcription.segments)" in composer
    assert "Analyze dialogue" in composer
    assert "setPlayhead(block.start)" in composer
    assert "setPlayhead(marker.at)" in composer
    assert "review_only" in api
