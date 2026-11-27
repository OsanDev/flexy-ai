"""Scene- and dialogue-aware timeline drafting using supplied evidence only."""
from __future__ import annotations
from typing import Any
import math


def build_smart_timeline(
    assets: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    transcript_segments: list[dict[str, Any]],
    target_duration: float,
    style: str = "balanced",
    max_shot_duration: float | None = None,
    min_shot_duration: float | None = None,
    beat_times: list[float] | None = None,
) -> dict[str, Any]:
    if style not in {"balanced", "dynamic", "calm"}:
        raise ValueError("Style must be balanced, dynamic, or calm.")
    if not math.isfinite(target_duration) or not 1 <= target_duration <= 600:
        raise ValueError("Target duration must be between 1 and 600 seconds.")
    if max_shot_duration is not None and (not math.isfinite(max_shot_duration) or not 0.5 <= max_shot_duration <= 15):
        raise ValueError("Maximum shot duration must be between 0.5 and 15 seconds.")
    if min_shot_duration is not None and (not math.isfinite(min_shot_duration) or not 0.5 <= min_shot_duration <= 10):
        raise ValueError("Minimum shot duration must be between 0.5 and 10 seconds.")
    if min_shot_duration is not None and max_shot_duration is not None and min_shot_duration > max_shot_duration:
        raise ValueError("Minimum shot duration cannot exceed maximum shot duration.")

    # Beat markers must come from an upstream audio analyzer or an explicit user source.
    # This function aligns edits to supplied markers; it does not claim to detect beats.
    valid_beats: list[float] = []
    for marker in beat_times or []:
        if isinstance(marker, (int, float)) and math.isfinite(float(marker)) and float(marker) >= 0:
            value = float(marker)
            if not valid_beats or value > valid_beats[-1]:
                valid_beats.append(value)
    beat_gaps = [b - a for a, b in zip(valid_beats, valid_beats[1:])
                 if 0.25 <= b - a <= 2.0]
    beat_interval = None
    if len(beat_gaps) >= 2:
        ordered_gaps = sorted(beat_gaps)
        middle = len(ordered_gaps) // 2
        beat_interval = (ordered_gaps[middle] if len(ordered_gaps) % 2
                         else (ordered_gaps[middle - 1] + ordered_gaps[middle]) / 2)

    visual_assets = [a for a in assets if a.get("type") == "video" and a.get("id")]
    audio_assets = [a for a in assets if a.get("type") == "audio" and a.get("id")]
    if not visual_assets:
        return {"engine": "scene_dialogue_rules_v1", "clips": [], "audio_clips": [],
                "duration": 0, "target_duration": target_duration,
                "warnings": ["Import at least one video asset to build a scene-aware timeline."]}

    # Validate and normalize transcript evidence. No speech is inferred.
    dialogue: list[tuple[float, float]] = []
    for segment in transcript_segments:
        if not isinstance(segment, dict):
            continue
        try:
            start, end = float(segment["start"]), float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(start) and math.isfinite(end) and 0 <= start < end and str(segment.get("text", "")).strip():
            dialogue.append((start, end))

    # Rank candidate shots using only supplied transcript timing and scene duration.
    # Selection uses ranking to choose useful footage, then restores source order so
    # the resulting edit remains understandable and deterministic.
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    for asset in visual_assets:
        try:
            source_duration = float(asset.get("duration") or 0)
        except (TypeError, ValueError):
            source_duration = 0
        if not math.isfinite(source_duration) or source_duration <= 0:
            warnings.append(f"Duration is unknown for {asset.get('name', asset['id'])}; this asset was skipped.")
            continue

        raw = scenes if len(visual_assets) == 1 else asset.get("scenes", [])
        scene_by_start: dict[float, dict[str, Any]] = {}
        for scene in raw:
            if not isinstance(scene, dict) or not isinstance(scene.get("start"), (int, float)):
                continue
            scene_start_value = float(scene["start"])
            if math.isfinite(scene_start_value) and 0 <= scene_start_value < source_duration:
                scene_by_start[scene_start_value] = scene
        boundaries = sorted(scene_by_start)
        if not boundaries or boundaries[0] > 0:
            boundaries.insert(0, 0.0)
        for index, scene_start in enumerate(boundaries):
            scene_end = boundaries[index + 1] if index + 1 < len(boundaries) else source_duration
            scene_length = scene_end - scene_start
            if scene_length <= 0:
                continue
            overlapping = [(a, b) for a, b in dialogue
                            if min(scene_end, b) > max(scene_start, a)]
            dialogue_seconds = sum(max(0.0, min(scene_end, b) - max(scene_start, a))
                                   for a, b in overlapping)
            dialogue_density = min(1.0, dialogue_seconds / scene_length)
            # Prefer scenes with actual supplied speech, while avoiding a blanket
            # penalty for silent visual material. Duration fit is style-specific.
            preferred = 3.0 if style == "dynamic" else 8.0 if style == "calm" else 5.0
            duration_fit = min(1.0, scene_length / preferred)
            base_score = 70.0 * dialogue_density + 30.0 * duration_fit
            # Optional upstream visual-analysis signals are normalized to [0, 1].
            # This ranker does not claim to run a vision model itself.
            scene_meta = scene_by_start.get(scene_start, {})
            visual_fields = ("visual_interest", "subject_presence", "motion_suitability")
            visual_signals: dict[str, float] = {}
            for field in visual_fields:
                value = scene_meta.get(field)
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    visual_signals[field] = min(1.0, max(0.0, float(value)))
            visual_score = (sum(visual_signals.values()) / len(visual_signals)
                            if visual_signals else None)
            score = (0.75 * base_score + 25.0 * visual_score
                     if visual_score is not None else base_score)
            # Pacing is evidence-led rather than a fixed duration for every shot.
            # Dialogue density gives spoken moments room; supplied motion suitability
            # can shorten dynamic edits. Missing signals remain neutral.
            motion = visual_signals.get("motion_suitability", 0.5)
            if style == "dynamic":
                pacing_factor = 1.0 + 0.10 * dialogue_density - 0.20 * (motion - 0.5)
            elif style == "calm":
                pacing_factor = 1.0 + 0.25 * dialogue_density - 0.05 * (motion - 0.5)
            else:
                pacing_factor = 1.0 + 0.15 * dialogue_density - 0.10 * (motion - 0.5)
            pacing_factor = min(1.25, max(0.75, pacing_factor))
            candidates.append({
                "asset_id": str(asset["id"]), "scene_start": scene_start,
                "scene_end": scene_end, "scene_length": scene_length,
                "dialogue": overlapping, "dialogue_seconds": dialogue_seconds,
                "dialogue_density": dialogue_density, "duration_fit": duration_fit,
                "visual_signals": visual_signals, "visual_score": visual_score,
                "pacing_factor": pacing_factor,
                "score": round(score, 2),
            })

    # Pick the strongest evidence first. Ties are stable by source order.
    preferred = 3.0 if style == "dynamic" else 8.0 if style == "calm" else 5.0
    ranked = sorted(enumerate(candidates), key=lambda item: (-item[1]["score"], item[0]))
    selected: list[dict[str, Any]] = []
    remaining = target_duration
    skipped_for_minimum = 0
    for _, candidate in ranked:
        if remaining <= 0:
            break
        shot_cap = max_shot_duration or 15.0
        shot_floor = min_shot_duration or 0.0
        paced_preferred = preferred * candidate["pacing_factor"]
        desired = min(candidate["scene_length"], max(shot_floor, min(paced_preferred, shot_cap)))
        duration = min(desired, remaining)
        beat_count = None
        if beat_interval is not None:
            # Snap the intended shot length to the nearest whole beat count,
            # while preserving the user's floor/cap and available source length.
            low = max(0.5, shot_floor)
            high = min(shot_cap, candidate["scene_length"], remaining)
            if high >= low:
                beat_count = max(1, round(duration / beat_interval))
                snapped = beat_count * beat_interval
                if low <= snapped <= high:
                    duration = snapped
                else:
                    beat_count = None
        if duration < 0.5:
            continue
        if shot_floor and (candidate["scene_length"] + 1e-9 < shot_floor or remaining + 1e-9 < shot_floor):
            skipped_for_minimum += 1
            continue
        scene_start, scene_end = candidate["scene_start"], candidate["scene_end"]
        source_start = scene_start
        if candidate["dialogue"] and candidate["scene_length"] > duration:
            # Center the shot around the strongest supplied dialogue segment.
            # Longest segment wins; ties resolve to earliest speech.
            speech_start, speech_end = max(
                candidate["dialogue"], key=lambda pair: (pair[1] - pair[0], -pair[0]))
            source_start = min(max(speech_start, scene_start), scene_end - duration)
        selected_end = source_start + duration
        selected_overlap = sum(max(0.0, min(selected_end, b) - max(source_start, a))
                               for a, b in dialogue)
        selected.append({**candidate, "source_start": source_start,
                         "duration": duration, "selected_overlap": selected_overlap,
                         "beat_count": beat_count})
        remaining -= duration

    # Preserve original story order after ranking has chosen the shots.
    selected.sort(key=lambda shot: (shot["asset_id"], shot["scene_start"]))
    clips: list[dict[str, Any]] = []
    cursor = 0.0
    for shot in selected:
        has_dialogue = shot["selected_overlap"] > 0
        clips.append({
            "assetId": shot["asset_id"], "start": round(cursor, 3),
            "sourceStart": round(shot["source_start"], 3),
            "duration": round(shot["duration"], 3),
            "transition": "fade" if clips else "none",
            "evidence": {
                "scene_start": round(shot["scene_start"], 3),
                "dialogue_overlap_seconds": round(shot["selected_overlap"], 3),
                "contains_transcript": has_dialogue,
                "dialogue_density": round(shot["dialogue_density"], 3),
                "duration_fit": round(shot["duration_fit"], 3),
                "visual_signals": shot["visual_signals"],
                "visual_score": (round(shot["visual_score"], 3)
                                 if shot["visual_score"] is not None else None),
                "pacing_factor": round(shot["pacing_factor"], 3),
                "beat_aligned": shot["beat_count"] is not None,
                "beats_per_shot": shot["beat_count"],
                "beat_interval_seconds": (round(beat_interval, 4) if beat_interval is not None else None),
                "shot_score": shot["score"],
            },
            "reason": ("Shot anchored to supplied dialogue; duration adjusted using dialogue density and available motion evidence."
                       if has_dialogue else "Ranked chronological scene; duration adjusted using available motion evidence and style."),
        })
        cursor += shot["duration"]

    audio_clips = []
    if audio_assets:
        audio = audio_assets[0]
        try:
            audio_duration = float(audio.get("duration") or target_duration)
        except (TypeError, ValueError):
            audio_duration = target_duration
        if audio_duration > 0 and cursor > 0:
            audio_clips.append({"assetId": str(audio["id"]), "start": 0.0, "sourceStart": 0.0,
                                "duration": round(min(cursor, audio_duration), 3), "volume": 0.35})

    if not scenes:
        warnings.append("No scene boundaries supplied. A fallback start-at-zero segment was used; run scene detection for better cut points.")
    if beat_times and beat_interval is None:
        warnings.append("Beat sync was not applied: at least three valid, consistently spaced beat markers are required.")
    if beat_interval is not None:
        warnings.append(f"Beat-grid alignment used supplied markers at approximately {60.0 / beat_interval:.1f} BPM. Verify synchronization against the music.")
    if not dialogue:
        warnings.append("No valid transcript segments supplied. Shot selection uses scene boundaries and style only.")
    if skipped_for_minimum:
        warnings.append(f"{skipped_for_minimum} candidate shot(s) were skipped because they could not meet the {min_shot_duration:.1f}s minimum length.")
    if cursor < target_duration:
        warnings.append(f"Selected footage covers {cursor:.1f}s of the requested {target_duration:.1f}s.")
    warnings.append("This is a deterministic first-cut draft, not semantic scene understanding. Review every cut and audio level.")
    return {"engine": "scene_dialogue_rules_v1", "style": style,
            "max_shot_duration": max_shot_duration, "min_shot_duration": min_shot_duration, "clips": clips,
            "audio_clips": audio_clips, "duration": round(cursor, 3),
            "target_duration": round(target_duration, 3), "scene_count": len(scenes),
            "transcript_segment_count": len(dialogue),
            "beat_sync": beat_interval is not None,
            "beat_interval_seconds": round(beat_interval, 4) if beat_interval is not None else None,
            "warnings": warnings}
