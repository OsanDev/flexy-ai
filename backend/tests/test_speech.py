import json
from pathlib import Path

import pytest
from app import speech


def test_speech_unconfigured_returns_explicit_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("FLEXY_AI_API_KEY", raising=False)
    result = speech.transcribe_media(tmp_path / "not-used.wav")
    assert result["available"] is False
    assert result["segments"] == []
    assert "not configured" in result["notice"]


def test_normalize_segments_sorts_and_validates():
    result = speech.normalize_segments([
        {"start": 2, "end": 3, "text": "second"},
        {"start": 0, "end": 1.2, "text": " first ", "words": [
            {"word": "first", "start": 0, "end": 0.5}]},
        {"start": 4, "end": 4, "text": "invalid"},
        {"start": "bad", "end": 5, "text": "invalid"},
    ])
    assert [item["text"] for item in result] == ["first", "second"]
    assert result[0]["words"][0]["word"] == "first"


def test_subtitle_srt_and_vtt_formats():
    segments = [{"start": 1.25, "end": 2.5, "text": "Hello world"}]
    srt = speech.subtitles(segments, "srt")
    vtt = speech.subtitles(segments, "vtt")
    assert "00:00:01,250 --> 00:00:02,500" in srt
    assert "WEBVTT" in vtt
    assert "00:00:01.250 --> 00:00:02.500" in vtt
    with pytest.raises(ValueError):
        speech.subtitles(segments, "ass")


def test_transcription_calls_openai_compatible_endpoint(monkeypatch, tmp_path: Path):
    media = tmp_path / "sample.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    monkeypatch.setenv("FLEXY_AI_BASE_URL", "https://speech.example/v1")
    monkeypatch.setenv("FLEXY_SPEECH_MODEL", "whisper-test")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "Hello world", "language": "en", "segments": [
                {"start": 0, "end": 1.1, "text": "Hello world"}
            ]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data
        captured["headers"] = request.headers
        return FakeResponse()
    monkeypatch.setattr(speech.urllib.request, "urlopen", fake_urlopen)
    result = speech.transcribe_media(media)
    assert result["available"] is True
    assert result["text"] == "Hello world"
    assert result["segments"][0]["start"] == 0
    assert captured["url"] == "https://speech.example/v1/audio/transcriptions"
    assert b"whisper-test" in captured["body"]
    assert "Bearer test-key" == captured["headers"]["Authorization"]


def test_transcription_requests_word_timestamps_and_optional_language(monkeypatch, tmp_path: Path):
    media = tmp_path / "sample.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "Hello world", "language": "en", "segments": [
                {"start": 0, "end": 1.1, "text": "Hello world"}
            ]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["body"] = request.data
        return FakeResponse()
    monkeypatch.setattr(speech.urllib.request, "urlopen", fake_urlopen)
    result = speech.transcribe_media(media, language="en")
    assert result["available"] is True
    assert b"\r\nword\r\n" in captured["body"]
    assert b'name="language"\r\n\r\nen\r\n' in captured["body"]


def test_normalize_segments_preserves_word_timestamps():
    result = speech.normalize_segments([{
        "start": 0.0, "end": 1.25, "text": "Hello world",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.48},
            {"word": "world", "start": 0.52, "end": 1.25},
        ],
    }])
    assert len(result) == 1
    assert result[0]["words"][0]["word"] == "Hello"
    assert result[0]["words"][1]["end"] == 1.25


def test_subtitle_export_formats_timestamped_segments():
    segments = [{"start": 1.2, "end": 2.4, "text": "Hello world"}]
    srt = speech.subtitles(segments, "srt")
    vtt = speech.subtitles(segments, "vtt")
    assert "00:00:01,200 --> 00:00:02,400" in srt
    assert "WEBVTT" in vtt
    assert "00:00:01.200 --> 00:00:02.400" in vtt


def test_transcription_multipart_filename_is_not_taken_from_uploaded_file(monkeypatch, tmp_path: Path):
    media = tmp_path / 'clip\r\nContent-Type: text_plain".wav'
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "Safe", "segments": [
                {"start": 0, "end": 1, "text": "Safe"}
            ]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(speech.urllib.request, "urlopen", fake_urlopen)
    result = speech.transcribe_media(media)

    assert result["available"] is True
    assert b'filename="flexy-media-upload"' in captured["body"]
    assert b'Content-Type: text/plain' not in captured["body"]

@pytest.mark.parametrize("language", ["en\\r\\nX-Evil: yes", "en;boundary=bad", "<script>", "a", "x" * 21])
def test_transcription_rejects_unsafe_language_tags_before_provider_call(monkeypatch, tmp_path, language):
    media = tmp_path / "sample.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")

    def unexpected_urlopen(*args, **kwargs):
        pytest.fail("Provider must not be called for an invalid language tag")

    monkeypatch.setattr(speech.urllib.request, "urlopen", unexpected_urlopen)
    with pytest.raises(ValueError, match="Language must be"):
        speech.transcribe_media(media, language=language)


