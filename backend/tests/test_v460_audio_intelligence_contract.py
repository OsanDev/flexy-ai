from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_audio_waveform_engine_uses_normalized_peak_buckets():
    source = (WEB / "lib" / "audioIntelligence.ts").read_text()
    assert "analyzeAudioWaveforms" in source
    assert "waveform?.points ?? waveform?.samples ?? waveform?.waveform" in source
    assert "value <= 0.025" in source
    assert "hasQuietOpening" in source and "hasQuietEnding" in source


def test_audio_engine_flags_quiet_regions_edges_and_high_peaks():
    source = (WEB / "lib" / "audioIntelligence.ts").read_text()
    for token in ("Quiet or silent sections", "Quiet audio opening",
                  "Quiet audio ending", "Very high waveform peaks"):
        assert token in source


def test_audio_engine_checks_dialogue_music_overlap():
    source = (WEB / "lib" / "audioIntelligence.ts").read_text()
    assert 'current.role === "dialogue"' in source
    assert 'next.role === "music"' in source
    assert "Dialogue and music overlap" in source


def test_audio_panel_fetches_waveforms_and_displays_findings():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "mediaApi.waveform(projectId, mediaId)" in source
    assert 'aria-label="Audio intelligence"' in source
    assert "audioIntelligence.findings.map" in source
    assert "audioIntelligence.profiles.map" in source
    assert "Analyze audio" in source
    assert "setSelectedClip({ id: clip.id, type: \"audio\" })" in source


def test_audio_visualization_and_release_version_exist():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "audio-profile-wave" in source
    assert ".audio-intelligence-panel" in (WEB / "styles.css").read_text()
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
