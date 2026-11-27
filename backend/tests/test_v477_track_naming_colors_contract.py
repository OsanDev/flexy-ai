from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"
GRAPH = ROOT / "frontend-reference/apps/web/src/lib/timelineGraph.ts"

def test_track_names_and_color_labels_are_persisted():
    source = COMPONENT.read_text()
    graph = GRAPH.read_text()
    assert "updateTrackMeta" in source
    assert "trackNames" in source and "trackColors" in source
    assert "Rename ${label}" in source
    assert "Color for ${label}" in source
    assert all(f'<option value="{color}">' in source for color in ("violet", "mint", "amber", "rose", "blue"))
    assert "trackNames?: Record<string, string>" in graph
    assert "trackColors?: Record<string, string>" in graph
