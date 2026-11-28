"""Validated FFmpeg renderer for sequential video and timeline-positioned audio clips."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from . import storage


VIDEO_ENCODER_CHOICES = ("auto", "libx264", "h264_nvenc", "h264_qsv", "h264_videotoolbox")
HARDWARE_VIDEO_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_videotoolbox")


def probe_video_encoders() -> dict[str, Any]:
    """Inspect FFmpeg's compiled H.264 encoders without assuming hardware is usable."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ffmpeg_available": False, "available": [], "hardware": [], "error": "FFmpeg is not installed."}
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=8
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        available = sorted({
            name for name in ("libx264", *HARDWARE_VIDEO_ENCODERS)
            if re.search(rf"\b{re.escape(name)}\b", output)
        })
        return {
            "ffmpeg_available": result.returncode == 0,
            "available": available,
            "hardware": [name for name in available if name in HARDWARE_VIDEO_ENCODERS],
            "error": None if result.returncode == 0 else (result.stderr or "Could not list FFmpeg encoders.")[-500:],
        }
    except Exception as exc:
        return {"ffmpeg_available": True, "available": [], "hardware": [], "error": str(exc)[:500]}


def select_video_encoder(requested: str | None = None, capabilities: dict[str, Any] | None = None) -> dict[str, str]:
    """Resolve a listed H.264 encoder, preferring portable software encoding."""
    requested = (requested or __import__("os").getenv("FLEXY_VIDEO_ENCODER", "auto")).strip().lower()
    if requested not in VIDEO_ENCODER_CHOICES:
        raise RenderValidationError(
            "FLEXY_VIDEO_ENCODER must be auto, libx264, h264_nvenc, h264_qsv or h264_videotoolbox."
        )
    capabilities = capabilities or probe_video_encoders()
    if not capabilities.get("ffmpeg_available", True):
        raise RenderValidationError("FFmpeg is not available on this render server.")
    available = capabilities.get("available", [])
    if requested == "auto":
        if "libx264" in available:
            chosen = "libx264"
        else:
            chosen = next((name for name in HARDWARE_VIDEO_ENCODERS if name in available), None)
            if chosen is None:
                raise RenderValidationError(
                    "No supported H.264 video encoder is available in this FFmpeg build."
                )
        mode = "software" if chosen == "libx264" else "hardware"
    elif requested not in available:
        raise RenderValidationError(
            f"Configured video encoder '{requested}' is not listed by this FFmpeg build. "
            f"Available: {', '.join(available) or 'none'}."
        )
    else:
        chosen = requested
        mode = "software" if chosen == "libx264" else "hardware"
    preset = {"libx264": "veryfast", "h264_nvenc": "p4", "h264_qsv": "veryfast",
              "h264_videotoolbox": "realtime"}[chosen]
    return {"encoder": chosen, "mode": mode, "preset": preset,
            "note": ("CPU encoding selected for broad compatibility." if mode == "software"
                     else "FFmpeg lists this hardware encoder; device access and driver compatibility still need a real render test.")}


MAX_CLIPS = 80
MAX_DURATION = 60 * 30
MAX_RENDER_SECONDS = 60 * 60
RENDER_POLL_INTERVAL = 0.25
ALLOWED_WIDTHS = {720, 1080, 1280, 1440, 1920, 2560, 2160, 3840, 4320, 7680}
ALLOWED_HEIGHTS = {720, 1080, 1280, 1440, 1920, 2560, 2160, 3840, 4320, 7680}
EXPORT_PRESETS = {
    "720p": (1280, 720, "5M"),
    "1080p": (1920, 1080, "12M"),
    "2k": (2560, 1440, "24M"),
    "4k": (3840, 2160, "35M"),
    "8k": (7680, 4320, "100M"),
}

class RenderValidationError(ValueError):
    pass


class RenderCancelledError(RuntimeError):
    """Raised when a render job is cancelled by its owner."""


def _validated_media_path(media_id: Any) -> tuple[dict[str, Any], Path]:
    if not isinstance(media_id, str) or not media_id:
        raise RenderValidationError("Each clip needs a media_id.")
    media = storage.get_media(media_id)
    if not media:
        raise RenderValidationError(f"Unknown media asset: {media_id}")
    path = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not path.is_file():
        raise RenderValidationError(f"Stored media is missing: {media_id}")
    return media, path

