from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"

def test_timeline_graph_uses_backend_render_contract_keys():
    source = (APP / "lib/timelineGraph.ts").read_text()
    for key in ('media_id:', 'source_start:', 'timeline_start:', 'track_index:',
                'audio_clips:', 'fade_in:', 'fade_out:', 'frame_rate:', 'export_preset:'):
        assert key in source

def test_timeline_graph_sorts_clips_and_validates_time_ranges():
    source = (APP / "lib/timelineGraph.ts").read_text()
    assert "sort((a, b) => a.timelineStart - b.timelineStart" in source
    assert "clip.duration <= 0" in source
    assert "document.videoClips.length" in source
    assert "getTimelineDuration(document) > 1800" in source

def test_app_wires_composer_output_into_export_panel():
    source = (APP / "App.tsx").read_text()
    assert 'import { TimelineComposer } from "./components/TimelineComposer"' in source
    assert "<TimelineComposer assets={assets} onGraphChange=" in source
    assert "graph={graphMode === \"timeline\" ? timelineGraph : graph!}" in source
