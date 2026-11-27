"""Non-destructive, evidence-based edit recommendations for FLEXY AI."""
from __future__ import annotations
from typing import Any


def build_recommendations(
    scenes: list[dict[str, Any]] | None = None,
    transcript_segments: list[dict[str, Any]] | None = None,
    duration: float | None = None,
    style: str = "balanced",
) -> dict[str, Any]:
    scenes = scenes or []
    transcript_segments = transcript_segments or []
    if style not in {"balanced", "dynamic", "calm"}:
        raise ValueError("Style must be balanced, dynamic, or calm.")
    if duration is not None and duration < 0:
        raise ValueError("Duration cannot be negative.")

    recs: list[dict[str, Any]] = []
    valid_scenes = sorted(
        [s for s in scenes if isinstance(s, dict) and isinstance(s.get("start"), (int, float)) and s["start"] >= 0],
        key=lambda s: float(s["start"]),
    )
    if valid_scenes:
        starts = [float(s["start"]) for s in valid_scenes]
        boundaries = starts + ([float(duration)] if duration and duration > starts[-1] else [])
        lengths = [b - a for a, b in zip(boundaries, boundaries[1:]) if b >= a]
        if lengths:
            avg = sum(lengths) / len(lengths)
            long_limit = 7.0 if style == "dynamic" else 12.0 if style == "balanced" else 20.0
            long_scenes = [i for i, length in enumerate(lengths) if length > long_limit]
            if long_scenes:
                recs.append({"id": "review-long-shots", "kind": "pacing", "priority": "medium",
                    "title": "Review longer shots", "detail": f"{len(long_scenes)} detected shot(s) exceed {long_limit:g} seconds. Check whether they need trimming or a cutaway.",
                    "evidence": {"scene_indexes": long_scenes[:20], "average_shot_seconds": round(avg, 2)}, "start": starts[long_scenes[0]]})
            if style == "dynamic" and avg > 5:
                recs.append({"id": "increase-cut-frequency", "kind": "pacing", "priority": "low",
                    "title": "Consider a quicker rhythm", "detail": f"Average detected shot length is {avg:.1f} seconds. For a dynamic edit, test shorter selects while preserving meaning.",
                    "evidence": {"average_shot_seconds": round(avg, 2)}, "start": 0.0})
            elif style == "calm" and avg < 2.5:
                recs.append({"id": "allow-more-breathing-room", "kind": "pacing", "priority": "low",
                    "title": "Consider longer holds", "detail": f"Average detected shot length is {avg:.1f} seconds. A calmer edit may benefit from a few longer holds.",
                    "evidence": {"average_shot_seconds": round(avg, 2)}, "start": 0.0})
    else:
        recs.append({"id": "detect-scenes-first", "kind": "workflow", "priority": "info",
            "title": "Detect scenes first", "detail": "Run scene detection on a video asset to receive shot-pacing recommendations.", "evidence": {}})

    valid_segments = [s for s in transcript_segments if isinstance(s, dict)
        and isinstance(s.get("start"), (int, float)) and isinstance(s.get("end"), (int, float))
        and 0 <= s["start"] < s["end"] and str(s.get("text", "")).strip()]
    valid_segments.sort(key=lambda s: float(s["start"]))
    if valid_segments:
        gaps = []
        for left, right in zip(valid_segments, valid_segments[1:]):
            gap = float(right["start"]) - float(left["end"])
            if gap >= 2.0:
                gaps.append({"start": round(float(left["end"]), 3), "end": round(float(right["start"]), 3), "seconds": round(gap, 2)})
        if gaps:
            recs.append({"id": "review-dialogue-pauses", "kind": "dialogue", "priority": "medium",
                "title": "Review pauses in dialogue", "detail": f"Found {len(gaps)} pause(s) of at least two seconds. Listen before trimming; some pauses may be intentional.",
                "evidence": {"gaps": gaps[:20]}, "start": gaps[0]["start"]})
        else:
            recs.append({"id": "dialogue-covered", "kind": "dialogue", "priority": "info",
                "title": "Dialogue segments are continuous", "detail": "No gaps of two seconds or more were found between the supplied transcript segments.",
                "evidence": {"segment_count": len(valid_segments)}})
    else:
        recs.append({"id": "add-transcript", "kind": "dialogue", "priority": "info",
            "title": "Add a transcript for dialogue-aware suggestions", "detail": "Run Auto subtitles or paste a transcript to analyse dialogue pauses. No speech has been inferred.", "evidence": {}})

    return {"engine": "evidence_rules_v1", "style": style, "recommendation_count": len(recs),
            "recommendations": recs,
            "notice": "Suggestions are non-destructive. Review the footage and audio before applying any edit."}
