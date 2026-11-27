"""Optional speech transcription and subtitle formatting for FLEXY AI.

No synthetic transcript is generated when a provider is unavailable. The provider
returns timestamped segments when supported; subtitle formatting is deterministic
and can be used independently of a live API connection.
"""
from __future__ import annotations

import json
import os
import re
import math
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class SpeechProviderError(RuntimeError):
    pass


def speech_is_configured() -> bool:
    return bool(os.getenv("FLEXY_AI_API_KEY", "").strip())


def _timestamp(value: float, *, comma: bool) -> str:
    millis = max(0, round(float(value) * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    separator = "," if comma else "."
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def normalize_segments(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items[:5000]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()[:1000]
        try:
            start = max(0.0, float(item.get("start", 0)))
            end = max(0.0, float(item.get("end", start)))
        except (TypeError, ValueError):
            continue
        if not text or end <= start:
            continue
        segment: dict[str, Any] = {"id": str(item.get("id") or uuid.uuid4()),
                                   "start": round(start, 3), "end": round(end, 3), "text": text}
        words = item.get("words")
        if isinstance(words, list):
            clean_words = []
            for word in words[:200]:
                if not isinstance(word, dict):
                    continue
                word_text = str(word.get("word", word.get("text", ""))).strip()[:100]
                try:
                    word_start = max(0.0, float(word["start"]))
                    word_end = max(word_start, float(word["end"]))
                except (KeyError, TypeError, ValueError):
                    continue
                if word_text and word_end > word_start:
                    clean_words.append({"word": word_text, "start": round(word_start, 3), "end": round(word_end, 3)})
            if clean_words:
                segment["words"] = clean_words
        speaker_id = item.get("speaker_id")
        if isinstance(speaker_id, str) and speaker_id.strip():
            segment["speaker_id"] = speaker_id.strip()[:64]
        result.append(segment)
    return sorted(result, key=lambda segment: (segment["start"], segment["end"]))



def analyze_transcript(segments: Any) -> dict[str, Any]:
    """Return transparent, timestamp-derived speech metrics for a transcript.

    Speaker statistics are included only for explicit provider-supplied labels.
    This does not verify real-world identity or semantically judge what was said.
    Filler detection is limited to a small English-language vocabulary.
    """
    normalized = normalize_segments(segments)
    words = [word for segment in normalized for word in segment.get("words", [])]
    token_pattern = re.compile(r"[\w’']+", re.UNICODE)
    total_words = sum(len(token_pattern.findall(segment["text"])) for segment in normalized)
    if words:
        speech_start = min(word["start"] for word in words)
        speech_end = max(word["end"] for word in words)
    elif normalized:
        speech_start = normalized[0]["start"]
        speech_end = normalized[-1]["end"]
    else:
        speech_start = speech_end = 0.0
    active_duration = max(0.0, speech_end - speech_start)
    speaking_rate = round(total_words * 60 / active_duration, 1) if active_duration > 0 else None

    pauses = []
    for previous, current in zip(normalized, normalized[1:]):
        gap = round(current["start"] - previous["end"], 3)
        if gap >= 0.6:
            pauses.append({"start": round(previous["end"], 3), "end": round(current["start"], 3), "duration": gap})

    # Speaker IDs are only reported when the configured provider actually returns
    # diarized segments. Never infer a speaker from transcript text or timing.
    speaker_segments = [segment for segment in normalized if segment.get("speaker_id")]
    speaker_ids = sorted({segment["speaker_id"] for segment in speaker_segments})
    speaker_durations: dict[str, float] = {}
    speaker_word_counts: dict[str, int] = {}
    for segment in speaker_segments:
        speaker = segment["speaker_id"]
        speaker_durations[speaker] = round(speaker_durations.get(speaker, 0.0) + segment["end"] - segment["start"], 3)
        speaker_word_counts[speaker] = speaker_word_counts.get(speaker, 0) + len(token_pattern.findall(segment["text"]))
    speaker_changes = []
    for previous, current in zip(normalized, normalized[1:]):
        old_speaker, new_speaker = previous.get("speaker_id"), current.get("speaker_id")
        if old_speaker and new_speaker and old_speaker != new_speaker:
            speaker_changes.append({"at": round(current["start"], 3), "from": old_speaker, "to": new_speaker})

    filler_terms = ("you know", "i mean", "um", "uh", "erm", "ah", "hmm")
    filler_counts: dict[str, int] = {}
    for segment in normalized:
        lowered = segment["text"].lower()
        for term in filler_terms:
            count = len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", lowered))
            if count:
                filler_counts[term] = filler_counts.get(term, 0) + count
    suggestions: list[dict[str, Any]] = []
    for pause in pauses:
        if pause["duration"] >= 1.2:
            suggestions.append({
                "type": "review_pause", "start": pause["start"], "end": pause["end"],
                "priority": "high" if pause["duration"] >= 2.5 else "normal",
                "reason": f"A {pause['duration']:.1f}s gap appears between transcript segments.",
                "action": "Review this gap and trim it if it is not intentional.",
            })
    if filler_counts:
        suggestions.append({
            "type": "review_fillers", "priority": "normal",
            "count": sum(filler_counts.values()), "terms": filler_counts,
            "reason": "Potential English filler words were found in the transcript.",
            "action": "Review each occurrence before removing it to preserve the speaker's meaning.",
        })
    if speaking_rate is not None and speaking_rate > 190:
        suggestions.append({"type": "review_pacing", "priority": "normal",
                            "reason": f"Estimated speaking rate is {speaking_rate} words per minute.",
                            "action": "Consider shorter caption groups or a slightly longer caption display time."})
    elif speaking_rate is not None and 0 < speaking_rate < 85:
        suggestions.append({"type": "review_pacing", "priority": "low",
                            "reason": f"Estimated speaking rate is {speaking_rate} words per minute.",
                            "action": "Check whether long gaps are intentional before tightening the edit."})
    if normalized and not words:
        suggestions.append({"type": "word_timing_unavailable", "priority": "low",
                            "reason": "The provider returned segment timing but no word-level timing.",
                            "action": "Use segment captions or run a provider that supports word timestamps for karaoke-style captions."})
    return {
        "segment_count": len(normalized),
        "word_count": total_words,
        "word_timestamps": len(words),
        "active_duration_seconds": round(active_duration, 3),
        "speaking_rate_wpm": speaking_rate,
        "long_pauses": pauses[:200],
        "filler_word_counts": filler_counts,
        "speaker_analysis": {
            "available": bool(speaker_ids),
            "speaker_count": len(speaker_ids),
            "speakers": [{"speaker_id": speaker, "segment_count": sum(1 for segment in speaker_segments if segment["speaker_id"] == speaker),
                          "estimated_speech_seconds": speaker_durations[speaker],
                          "word_count": speaker_word_counts[speaker]} for speaker in speaker_ids],
            "speaker_changes": speaker_changes[:500],
        },
        "editing_suggestions": suggestions[:250],
        "notice": "Metrics are estimates from transcript text and timestamps. Filler detection is English-only. Speaker labels are provider-generated only when diarization is enabled; they are not identity verification. Suggestions are review points, not automatic cuts.",
    }

def subtitles(segments: Any, fmt: str = "srt", *, include_speaker_labels: bool = False) -> str:
    normalized = normalize_segments(segments)
    if fmt not in {"srt", "vtt"}:
        raise ValueError("Subtitle format must be srt or vtt.")
    lines = ["WEBVTT", ""] if fmt == "vtt" else []
    for index, segment in enumerate(normalized, 1):
        start = _timestamp(segment["start"], comma=fmt == "srt")
        end = _timestamp(segment["end"], comma=fmt == "srt")
        text = segment["text"]
        speaker = segment.get("speaker_id") if include_speaker_labels else None
        if speaker:
            # Provider IDs are constrained during normalization and escaped for
            # WebVTT voice-cue syntax; no raw markup from transcript text is added.
            safe_speaker = re.sub(r"[^A-Za-z0-9_-]", "_", str(speaker))[:64]
            text = f"[{safe_speaker}] {text}" if fmt == "srt" else f"<v {safe_speaker}>{text}</v>"
        if fmt == "srt":
            lines.extend([str(index), f"{start} --> {end}", text, ""])
        else:
            lines.extend([f"{start} --> {end}", text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _normalize_language(language: str | None) -> str | None:
    """Accept a compact BCP-47-like language tag safe for multipart fields."""
    if language is None or not language.strip():
        return None
    value = language.strip()
    if len(value) > 20 or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value):
        raise ValueError("Language must be a valid short language tag, such as en or en-US.")
    return value


def _transcribe_diarized_file(path: Path, *, timeout: float, language: str | None) -> dict[str, Any]:
    """Use an explicitly configured diarization-capable provider model.

    OpenAI-compatible providers differ, so diarization is opt-in via
    FLEXY_SPEECH_DIARIZATION_MODEL. The provider must return diarized_json with
    segment-level speaker_id values. No speaker labels are fabricated.
    """
    base = os.getenv("FLEXY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip()
    if not model:
        raise SpeechProviderError("Speaker diarization is not configured. Set FLEXY_SPEECH_DIARIZATION_MODEL to a provider-supported diarization model.")
    boundary = "----FLEXY" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\ndiarized_json\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chunking_strategy\"\r\n\r\nauto\r\n".encode(),
        *([f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{language}\r\n".encode()] if language else []),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"flexy-media-upload\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
        path.read_bytes(), f"\r\n--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        base + "/audio/transcriptions", data=b"".join(parts),
        headers={"Authorization": f"Bearer {os.getenv('FLEXY_AI_API_KEY', '').strip()}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SpeechProviderError(f"Diarization provider request failed: {type(exc).__name__}.") from exc
    segments = normalize_segments(raw.get("segments", []))
    if not segments or not any(segment.get("speaker_id") for segment in segments):
        raise SpeechProviderError("The configured diarization model returned no speaker labels. Check that the provider supports diarized_json output.")
    text = str(raw.get("text", "")).strip()[:100_000]
    if not text:
        text = " ".join(segment["text"] for segment in segments)
    return {"available": True, "provider": "openai_compatible", "model": model,
            "text": text, "language": raw.get("language"), "segments": segments,
            "diarization": {"enabled": True, "speaker_count": len({s["speaker_id"] for s in segments if s.get("speaker_id")}),
                            "notice": "Speaker labels are provider-generated labels, not verified real-world identities."}}


def _transcribe_single_file(path: Path, *, timeout: float, language: str | None) -> dict[str, Any]:
    """Send one provider-sized media file and normalize its timestamped result."""
    base = os.getenv("FLEXY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("FLEXY_SPEECH_MODEL", "whisper-1").strip()
    boundary = "----FLEXY" + uuid.uuid4().hex
    # Never place an uploaded filename in a multipart header. The stored name may
    # originate from an untrusted client and could contain header control chars.
    filename = "flexy-media-upload"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\nverbose_json\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"timestamp_granularities[]\"\r\n\r\nsegment\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"timestamp_granularities[]\"\r\n\r\nword\r\n".encode(),
        *([f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{language}\r\n".encode()]
          if language else []),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    request = urllib.request.Request(
        base + "/audio/transcriptions", data=b"".join(parts),
        headers={"Authorization": f"Bearer {os.getenv('FLEXY_AI_API_KEY', '').strip()}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        segments = normalize_segments(raw.get("segments", []))
        # Some compatible providers return word timestamps separately. Preserve
        # them by attaching each word to its containing segment when possible.
        raw_words = raw.get("words", [])
        if isinstance(raw_words, list) and raw_words:
            words = normalize_segments([{
                "start": item.get("start"), "end": item.get("end"),
                "text": item.get("word", item.get("text", "")),
            } for item in raw_words if isinstance(item, dict)])
            for segment in segments:
                segment_words = [
                    {"word": word["text"], "start": word["start"], "end": word["end"]}
                    for word in words
                    if word["start"] >= segment["start"] - 0.05
                    and word["end"] <= segment["end"] + 0.05
                ]
                if segment_words:
                    segment["words"] = segment_words
        text = str(raw.get("text", "")).strip()[:100_000]
        if not text and segments:
            text = " ".join(segment["text"] for segment in segments)
        return {"available": True, "provider": "openai_compatible", "model": model,
                "text": text, "language": raw.get("language"), "segments": segments}
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SpeechProviderError(f"Speech provider request failed: {type(exc).__name__}.") from exc


def _transcribe_large_media(path: Path, *, timeout: float, language: str | None) -> dict[str, Any]:
    """Extract bounded audio chunks and merge their timestamps into source time."""
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        duration = float(probe.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SpeechProviderError("Large-media transcription needs FFmpeg and FFprobe to read the audio duration.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise SpeechProviderError("Could not determine a valid duration for this media file.")
    if duration > 12 * 60 * 60:
        raise SpeechProviderError("Transcription is limited to 12 hours per media file. Split the source into shorter projects.")

    chunk_seconds = 480.0
    merged_segments: list[dict[str, Any]] = []
    transcript_parts: list[str] = []
    detected_language = None
    chunk_count = math.ceil(duration / chunk_seconds)
    try:
        with tempfile.TemporaryDirectory(prefix="flexy-speech-") as temp_dir:
            for index in range(chunk_count):
                offset = index * chunk_seconds
                chunk_duration = min(chunk_seconds, duration - offset)
                chunk_path = Path(temp_dir) / f"speech-{index:04d}.mp3"
                try:
                    subprocess.run(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                         "-ss", f"{offset:.3f}", "-i", str(path), "-t", f"{chunk_duration:.3f}",
                         "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
                         "-b:a", "48k", "-f", "mp3", str(chunk_path)],
                        capture_output=True, text=True, timeout=max(60, timeout), check=True,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    raise SpeechProviderError(f"Could not prepare speech audio chunk {index + 1}.") from exc
                if not chunk_path.is_file() or chunk_path.stat().st_size == 0:
                    raise SpeechProviderError(f"Audio extraction produced an empty chunk ({index + 1}).")
                if chunk_path.stat().st_size > 25 * 1024 * 1024:
                    raise SpeechProviderError(f"Extracted audio chunk {index + 1} still exceeds the provider's 25 MB limit.")
                result = (_transcribe_diarized_file(chunk_path, timeout=timeout, language=language)
                          if os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip()
                          else _transcribe_single_file(chunk_path, timeout=timeout, language=language))
                detected_language = detected_language or result.get("language")
                if result.get("text"):
                    transcript_parts.append(str(result["text"]))
                for segment in result.get("segments", []):
                    adjusted = {**segment,
                                "id": f"chunk-{index}-{segment.get('id', 'segment')}",
                                "start": round(float(segment["start"]) + offset, 3),
                                "end": round(min(duration, float(segment["end"]) + offset), 3)}
                    if adjusted["end"] <= adjusted["start"]:
                        continue
                    if isinstance(segment.get("words"), list):
                        adjusted["words"] = [
                            {**word, "start": round(float(word["start"]) + offset, 3),
                             "end": round(min(duration, float(word["end"]) + offset), 3)}
                            for word in segment["words"]
                        ]
                    merged_segments.append(adjusted)
    except SpeechProviderError:
        raise
    normalized = normalize_segments(merged_segments)
    return {
        "available": True, "provider": "openai_compatible",
        "model": (os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip()
                  or os.getenv("FLEXY_SPEECH_MODEL", "whisper-1").strip()),
        "text": " ".join(transcript_parts)[:100_000], "language": detected_language,
        "segments": normalized, "analysis": analyze_transcript(normalized),
        "diarization": {"enabled": bool(os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip()),
                        "speaker_count": len({s["speaker_id"] for s in normalized if s.get("speaker_id")}),
                        "notice": "Speaker labels are namespaced per audio chunk; cross-chunk identity matching is not claimed."}
                       if os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip() else {"enabled": False},
        "chunking": {"enabled": True, "chunk_count": chunk_count, "chunk_duration_seconds": chunk_seconds},
        "notice": "Long-media transcription was processed in audio-only chunks. Segment and word times were restored to the original media timeline. Review timing and wording before publishing.",
    }


def detect_silence(path: Path, *, noise_db: float = -35.0, min_duration: float = 0.4) -> dict[str, Any]:
    """Detect low-volume intervals with FFmpeg; intervals are review suggestions, not cuts."""
    if not path.is_file():
        raise SpeechProviderError("Media file was not found.")
    if not math.isfinite(noise_db) or not -90 <= noise_db <= -10:
        raise ValueError("Silence threshold must be between -90 and -10 dB.")
    if not math.isfinite(min_duration) or not 0.1 <= min_duration <= 10:
        raise ValueError("Minimum silence duration must be between 0.1 and 10 seconds.")
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
               "-af", f"silencedetect=noise={noise_db:.1f}dB:d={min_duration:.2f}", "-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SpeechProviderError("Silence detection requires FFmpeg to be installed and available.") from exc
    output = (result.stderr or "") + "\n" + (result.stdout or "")
    if result.returncode != 0:
        raise SpeechProviderError("FFmpeg could not analyze this media's audio stream.")
    starts = re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", output)
    ends = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", output)
    intervals = []
    for index, start in enumerate(starts):
        begin = max(0.0, float(start))
        if index < len(ends):
            finish = max(begin, float(ends[index]))
        else:
            duration_match = re.search(r"silence_duration:\s*(\d+(?:\.\d+)?)", output[output.find(f"silence_start: {start}"):])
            finish = begin + float(duration_match.group(1)) if duration_match else begin
        if finish - begin >= min_duration:
            intervals.append({"start": round(begin, 3), "end": round(finish, 3),
                              "duration": round(finish - begin, 3),
                              "suggestion": "Review this quiet interval; keep it if it is intentional."})
    return {"available": True, "method": "ffmpeg_silencedetect", "threshold_db": noise_db,
            "minimum_duration_seconds": min_duration, "silence_count": len(intervals),
            "silences": intervals[:2000],
            "notice": "Low-volume intervals are detected from the audio signal. Background music, room tone, and quiet speech can affect results. No media is modified."}


def transcribe_media(path: Path, *, timeout: float = 90, language: str | None = None) -> dict[str, Any]:
    language = _normalize_language(language)
    key = os.getenv("FLEXY_AI_API_KEY", "").strip()
    if not key:
        return {"available": False, "provider": None, "text": "", "segments": [],
                "notice": "Speech AI is not configured. Set FLEXY_AI_API_KEY on the backend to enable transcription."}
    if not path.is_file():
        raise SpeechProviderError("Media file was not found.")
    if path.stat().st_size > 25 * 1024 * 1024:
        return _transcribe_large_media(path, timeout=timeout, language=language)
    result = (_transcribe_diarized_file(path, timeout=timeout, language=language)
              if os.getenv("FLEXY_SPEECH_DIARIZATION_MODEL", "").strip()
              else _transcribe_single_file(path, timeout=timeout, language=language))
    result["analysis"] = analyze_transcript(result.get("segments", []))
    result["notice"] = ("Machine-generated transcription with provider speaker labels. Labels are not verified identities. Review speaker turns, names, punctuation and timing before publishing."
                        if result.get("diarization", {}).get("enabled") else
                        "Machine-generated transcription with segment and, when supported, word timing. Review names, punctuation and timing before publishing.")
    return result



def build_dialogue_edit_plan(segments: Any, *, pause_threshold: float = 1.2, max_block_duration: float = 24.0) -> dict[str, Any]:
    """Group transcript into reviewable dialogue beats and non-destructive cut points.

    Blocks are transcript-derived editing units, not claims about visual scenes.
    Speaker boundaries are used only when provider labels are present.
    """
    if not math.isfinite(float(pause_threshold)) or not 0.2 <= float(pause_threshold) <= 10:
        raise ValueError("pause_threshold must be between 0.2 and 10 seconds.")
    if not math.isfinite(float(max_block_duration)) or not 3 <= float(max_block_duration) <= 120:
        raise ValueError("max_block_duration must be between 3 and 120 seconds.")

    normalized = normalize_segments(segments)
    blocks: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        speakers = list(dict.fromkeys(seg["speaker_id"] for seg in current if seg.get("speaker_id")))
        blocks.append({
            "block_id": f"dialogue_{len(blocks) + 1}",
            "start": current[0]["start"], "end": current[-1]["end"],
            "duration": round(current[-1]["end"] - current[0]["start"], 3),
            "text": " ".join(seg["text"] for seg in current),
            "segment_ids": [seg["id"] for seg in current],
            "speaker_ids": speakers,
            "kind": "speaker_exchange" if len(speakers) > 1 else "speaker_turn" if speakers else "dialogue",
        })
        current.clear()

    for segment in normalized:
        if current:
            previous = current[-1]
            gap = max(0.0, segment["start"] - previous["end"])
            previous_speaker, next_speaker = previous.get("speaker_id"), segment.get("speaker_id")
            speaker_change = bool(previous_speaker and next_speaker and previous_speaker != next_speaker)
            elapsed = segment["end"] - current[0]["start"]
            reason = "long_pause" if gap >= pause_threshold else "speaker_change" if speaker_change else "max_block_duration" if elapsed > max_block_duration else None
            if reason:
                if reason in {"long_pause", "max_block_duration"}:
                    flush()
                boundaries.append({
                    "at": round(segment["start"], 3), "previous_end": round(previous["end"], 3),
                    "gap_seconds": round(gap, 3), "reason": reason,
                    "review_only": True,
                    "suggestion": "Review this boundary as a possible dialogue cut; keep natural pauses that support meaning or performance.",
                })
        current.append(segment)
    flush()

    return {
        "available": bool(normalized),
        "block_count": len(blocks), "blocks": blocks,
        "boundary_count": len(boundaries), "cut_candidates": boundaries,
        "speaker_labels_available": any(seg.get("speaker_id") for seg in normalized),
        "notice": "Dialogue blocks and cut candidates are generated from transcript timing and provider speaker labels only. They are review suggestions, not automatic edits or visual scene detection.",
    }