def validate_render_graph(graph: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise RenderValidationError("Render graph must be an object.")
    clips = graph.get("clips")
    audio_clips = graph.get("audio_clips", [])
    captions = graph.get("captions", [])
    if not isinstance(clips, list) or not clips or len(clips) > MAX_CLIPS:
        raise RenderValidationError(f"Provide between 1 and {MAX_CLIPS} video clips.")
    if not isinstance(audio_clips, list) or len(audio_clips) > MAX_CLIPS:
        raise RenderValidationError(f"Provide no more than {MAX_CLIPS} audio clips.")
    if not isinstance(captions, list) or len(captions) > 500:
        raise RenderValidationError("Provide no more than 500 caption items.")
    width, height, fps = graph.get("width", 1920), graph.get("height", 1080), graph.get("frame_rate", 30)
    export_preset = graph.get("export_preset", "custom")
    if export_preset not in ("custom", *EXPORT_PRESETS.keys()):
        raise RenderValidationError("Export preset must be custom, 720p, 1080p, 2k, 4k or 8k.")
    if export_preset != "custom":
        preset_width, preset_height, target_bitrate = EXPORT_PRESETS[export_preset]
        if isinstance(width, (int, float)) and isinstance(height, (int, float)) and height > width:
            width, height = preset_height, preset_width
        else:
            width, height = preset_width, preset_height
    else:
        target_bitrate = graph.get("video_bitrate", "12M")
        if target_bitrate not in ("2M", "4M", "5M", "8M", "12M", "20M", "35M", "50M", "100M"):
            raise RenderValidationError("Unsupported video bitrate. Choose a supported bitrate from 2M to 100M.")
    if width not in ALLOWED_WIDTHS or height not in ALLOWED_HEIGHTS:
        raise RenderValidationError("Unsupported output dimensions.")
    if fps not in (24, 25, 30, 50, 60, 120):
        raise RenderValidationError("Unsupported frame rate.")
    # FLEXY's supported delivery targets are 8K up to 60 FPS and 120 FPS
    # through 4K. Enforce this server-side even if a client bypasses the UI.
    if fps == 120 and max(width, height) > 3840:
        raise RenderValidationError("120 FPS export is supported up to 4K. Choose 60 FPS for 8K output.")
    if export_preset != "custom" and fps == 120:
        target_bitrate = f"{round(int(target_bitrate.rstrip('M')) * 1.5)}M"
    normalized_video = []
    total = 0.0
    legacy_cursor = 0.0
    for clip in clips:
        if not isinstance(clip, dict):
            raise RenderValidationError("Each video clip must be an object.")
        start, duration = clip.get("source_start", 0), clip.get("duration")
        if isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0:
            raise RenderValidationError("source_start must be a non-negative number.")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise RenderValidationError("duration must be a positive number.")
        media, path = _validated_media_path(clip.get("media_id"))
        is_video = media["mime_type"].startswith("video/")
        is_image = media["mime_type"].startswith("image/")
        if not (is_video or is_image):
            raise RenderValidationError("Visual track clips must reference video or image media.")
        if is_image and float(start) != 0:
            raise RenderValidationError("Still image clips must use source_start 0.")
        has_explicit_timeline_start = "timeline_start" in clip
        timeline_start = clip.get("timeline_start", legacy_cursor)
        track_index = clip.get("track_index", 0)
        if isinstance(timeline_start, bool) or not isinstance(timeline_start, (int, float)) or timeline_start < 0:
            raise RenderValidationError("Video timeline_start must be a non-negative number.")
        if isinstance(track_index, bool) or not isinstance(track_index, int) or not 0 <= track_index <= 7:
            raise RenderValidationError("Video track_index must be an integer from 0 to 7.")
        transition = clip.get("transition", "none")
        if transition not in ("none", "fade", "crossfade"):
            raise RenderValidationError("Video transition must be none, fade or crossfade.")
        opacity = clip.get("opacity", 1.0)
        scale = clip.get("scale", 1.0)
        position_x = clip.get("position_x", 0)
        position_y = clip.get("position_y", 0)
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0 <= opacity <= 1:
            raise RenderValidationError("Video opacity must be between 0 and 1.")
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.1 <= scale <= 3:
            raise RenderValidationError("Video scale must be between 0.1 and 3.")
        for value, label in ((position_x, "position_x"), (position_y, "position_y")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) > 7680:
                raise RenderValidationError(f"Video {label} must be between -7680 and 7680.")
        clip_end = float(timeline_start) + float(duration)
        if not has_explicit_timeline_start:
            legacy_cursor = max(legacy_cursor, clip_end)
        total = max(total, clip_end)
        if total > MAX_DURATION:
            raise RenderValidationError("Video duration exceeds the 30-minute development limit.")
        normalized_video.append({"path": str(path), "source_start": float(start), "duration": float(duration),
                                 "timeline_start": float(timeline_start), "track_index": track_index,
                                 "transition": transition, "is_image": is_image,
                                 "opacity": float(opacity), "scale": float(scale),
                                 "position_x": float(position_x), "position_y": float(position_y)})

    normalized_audio = []
    for clip in audio_clips:
        if not isinstance(clip, dict):
            raise RenderValidationError("Each audio clip must be an object.")
        source_start = clip.get("source_start", 0)
        duration = clip.get("duration")
        timeline_start = clip.get("timeline_start", 0)
        volume = clip.get("volume", 1.0)
        fade_in = clip.get("fade_in", 0.0)
        fade_out = clip.get("fade_out", 0.0)
        role = clip.get("role", "other")
        bus = clip.get("bus", "effects" if role == "other" else role)
        if bus not in ("dialogue", "music", "effects"): raise RenderValidationError("Audio bus must be dialogue, music or effects.")
        if role not in ("dialogue", "music", "other"):
            raise RenderValidationError("Audio role must be dialogue, music or other.")
        for value, label in ((source_start, "source_start"), (timeline_start, "timeline_start")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise RenderValidationError(f"{label} must be a non-negative number.")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise RenderValidationError("Audio duration must be a positive number.")
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0 <= volume <= 2:
            raise RenderValidationError("Audio volume must be between 0 and 2.")
        for value, label in ((fade_in, "fade_in"), (fade_out, "fade_out")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise RenderValidationError(f"Audio {label} must be a non-negative number.")
            if value > float(duration):
                raise RenderValidationError(f"Audio {label} cannot exceed clip duration.")
        if float(fade_in) + float(fade_out) > float(duration):
            raise RenderValidationError("Audio fade-in and fade-out cannot overlap beyond clip duration.")
        raw_keyframes = clip.get("volume_keyframes", [])
        if not isinstance(raw_keyframes, list) or len(raw_keyframes) > 100:
            raise RenderValidationError("Audio volume_keyframes must be a list of no more than 100 items.")
        normalized_keyframes = []
        previous_time = -1.0
        for keyframe in raw_keyframes:
            if not isinstance(keyframe, dict):
                raise RenderValidationError("Each audio volume keyframe must be an object.")
            key_time = keyframe.get("time")
            key_volume = keyframe.get("volume")
            if isinstance(key_time, bool) or not isinstance(key_time, (int, float)) or not 0 <= key_time <= float(duration):
                raise RenderValidationError("Audio keyframe time must be within the clip duration.")
            if isinstance(key_volume, bool) or not isinstance(key_volume, (int, float)) or not 0 <= key_volume <= 2:
                raise RenderValidationError("Audio keyframe volume must be between 0 and 2.")
            if float(key_time) <= previous_time:
                raise RenderValidationError("Audio keyframe times must be strictly increasing.")
            previous_time = float(key_time)
            normalized_keyframes.append({"time": float(key_time), "volume": float(key_volume)})
        media, path = _validated_media_path(clip.get("media_id"))
        if not media["mime_type"].startswith("audio/"):
            raise RenderValidationError("Audio track clips must reference audio media.")
        if float(timeline_start) + float(duration) > MAX_DURATION:
            raise RenderValidationError("Audio timeline exceeds the 30-minute development limit.")
        normalized_audio.append({
            "path": str(path), "source_start": float(source_start),
            "duration": float(duration), "timeline_start": float(timeline_start),
            "volume": float(volume), "fade_in": float(fade_in), "fade_out": float(fade_out),
            "volume_keyframes": normalized_keyframes, "role": role, "bus": bus,
        })
    normalized_captions = []
    for caption in captions:
        if not isinstance(caption, dict):
            raise RenderValidationError("Each caption must be an object.")
        text = caption.get("text")
        start, duration = caption.get("start", 0), caption.get("duration")
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise RenderValidationError("Caption text must contain 1 to 1000 characters.")
        for value, label in ((start, "caption start"), (duration, "caption duration")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise RenderValidationError(f"{label} must be a non-negative number.")
        if duration <= 0 or float(start) + float(duration) > MAX_DURATION:
            raise RenderValidationError("Caption duration is invalid or exceeds the project limit.")
        style = caption.get("style") or {}
        if not isinstance(style, dict):
            raise RenderValidationError("Caption style must be an object.")
        alignment = style.get("alignment", "center")
        position = style.get("position", "bottom")
        if alignment not in ("left", "center", "right") or position not in ("top", "bottom"):
            raise RenderValidationError("Caption alignment or position is invalid.")
        def bounded_number(key, default, minimum, maximum):
            value = style.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
                raise RenderValidationError(f"Caption {key} must be between {minimum} and {maximum}.")
            return float(value)
        def valid_color(key, default):
            value = style.get(key, default)
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value):
                raise RenderValidationError(f"Caption {key} must be a hex color.")
            return value.lower()
        normalized_style = {
            "alignment": alignment, "position": position,
            "font_size": bounded_number("fontSize", 28, 12, 72),
            "vertical_offset": bounded_number("verticalOffset", 7, 0, 100),
            "outline_width": bounded_number("outlineWidth", 0, 0, 8),
            "shadow_blur": bounded_number("shadowBlur", 0, 0, 32),
            "color": valid_color("color", "#ffffff"),
            "background_color": valid_color("backgroundColor", "#000000b8"),
            "outline_color": valid_color("outlineColor", "#000000"),
            "shadow_color": valid_color("shadowColor", "#000000"),
            "bold": style.get("bold", True) is not False,
            "animation": style.get("animation", "none"),
            "animation_duration": bounded_number("animationDuration", 0.45, 0.1, 2),
        }
        if normalized_style["animation"] not in ("none", "word", "karaoke", "pop", "fade", "slide"):
            raise RenderValidationError("Caption animation is invalid.")
        raw_word_timings = caption.get("word_timings", [])
        if not isinstance(raw_word_timings, list) or len(raw_word_timings) > 12:
            raise RenderValidationError("Caption word timings must contain no more than 12 entries.")
        normalized_word_timings = []
        previous_word_end = float(start)
        for word_timing in raw_word_timings:
            if not isinstance(word_timing, dict):
                raise RenderValidationError("Each caption word timing must be an object.")
            word = word_timing.get("word")
            word_start, word_end = word_timing.get("start"), word_timing.get("end")
            if not isinstance(word, str) or not word.strip() or len(word) > 100:
                raise RenderValidationError("Caption word text must contain 1 to 100 characters.")
            if (isinstance(word_start, bool) or not isinstance(word_start, (int, float))
                    or isinstance(word_end, bool) or not isinstance(word_end, (int, float))
                    or not float(start) <= float(word_start) < float(word_end) <= float(start) + float(duration)
                    or float(word_start) < previous_word_end - 0.02):
                raise RenderValidationError("Caption word timings must be ordered and inside the caption time range.")
            normalized_word_timings.append({"word": word.strip(), "start": float(word_start), "end": float(word_end)})
            previous_word_end = float(word_end)
        normalized_captions.append({
            "text": text.strip(), "start": float(start), "duration": float(duration),
            "style": normalized_style, "word_timings": normalized_word_timings,
        })
    ducking_settings = graph.get("ducking_settings", {})
    if not isinstance(ducking_settings, dict):
        raise RenderValidationError("ducking_settings must be an object.")
    def ducking_number(key: str, default: float, minimum: float, maximum: float) -> float:
        value = ducking_settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
            raise RenderValidationError(f"Ducking {key} must be between {minimum:g} and {maximum:g}.")
        return float(value)
    normalized_ducking = {
        "threshold_db": ducking_number("threshold_db", -24, -40, -6),
        "ratio": ducking_number("ratio", 8, 1, 20),
        "attack_ms": ducking_number("attack_ms", 20, 1, 200),
        "release_ms": ducking_number("release_ms", 450, 50, 2000),
    }
    raw_mixer = graph.get("audio_mixer", {})
    if not isinstance(raw_mixer, dict):
        raise RenderValidationError("audio_mixer must be an object.")
    normalized_mixer = {}
    for bus_name in ("dialogue", "music", "effects", "master"):
        raw_bus = raw_mixer.get(bus_name, {})
        if not isinstance(raw_bus, dict):
            raise RenderValidationError(f"Audio mixer {bus_name} bus must be an object.")
        gain = raw_bus.get("gain", 1.0)
        muted = raw_bus.get("muted", False)
        if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not 0 <= gain <= 2:
            raise RenderValidationError(f"Audio mixer {bus_name} gain must be between 0 and 2.")
        if not isinstance(muted, bool):
            raise RenderValidationError(f"Audio mixer {bus_name} muted must be boolean.")
        normalized_mixer[bus_name] = {"gain": float(gain), "muted": muted}
    return {
        "clips": normalized_video, "audio_clips": normalized_audio, "captions": normalized_captions,
        "width": width, "height": height, "frame_rate": fps,
        "export_preset": export_preset, "video_bitrate": target_bitrate,
        "audio_mixer": normalized_mixer,
        "ducking": bool(graph.get("ducking", False)),
        "ducking_settings": normalized_ducking,
        "video_duration": total,
    }

def _srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _ass_color(value: str) -> str:
    """Convert #RRGGBB or #RRGGBBAA into ASS &HAABBGGRR notation."""
    raw = value.lstrip("#")
    red, green, blue = raw[:2], raw[2:4], raw[4:6]
    alpha = raw[6:8] if len(raw) == 8 else "ff"
    opacity = 255 - int(alpha, 16)
    return f"&H{opacity:02X}{blue}{green}{red}&"


def _ass_escape_text(value: str) -> str:
    # Escape user-provided override delimiters and preserve intentional line breaks.
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\r\\n", "\\N").replace("\n", "\\N").replace("\r", "\\N")


def _ass_animation_tags(animation: str, duration: float, width: int, height: int, x: int, y: int) -> str:
    """Return ASS override tags for supported caption entrance/reveal effects."""
    cs = max(1, min(200, round(duration * 100)))
    if animation == "fade":
        return f"\\fad({cs},0)"
    if animation == "pop":
        return f"\\fscx70\\fscy70\\t(0,{cs},\\fscx100\\fscy100)"
    if animation == "slide":
        start_y = max(0, y - round(height * 0.06))
        return f"\\move({x},{start_y},{x},{y},0,{cs})"
    return ""


def _caption_word_events(item: dict[str, Any], name: str, alignment: int, x: int, y: int) -> list[str]:
    """Build timed ASS events for word reveal and karaoke caption modes."""
    style = item.get("style") or {}
    animation = style.get("animation", "none")
    words = str(item["text"]).split()
    if animation not in ("word", "karaoke") or not words:
        return []
    start = float(item["start"])
    duration = float(item["duration"])
    reveal_duration = min(duration, float(style.get("animation_duration", 0.45)))
    step = (reveal_duration if animation == "word" else duration) / len(words)
    base = f"{{\\an{alignment}\\pos({x},{y})}}"
    if animation == "word":
        events = []
        for count in range(1, len(words) + 1):
            event_start = start + (count - 1) * step
            line = " ".join(words[:count])
            events.append(f"Dialogue: 0,{_ass_timestamp(event_start)},{_ass_timestamp(start + duration)},{name},,0,0,0,,{base}{_ass_escape_text(line)}")
        return events
    timed_words = item.get("word_timings") or []
    if timed_words and len(timed_words) == len(words):
        karaoke_parts = []
        for index, timed_word in enumerate(timed_words):
            next_start = float(timed_words[index + 1]["start"]) if index + 1 < len(timed_words) else float(timed_word["end"])
            word_duration = max(0.01, next_start - float(timed_word["start"]))
            word_text = str(timed_word.get("word", ""))
            karaoke_parts.append(f"{{\\kf{max(1, round(word_duration * 100))}}}{_ass_escape_text(word_text)} ")
        karaoke = "".join(karaoke_parts).rstrip()
        event_start = max(start, float(timed_words[0]["start"]))
        event_end = min(start + duration, float(timed_words[-1]["end"]))
        return [f"Dialogue: 0,{_ass_timestamp(event_start)},{_ass_timestamp(event_end)},{name},,0,0,0,,{base}{karaoke}"]
    karaoke = "".join(f"{{\\kf{max(1, round(step * 100))}}}{_ass_escape_text(word)} " for word in words).rstrip()
    return [f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(start + duration)},{name},,0,0,0,,{base}{karaoke}"]


def _captions_to_ass(captions: list[dict[str, Any]], width: int, height: int) -> str:
    header = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H77000000,1,0,0,0,100,100,0,0,1,2,1,2,40,40,40,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    for index, item in enumerate(sorted(captions, key=lambda row: row["start"])):
        style = item.get("style") or {}
        alignment = {"left": 1, "center": 2, "right": 3}[style.get("alignment", "center")]
        top = style.get("position", "bottom") == "top"
        ass_alignment = alignment + (6 if top else 0)
        offset = float(style.get("vertical_offset", 7))
        y = round(height * offset / 100) if top else round(height * (1 - offset / 100))
        x = {"left": round(width * 0.05), "center": round(width * 0.5), "right": round(width * 0.95)}[style.get("alignment", "center")]
        color = _ass_color(style.get("color", "#ffffff"))
        outline = _ass_color(style.get("outline_color", "#000000"))
        shadow = _ass_color(style.get("shadow_color", "#000000"))
        background = _ass_color(style.get("background_color", "#000000b8"))
        bold = -1 if style.get("bold", True) else 0
        font_size = round(float(style.get("font_size", 28)))
        outline_width = float(style.get("outline_width", 0))
        shadow_blur = float(style.get("shadow_blur", 0))
        name = f"Caption{index}"
        secondary = _ass_color("#ffe66d") if style.get("animation") == "karaoke" else color
        style_line = (
            f"Style: {name},Arial,{font_size},{color},{secondary},{outline},{background},"
            f"{bold},0,0,0,100,100,0,0,3,{outline_width:g},{shadow_blur:g},"
            f"{ass_alignment},30,30,30,1"
        )
        header.insert(-4, style_line)
        start = _ass_timestamp(float(item["start"]))
        end = _ass_timestamp(float(item["start"]) + float(item["duration"]))
        animation = style.get("animation", "none")
        word_events = _caption_word_events(item, name, ass_alignment, x, y)
        if word_events:
            events.extend(word_events)
        else:
            text = _ass_escape_text(str(item["text"]))
            animation_tags = _ass_animation_tags(animation, float(style.get("animation_duration", 0.45)), width, height, x, y)
            events.append(f"Dialogue: 0,{start},{end},{name},,0,0,0,,{{\\an{ass_alignment}\\pos({x},{y}){animation_tags}}}{text}")
    return "\n".join(header + events) + "\n"


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _volume_keyframe_expression(keyframes: list[dict[str, float]], base_volume: float) -> str | None:
    """Build a frame-evaluated, piecewise-linear FFmpeg volume expression."""
    if not keyframes:
        return None
    points = [{"time": 0.0, "volume": float(base_volume)}]
    for point in keyframes:
        if point["time"] == 0:
            points[0] = point
        else:
            points.append(point)
    if len(points) == 1:
        return f"{points[0]['volume']:.6f}"
    expression = f"{points[-1]['volume']:.6f}"
    for left, right in reversed(list(zip(points, points[1:]))):
        span = right["time"] - left["time"]
        slope = (right["volume"] - left["volume"]) / span
        linear = f"({left['volume']:.6f}+({slope:.9f})*(t-{left['time']:.6f}))"
        expression = f"if(lt(t\\,{right['time']:.6f})\\,{linear}\\,{expression})"
    return expression


def render_mp4(graph: dict[str, Any], output_path: Path, progress_callback=None, cancel_check=None) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is not installed on the server. Install FFmpeg to enable MP4 rendering.")
    video_clips = graph["clips"]
    audio_clips = graph.get("audio_clips", [])
    captions = graph.get("captions", [])
    filters: list[str] = []
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    duration = float(graph["video_duration"])
    width, height, fps = graph["width"], graph["height"], graph["frame_rate"]
    command += ["-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}"]
    # Name the generated background stream before it is used by the overlay chain.
    filters.append("[0:v]setpts=PTS-STARTPTS[base]")
    ordered_video = sorted(enumerate(video_clips), key=lambda pair: (-pair[1]["track_index"], pair[1]["timeline_start"], pair[0]))
    overlay_label = "base"
    for visual_index, (original_index, clip) in enumerate(ordered_video):
        input_index = visual_index + 1
        if clip.get("is_image"):
            command += ["-loop", "1", "-t", str(clip["duration"]), "-i", clip["path"]]
        else:
            command += ["-ss", str(clip["source_start"]), "-t", str(clip["duration"]), "-i", clip["path"]]
        start = clip["timeline_start"]
        clip_duration = clip["duration"]
        end = start + clip_duration
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=rgba"
        )
        if clip["transition"] in ("fade", "crossfade"):
            fade_duration = min(0.45, max(0.08, clip_duration / 3))
            fade_out_start = max(0.0, clip_duration - fade_duration)
            video_filter += f",fade=t=in:st=0:d={fade_duration}:alpha=1,fade=t=out:st={fade_out_start}:d={fade_duration}:alpha=1"
        video_filter += (
            f",scale=iw*{clip['scale']}:ih*{clip['scale']},"
            f"colorchannelmixer=aa={clip['opacity']}"
        )
        video_filter += f",setpts=PTS-STARTPTS+{start}/TB"
        clip_label = f"visual{visual_index}"
        filters.append(f"[{input_index}:v:0]{video_filter}[{clip_label}]")
        next_label = f"composite{visual_index}"
        filters.append(
            f"[{overlay_label}][{clip_label}]overlay=x='(W-w)/2+{clip[\'position_x\']}':y='(H-h)/2+{clip[\'position_y\']}':eof_action=pass:shortest=0:"
            f"enable='between(t,{start},{end})'[{next_label}]"
        )
        overlay_label = next_label
    filters.append(f"[{overlay_label}]trim=duration={duration},setpts=PTS-STARTPTS[outv]")

    for offset, clip in enumerate(audio_clips):
        input_index = len(video_clips) + 1 + offset
        command += ["-ss", str(clip["source_start"]), "-t", str(clip["duration"]), "-i", clip["path"]]
        delay_ms = round(clip["timeline_start"] * 1000)
        label = f"a{offset}"
        mixer = graph.get("audio_mixer", {})
        bus_name = clip.get("bus", "effects" if clip.get("role") == "other" else clip.get("role", "effects"))
        bus_settings = mixer.get(bus_name, {"gain": 1.0, "muted": False})
        bus_gain = 0.0 if bus_settings.get("muted", False) else float(bus_settings.get("gain", 1.0))
        keyframe_expression = _volume_keyframe_expression(clip.get("volume_keyframes", []), clip["volume"])
        volume_filter = (f"volume='{keyframe_expression}':eval=frame,volume={bus_gain}" if keyframe_expression is not None
                         else f"volume={clip['volume'] * bus_gain}")
        audio_chain = (
            f"[{input_index}:a:0]atrim=duration={clip['duration']},asetpts=PTS-STARTPTS,"
            f"{volume_filter}"
        )
        if clip.get("fade_in", 0) > 0:
            audio_chain += f",afade=t=in:st=0:d={clip['fade_in']}"
        if clip.get("fade_out", 0) > 0:
            fade_start = max(0.0, clip["duration"] - clip["fade_out"])
            audio_chain += f",afade=t=out:st={fade_start}:d={clip['fade_out']}"
        audio_chain += f",adelay={delay_ms}|{delay_ms}[{label}]"
        filters.append(audio_chain)

    if audio_clips:
        dialogue = [i for i, clip in enumerate(audio_clips) if clip.get("bus", "effects" if clip.get("role") == "other" else clip.get("role", "effects")) == "dialogue"]
        music = [i for i, clip in enumerate(audio_clips) if clip.get("bus", "effects" if clip.get("role") == "other" else clip.get("role", "effects")) == "music"]
        other = [i for i, clip in enumerate(audio_clips) if clip.get("bus", "effects" if clip.get("role") == "other" else clip.get("role", "effects")) == "effects"]
        mixed_labels: list[str] = []
        if graph.get("ducking") and dialogue and music:
            dialogue_inputs = "".join(f"[a{i}]" for i in dialogue)
            filters.append(dialogue_inputs + f"amix=inputs={len(dialogue)}:duration=longest:dropout_transition=0,asplit=2[dialoguekey][dialogueout]")
            music_inputs = "".join(f"[a{i}]" for i in music)
            filters.append(music_inputs + f"amix=inputs={len(music)}:duration=longest:dropout_transition=0[musicbus]")
            duck = graph.get("ducking_settings", {})
            threshold = 10 ** (float(duck.get("threshold_db", -24)) / 20)
            ratio = float(duck.get("ratio", 8))
            attack = float(duck.get("attack_ms", 20))
            release = float(duck.get("release_ms", 450))
            filters.append(
                f"[musicbus][dialoguekey]sidechaincompress=threshold={threshold:.6f}:ratio={ratio:g}:"
                f"attack={attack:g}:release={release:g}:makeup=1[duckedmusic]"
            )
            mixed_labels.extend(["[dialogueout]", "[duckedmusic]"])
        else:
            mixed_labels.extend(f"[a{i}]" for i in dialogue + music)
        mixed_labels.extend(f"[a{i}]" for i in other)
        if len(mixed_labels) == 1:
            filters.append(mixed_labels[0] + f"atrim=duration={duration},asetpts=PTS-STARTPTS[outa]")
        else:
            labels = "".join(mixed_labels)
            filters.append(labels + f"amix=inputs={len(mixed_labels)}:duration=longest:dropout_transition=0,"
                          f"atrim=duration={duration},asetpts=PTS-STARTPTS[outa]")

    if audio_clips:
        master = graph.get("audio_mixer", {}).get("master", {"gain": 1.0, "muted": False})
        master_gain = 0.0 if master.get("muted", False) else float(master.get("gain", 1.0))
        filters.append(f"[outa]volume={master_gain}[masterout]")
    caption_file = None
    video_output_label = "outv"
    if graph.get("captions"):
        caption_file = output_path.with_suffix(".captions.ass")
        caption_file.write_text(_captions_to_ass(graph["captions"], width, height), encoding="utf-8")
        escaped = str(caption_file.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"[outv]subtitles=filename='{escaped}'[captioned]")
        video_output_label = "captioned"

    command += ["-filter_complex", ";".join(filters), "-map", f"[{video_output_label}]"]
    if audio_clips:
        command += ["-map", "[masterout]", "-c:a", "aac", "-b:a", "192k"]
    else:
        command += ["-an"]
    encoder = select_video_encoder()
    command += [
        "-c:v", encoder["encoder"], "-preset", encoder["preset"], "-b:v", graph["video_bitrate"],
        "-maxrate", graph["video_bitrate"], "-bufsize", graph["video_bitrate"], "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-stats_period", "1", "-progress", "pipe:1", "-nostats", str(output_path),
    ]
    try:
        # Read progress on a daemon thread so the render controller can keep
        # checking cancellation and the deadline even when FFmpeg emits no output.
        import queue
        import threading

        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log,
                                       text=True, bufsize=1)
            started = time.monotonic()
            lines: queue.Queue[str | None] = queue.Queue()

            def read_progress() -> None:
                try:
                    assert process.stdout is not None
                    for output_line in process.stdout:
                        lines.put(output_line)
                finally:
                    lines.put(None)

            reader = threading.Thread(target=read_progress, name="flexy-ffmpeg-progress", daemon=True)
            reader.start()
            try:
                finished_reading = False
                while not finished_reading:
                    if cancel_check and cancel_check():
                        raise RenderCancelledError("Render cancelled by user.")
                    if time.monotonic() - started > MAX_RENDER_SECONDS:
                        raise RuntimeError("FFmpeg render exceeded the 60-minute time limit.")
                    try:
                        line = lines.get(timeout=RENDER_POLL_INTERVAL)
                    except queue.Empty:
                        if process.poll() is not None:
                            # The reader will enqueue its EOF sentinel shortly.
                            continue
                        continue
                    if line is None:
                        finished_reading = True
                        continue
                    key, separator, value = line.strip().partition("=")
                    if separator and key == "out_time_ms":
                        try:
                            elapsed = int(value) / 1_000_000
                            percent = max(0, min(99, round(elapsed / duration * 100)))
                            if progress_callback:
                                progress_callback(percent)
                        except (ValueError, ZeroDivisionError):
                            pass
                return_code = process.wait(timeout=30)
            except Exception:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
            finally:
                if process.stdout is not None:
                    process.stdout.close()
            error_log.seek(0)
            stderr_text = error_log.read()
        if return_code != 0:
            raise RuntimeError((stderr_text or "FFmpeg render failed.")[-3000:])
    finally:
        if caption_file:
            caption_file.unlink(missing_ok=True)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg finished without producing an output file.")
    if progress_callback:
        progress_callback(100)
