from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_transcription_client_uses_authenticated_project_media_endpoint():
    source = (WEB / "lib" / "mediaApi.ts").read_text()
    assert "transcribe(projectId: string, mediaId: string)" in source
    assert "/transcribe" in source
    assert "{ method: \"POST\" }, true" in source
    assert "TranscriptionSegment" in source


def test_caption_editor_previews_and_imports_timestamped_segments():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Generate subtitles" in source
    assert "speech-caption-preview" in source
    assert "Import {buildSpeechCaptionCues(transcription.segments).length} smart captions" in source
    assert "buildSpeechCaptionCues" in source
    assert "setTranscription(null)" in source


def test_transcript_import_respects_source_trim_and_timeline_position():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "const timelineOffset = sourceUse ? sourceUse.timelineStart - sourceUse.sourceStart : 0" in source
    assert "const sourceEnd = sourceUse ? sourceStart + sourceUse.duration : Infinity" in source
    assert "start + timelineOffset" in source


def test_no_fake_transcript_and_provider_requirement_are_explained():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Requires backend speech credentials" in source
    assert "No synthetic transcript is created when unavailable" in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