def test_transcription_normalizes_language_tag(monkeypatch, tmp_path):
    media = tmp_path / "sample.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "Hello", "segments": [{"start": 0, "end": 1, "text": "Hello"}]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(speech.urllib.request, "urlopen", fake_urlopen)
    speech.transcribe_media(media, language=" en-US ")
    assert b'name="language"\r\n\r\nen-US\r\n' in captured["body"]


def test_analyze_transcript_reports_speaking_rate_pauses_and_english_fillers():
    result = speech.analyze_transcript([
        {"start": 0, "end": 1.0, "text": "Um, hello there", "words": [
            {"word": "Um", "start": 0, "end": 0.2},
            {"word": "hello", "start": 0.25, "end": 0.6},
            {"word": "there", "start": 0.65, "end": 1.0},
        ]},
        {"start": 2.0, "end": 3.0, "text": "I mean, welcome", "words": [
            {"word": "welcome", "start": 2.2, "end": 3.0},
        ]},
    ])
    assert result["segment_count"] == 2
    assert result["word_count"] == 6
    assert result["word_timestamps"] == 4
    assert result["speaking_rate_wpm"] == 120.0
    assert result["long_pauses"] == [{"start": 1.0, "end": 2.0, "duration": 1.0}]
    assert result["filler_word_counts"] == {"um": 1, "i mean": 1}


def test_analyze_transcript_handles_empty_and_non_word_timed_segments():
    empty = speech.analyze_transcript([])
    assert empty["word_count"] == 0
    assert empty["speaking_rate_wpm"] is None
    result = speech.analyze_transcript([{"start": 1, "end": 3, "text": "A short line"}])
    assert result["word_count"] == 3
    assert result["speaking_rate_wpm"] == 90.0
    assert result["word_timestamps"] == 0


def test_large_media_is_chunked_and_timestamps_are_restored(monkeypatch, tmp_path: Path):
    import subprocess

    media = tmp_path / "long-video.mp4"
    with media.open("wb") as handle:
        handle.truncate(26 * 1024 * 1024)
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    monkeypatch.setenv("FLEXY_AI_BASE_URL", "https://speech.example/v1")
    monkeypatch.setenv("FLEXY_SPEECH_MODEL", "whisper-test")

    ffmpeg_calls = []
    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="500", stderr="")
        ffmpeg_calls.append(command)
        Path(command[-1]).write_bytes(b"small-audio-chunk")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "hello", "language": "en", "segments": [
                {"start": 1, "end": 2, "text": "hello", "words": [
                    {"word": "hello", "start": 1, "end": 2}
                ]}
            ]}).encode()

    monkeypatch.setattr(speech.subprocess, "run", fake_run)
    monkeypatch.setattr(speech.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    result = speech.transcribe_media(media)

    assert len(ffmpeg_calls) == 2
    assert result["chunking"] == {"enabled": True, "chunk_count": 2, "chunk_duration_seconds": 480.0}
    assert [segment["start"] for segment in result["segments"]] == [1.0, 481.0]
    assert result["segments"][1]["words"][0]["start"] == 481.0
    assert result["analysis"]["segment_count"] == 2


def test_large_media_requires_ffprobe(monkeypatch, tmp_path: Path):
    import subprocess

    media = tmp_path / "long-video.mp4"
    with media.open("wb") as handle:
        handle.truncate(26 * 1024 * 1024)
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    def fail_probe(*args, **kwargs):
        raise FileNotFoundError("ffprobe")
    monkeypatch.setattr(speech.subprocess, "run", fail_probe)
    with pytest.raises(speech.SpeechProviderError, match="FFmpeg and FFprobe"):
        speech.transcribe_media(media)


def test_transcript_analysis_generates_non_destructive_editing_suggestions():
    result = speech.analyze_transcript([
        {"start": 0, "end": 1, "text": "Um, this is a test"},
        {"start": 3.5, "end": 4.5, "text": "You know, another line"},
    ])
    kinds = {item["type"] for item in result["editing_suggestions"]}
    assert "review_pause" in kinds
    assert "review_fillers" in kinds
    assert "word_timing_unavailable" in kinds
    assert all("action" in item for item in result["editing_suggestions"])


def test_detect_silence_parses_ffmpeg_intervals(monkeypatch, tmp_path):
    import subprocess
    media = tmp_path / "audio.wav"
    media.write_bytes(b"fake")
    def fake_run(command, **kwargs):
        assert "silencedetect=noise=-35.0dB:d=0.40" in command
        return subprocess.CompletedProcess(command, 0, stdout="",
            stderr="[silencedetect] silence_start: 1.250\n[silencedetect] silence_end: 2.750 | silence_duration: 1.500\n")
    monkeypatch.setattr(speech.subprocess, "run", fake_run)
    result = speech.detect_silence(media)
    assert result["silence_count"] == 1
    assert result["silences"][0]["start"] == 1.25
    assert result["silences"][0]["duration"] == 1.5


def test_detect_silence_validates_thresholds(tmp_path):
    media = tmp_path / "audio.wav"
    media.write_bytes(b"fake")
    with pytest.raises(ValueError, match="threshold"):
        speech.detect_silence(media, noise_db=0)
    with pytest.raises(ValueError, match="duration"):
        speech.detect_silence(media, min_duration=0)



def test_normalize_segments_preserves_provider_speaker_labels():
    result = speech.normalize_segments([
        {"start": 0, "end": 1, "text": "Hello", "speaker_id": "speaker_0"},
        {"start": 1, "end": 2, "text": "Hi", "speaker_id": "speaker_1"},
    ])
    assert [item["speaker_id"] for item in result] == ["speaker_0", "speaker_1"]


def test_transcript_analysis_reports_provider_speaker_turns():
    result = speech.analyze_transcript([
        {"start": 0, "end": 1, "text": "Hello there", "speaker_id": "speaker_0"},
        {"start": 1.2, "end": 2, "text": "Hi", "speaker_id": "speaker_1"},
        {"start": 2.1, "end": 3, "text": "Welcome back", "speaker_id": "speaker_0"},
    ])
    assert result["speaker_analysis"]["available"] is True
    assert result["speaker_analysis"]["speaker_count"] == 2
    assert len(result["speaker_analysis"]["speaker_changes"]) == 2
    assert {item["speaker_id"] for item in result["speaker_analysis"]["speakers"]} == {"speaker_0", "speaker_1"}


def test_diarized_transcription_uses_configured_model_and_labels(monkeypatch, tmp_path):
    media = tmp_path / "dialogue.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    monkeypatch.setenv("FLEXY_SPEECH_DIARIZATION_MODEL", "gpt-4o-transcribe-diarize")
    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "Hello. Hi.", "segments": [
                {"start": 0, "end": 0.8, "text": "Hello.", "speaker_id": "speaker_0"},
                {"start": 1, "end": 1.5, "text": "Hi.", "speaker_id": "speaker_1"},
            ]}).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(speech.urllib.request, "urlopen", fake_urlopen)
    result = speech.transcribe_media(media)
    assert b"gpt-4o-transcribe-diarize" in captured["body"]
    assert b"diarized_json" in captured["body"]
    assert b"chunking_strategy" in captured["body"]
    assert result["diarization"]["enabled"] is True
    assert result["analysis"]["speaker_analysis"]["speaker_count"] == 2


