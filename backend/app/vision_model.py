"""Optional OpenAI-compatible vision analysis for FLEXY AI scene thumbnails.

Only a single JPEG thumbnail is sent to the configured provider. If no API key is
configured, callers receive a clear unavailable result; no fake semantic labels
are generated locally.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class VisionProviderError(RuntimeError):
    pass


def vision_is_configured() -> bool:
    return bool(os.getenv("FLEXY_AI_API_KEY", "").strip())


def describe_scene(image_path: Path, *, timeout: float = 40) -> dict[str, Any]:
    key = os.getenv("FLEXY_AI_API_KEY", "").strip()
    if not key:
        return {
            "available": False,
            "provider": None,
            "description": None,
            "objects": [],
            "actions": [],
            "editing_notes": [],
            "notice": "Vision AI is not configured. Set FLEXY_AI_API_KEY on the backend to enable semantic scene analysis.",
        }
    if not image_path.is_file():
        raise VisionProviderError("Scene thumbnail was not found.")
    if image_path.stat().st_size > 8 * 1024 * 1024:
        raise VisionProviderError("Scene thumbnail exceeds the 8 MB vision request limit.")

    base = os.getenv("FLEXY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("FLEXY_VISION_MODEL", os.getenv("FLEXY_AI_MODEL", "gpt-4o-mini")).strip()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Analyze this single video-frame image for an editing application. "
                    "Return JSON with keys description (string), objects (array of short visible labels), "
                    "actions (array; only actions clearly visible), editing_notes (array of concise useful "
                    "editing observations), and confidence (number 0 to 1). Do not infer identity, "
                    "private traits, or events outside the frame. If uncertain, say so."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the visible content of this scene frame."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            },
        ],
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        description = parsed.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("Vision response did not contain a description")
        def clean_list(value: Any, limit: int, max_length: int) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item).strip()[:max_length] for item in value[:limit] if str(item).strip()]
        try:
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return {
            "available": True,
            "provider": "openai_compatible",
            "model": model,
            "description": description.strip()[:1200],
            "objects": clean_list(parsed.get("objects"), 20, 100),
            "actions": clean_list(parsed.get("actions"), 12, 120),
            "editing_notes": clean_list(parsed.get("editing_notes"), 12, 240),
            "confidence": confidence,
            "notice": "AI-generated interpretation of one frame; verify before using it as an editing decision.",
        }
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VisionProviderError(f"Vision provider request failed: {type(exc).__name__}.") from exc
