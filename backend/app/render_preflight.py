"""Project-scoped validation and non-destructive export preflight checks."""
from __future__ import annotations

from typing import Any

from . import storage
from .rendering import RenderValidationError, validate_render_graph, probe_video_encoders, select_video_encoder


def validate_project_render_graph(project_id: str, graph: dict[str, Any], owner_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate structure, project ownership and source ranges for every render entry point."""
    project = (storage.get_project_for_owner(owner_id, project_id)
               if owner_id is not None else storage.get_project(project_id))
    if not project:
        raise RenderValidationError("Project not found.")
    if not isinstance(graph, dict):
        raise RenderValidationError("Render graph must be an object.")

    normalized = validate_render_graph(graph)
    warnings: list[dict[str, str]] = []
    checked_media: dict[str, dict[str, Any]] = {}

    def check_asset(clip: dict[str, Any]) -> None:
        media_id = clip.get("media_id")
        media = checked_media.get(media_id)
        if media is None:
            media = (storage.get_media_for_owner(owner_id, media_id, project_id)
                     if owner_id is not None else storage.get_media(media_id))
            if not media or media.get("project_id") != project_id:
                raise RenderValidationError("Every export asset must belong to this project.")
            checked_media[media_id] = media
        duration = media.get("duration")
        if duration is not None:
            source_start = float(clip.get("source_start", 0))
            clip_duration = float(clip.get("duration", 0))
            if source_start + clip_duration > float(duration) + 0.08:
                raise RenderValidationError(
                    f"Clip exceeds the source duration for '{media.get('filename', media_id)}'."
                )

    for clip in graph.get("clips", []):
        check_asset(clip)
    for clip in graph.get("audio_clips", []):
        check_asset(clip)

    if not graph.get("audio_clips"):
        warnings.append({"code": "NO_AUDIO_TRACK", "message": "No separate audio clips are present. Review whether this export needs an audio track."})
    if not graph.get("captions"):
        warnings.append({"code": "NO_CAPTIONS", "message": "No captions are included in this export."})
    if normalized["video_duration"] < 1:
        warnings.append({"code": "VERY_SHORT_EXPORT", "message": "The export is shorter than one second."})
    if normalized["export_preset"] == "8k":
        warnings.append({"code": "HIGH_RESOURCE_8K", "message": "8K export is extremely resource-intensive. Confirm that the render server has sufficient CPU/GPU, memory, and storage before starting."})
    if normalized["export_preset"] == "8k" and normalized["frame_rate"] == 60:
        warnings.append({"code": "8K_60FPS_HEAVY", "message": "8K at 60 FPS is a demanding export target. Rendering may be slow or fail on hardware without adequate encoding capacity."})
    if normalized["frame_rate"] == 120:
        warnings.append({"code": "HIGH_FRAME_RATE_120", "message": "120 FPS export is demanding. For true 120 FPS motion, use source footage recorded at 120 FPS; lower-frame-rate footage will be duplicated/interpolated by the output frame-rate conversion."})

    encoder_capabilities = probe_video_encoders()
    try:
        encoder_choice = select_video_encoder(capabilities=encoder_capabilities)
    except RenderValidationError as exc:
        encoder_choice = {"encoder": None, "mode": "unavailable", "note": str(exc)}
    ffmpeg_available = bool(encoder_capabilities.get("ffmpeg_available"))
    encoder_available = bool(encoder_choice.get("encoder"))
    ready = ffmpeg_available and encoder_available
    report = {
        "ready": ready,
        "encoder": encoder_choice,
        "encoder_capabilities": encoder_capabilities,
        "project_id": project_id,
        "video_duration": normalized["video_duration"],
        "resolution": f"{normalized['width']}x{normalized['height']}",
        "frame_rate": normalized["frame_rate"],
        "export_preset": normalized["export_preset"],
        "video_bitrate": normalized["video_bitrate"],
        "video_clip_count": len(normalized["clips"]),
        "audio_clip_count": len(normalized["audio_clips"]),
        "caption_count": len(normalized["captions"]),
        "checked_media_count": len(checked_media),
        "warnings": warnings,
        "message": ("Preflight passed. Review warnings before starting the render."
                    if ready else
                    "Preflight blocked: FFmpeg is not available on this render server."
                    if not ffmpeg_available else
                    "Preflight blocked: no supported H.264 video encoder is available."),
        "encoder_warning": ("FFmpeg lists a hardware encoder, but actual device/driver support must be verified by a render."
                            if encoder_choice.get("mode") == "hardware" else None),
    }
    return normalized, report


def inspect_render(project_id: str, graph: dict[str, Any], owner_id: str | None = None) -> dict[str, Any]:
    """Check an export graph and report actionable warnings before rendering."""
    _, report = validate_project_render_graph(project_id, graph, owner_id=owner_id)
    return report