def test_diarization_requires_provider_speaker_labels(monkeypatch, tmp_path):
    media = tmp_path / "dialogue.wav"
    media.write_bytes(b"fake-audio")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    monkeypatch.setenv("FLEXY_SPEECH_DIARIZATION_MODEL", "diarize-test")

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"text": "No labels", "segments": [
                {"start": 0, "end": 1, "text": "No labels"}
            ]}).encode()

    monkeypatch.setattr(speech.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(speech.SpeechProviderError, match="no speaker labels"):
        speech.transcribe_media(media)



def test_subtitle_export_can_include_speaker_labels_without_changing_default():
    segments = [{"start": 0, "end": 1, "text": "Hello", "speaker_id": "speaker_0"}]
    assert "[speaker_0] Hello" not in speech.subtitles(segments, "srt")
    assert "[speaker_0] Hello" in speech.subtitles(segments, "srt", include_speaker_labels=True)
    assert "<v speaker_0>Hello</v>" in speech.subtitles(segments, "vtt", include_speaker_labels=True)


def test_dialogue_edit_plan_groups_speaker_turns_and_pause_boundaries():
    result = speech.build_dialogue_edit_plan([
        {"start": 0, "end": 1, "text": "We should go", "speaker_id": "speaker_0"},
        {"start": 1.1, "end": 2, "text": "I agree", "speaker_id": "speaker_1"},
        {"start": 4.5, "end": 5.5, "text": "Let's leave", "speaker_id": "speaker_0"},
    ])
    assert result["block_count"] == 2
    assert result["blocks"][0]["kind"] == "speaker_exchange"
    assert result["blocks"][0]["speaker_ids"] == ["speaker_0", "speaker_1"]
    assert any(item["reason"] == "long_pause" for item in result["cut_candidates"])
    assert result["cut_candidates"][0]["review_only"] is True


def test_dialogue_edit_plan_does_not_invent_speaker_labels():
    result = speech.build_dialogue_edit_plan([
        {"start": 0, "end": 1, "text": "Hello"},
        {"start": 1.1, "end": 2, "text": "Welcome"},
    ])
    assert result["speaker_labels_available"] is False
    assert result["blocks"][0]["kind"] == "dialogue"
    assert result["boundary_count"] == 0


@pytest.mark.parametrize("kwargs", [
    {"pause_threshold": 0.1}, {"pause_threshold": 11},
    {"max_block_duration": 2}, {"max_block_duration": 121},
])
def test_dialogue_edit_plan_rejects_out_of_range_controls(kwargs):
    with pytest.raises(ValueError):
        speech.build_dialogue_edit_plan([], **kwargs)
