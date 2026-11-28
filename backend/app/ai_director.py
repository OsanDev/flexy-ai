"""FLEXY AI Director with optional OpenAI-compatible model integration."""
from __future__ import annotations
import json, os, urllib.error, urllib.request
from typing import Any

PRESETS = {
    "portrait": {"id": "portrait", "label": "Vertical · Reels / Shorts", "width": 1080, "height": 1920},
    "landscape": {"id": "landscape", "label": "Landscape · YouTube", "width": 1920, "height": 1080},
    "square": {"id": "square", "label": "Square · Feed", "width": 1080, "height": 1080},
}


def _local_plan(instruction: str, assets: list[dict[str, Any]], project: dict[str, Any], transcript: str) -> dict[str, Any]:
    text = instruction.casefold()
    if any(w in text for w in ("reel", "reels", "short", "shorts", "tiktok", "vertical", "portrait")): preset = PRESETS["portrait"]
    elif any(w in text for w in ("square", "instagram post", "feed post")): preset = PRESETS["square"]
    elif any(w in text for w in ("youtube", "landscape", "widescreen", "16:9")): preset = PRESETS["landscape"]
    else:
        width, height = int(project.get("width", 1920) or 1920), int(project.get("height", 1080) or 1080)
        preset = PRESETS["portrait" if height > width else "square" if height == width else "landscape"]
    videos = [a for a in assets if a.get("type") == "video"]
    audios = [a for a in assets if a.get("type") == "audio"]
    images = [a for a in assets if a.get("type") == "image"]
    suggestions = []
    if not videos and not images:
        suggestions.append({"kind":"import_media","title":"Import footage","detail":"Add at least one video or image before building the visual sequence."})
    elif videos:
        suggestions.append({"kind":"sequence","title":"Build a visual sequence","detail":f"Arrange {len(videos)} video asset(s) in an opening-to-ending sequence."})
        long_count = sum(float(a.get("duration") or 0) > 30 for a in videos)
        if long_count: suggestions.append({"kind":"review_cuts","title":"Review long footage","detail":f"{long_count} video asset(s) exceed 30 seconds. Review them for tighter selects; no scene recognition has run."})
    else: suggestions.append({"kind":"image_sequence","title":"Create an image sequence","detail":f"Use {len(images)} image(s) as visual beats and adjust their timing."})
    if transcript.strip(): suggestions.append({"kind":"transcript","title":"Use the supplied transcript","detail":f"Transcript supplied ({len(transcript.split())} words). Review phrases and align captions to speech."})
    if "caption" in text or "subtitle" in text: suggestions.append({"kind":"captions","title":"Add synchronized captions","detail":"Generate or import a transcript, then review caption timing and wording."})
    if audios or any(w in text for w in ("music","song","audio","soundtrack")): suggestions.append({"kind":"audio","title":"Shape the soundtrack","detail":f"{len(audios)} audio asset(s) available. Place music under dialogue and adjust volume."})
    if any(w in text for w in ("fast","dynamic","energetic","highlight","montage")): suggestions.append({"kind":"pacing","title":"Use energetic pacing","detail":"Try shorter selects and varied shot lengths. Cut points need human review."})
    if not suggestions: suggestions.append({"kind":"review","title":"Review the edit direction","detail":"Start with the suggested canvas, then refine shot order, pacing and sound."})
    return {"provider":"local_rules","plan_version":"0.9.0","project_id":project.get("id"),"instruction":instruction,
            "summary":f"A {preset['label'].lower()} edit plan for {len(assets)} imported asset(s).","aspect_ratio":preset,
            "asset_summary":{"video":len(videos),"audio":len(audios),"image":len(images)},"suggestions":suggestions,
            "warnings":["Local planning mode is active. Configure an AI provider for model-generated suggestions.","Automatic speech recognition is not enabled; transcript text must be supplied."],
            "timeline_draft":_build_timeline_draft(instruction, assets, project)}


def _needs_advanced_model(instruction: str, assets: list[dict[str, Any]]) -> bool:
    """Route only genuinely involved editing requests to the stronger model."""
    text = instruction.casefold()
    advanced_terms = (
        "multi-clip", "multiple clips", "storyboard", "scene analysis", "analyze scenes",
        "motion track", "motion tracking", "composit", "green screen", "chroma key",
        "visual effects", "vfx", "match cut", "beat sync", "sequence", "narrative",
        "color grade", "camera movement", "detailed edit", "complex edit",
    )
    return len(assets) >= 8 or any(term in text for term in advanced_terms)


def _model_plan(instruction: str, assets: list[dict[str, Any]], project: dict[str, Any], transcript: str) -> dict[str, Any] | None:
    advanced = _needs_advanced_model(instruction, assets)
    if advanced:
        key = os.getenv("FLEXY_AI_ADVANCED_API_KEY", "").strip()
        base = os.getenv("FLEXY_AI_ADVANCED_BASE_URL", "https://api.z.ai/api/paas/v4").rstrip("/")
        model = os.getenv("FLEXY_AI_ADVANCED_MODEL", "glm-5.3-flash")
        tier = "advanced"
    else:
        key = os.getenv("FLEXY_AI_API_KEY", "").strip()
        base = os.getenv("FLEXY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("FLEXY_AI_MODEL", "gpt-4o-mini")
        tier = "fast"
    # If the advanced provider is not configured, keep the fast provider available.
    if not key and advanced:
        key = os.getenv("FLEXY_AI_API_KEY", "").strip()
        base = os.getenv("FLEXY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("FLEXY_AI_MODEL", "gpt-4o-mini")
        tier = "fast_fallback"
    if not key: return None
    payload = {"model":model,"temperature":0.3,"response_format":{"type":"json_object"},"messages":[
        {"role":"system","content":"You are FLEXY AI Director. Return JSON keys summary, aspect_ratio_id, suggestions, warnings. aspect_ratio_id must be portrait, landscape, or square. suggestions is an array of {kind,title,detail}. Never claim to inspect frames or hear audio. Use only supplied metadata/transcript. Suggestions must be editable and non-destructive."},
        {"role":"user","content":json.dumps({"instruction":instruction[:4000],"project":project,"assets":assets[:100],"transcript":transcript[:12000],"presets":PRESETS},ensure_ascii=False)}]}
    # GLM-5.3-Flash supports low reasoning effort, avoiding its default maximum effort.
    if model.startswith("glm-5.3"):
        payload["reasoning_effort"] = "low"
    req = urllib.request.Request(base+"/chat/completions",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=35) as response: raw=json.loads(response.read().decode())
        parsed=json.loads(raw["choices"][0]["message"]["content"])
        preset=PRESETS.get(parsed.get("aspect_ratio_id"),PRESETS["landscape"])
        items=parsed.get("suggestions",[])
        if not isinstance(items,list): raise ValueError("Invalid suggestions list")
        safe=[]
        for item in items[:12]:
            if isinstance(item,dict): safe.append({"kind":str(item.get("kind","review"))[:40],"title":str(item.get("title","Review suggestion"))[:120],"detail":str(item.get("detail","Review before applying."))[:600]})
        if not safe: raise ValueError("No usable suggestions")
        warnings=parsed.get("warnings",[])
        return {"provider":"openai_compatible","model":model,"model_tier":tier,"plan_version":"0.9.0","project_id":project.get("id"),"instruction":instruction,
                "summary":str(parsed.get("summary","AI-generated edit plan"))[:500],"aspect_ratio":preset,
                "asset_summary":{k:sum(a.get("type")==k for a in assets) for k in ("video","audio","image")},"suggestions":safe,
                "warnings":[str(w)[:300] for w in warnings[:8]] if isinstance(warnings,list) else [],
                "timeline_draft":_build_timeline_draft(instruction, assets, project)}
    except (urllib.error.URLError,TimeoutError,KeyError,IndexError,TypeError,ValueError,json.JSONDecodeError) as exc:
        result=_local_plan(instruction,assets,project,transcript)
        result["warnings"].insert(0,f"AI provider request failed; local fallback used ({type(exc).__name__}).")
        return result


def build_edit_plan(instruction: str, assets: list[dict[str, Any]], project: dict[str, Any] | None = None, transcript: str = "") -> dict[str, Any]:
    project_data=project or {}
    return _model_plan(instruction,assets,project_data,transcript) or _local_plan(instruction,assets,project_data,transcript)


def _build_timeline_draft(instruction: str, assets: list[dict[str, Any]], project: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic, editable starter sequence from supplied asset metadata."""
    import re
    text = instruction.casefold()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*)?(?:second|seconds|sec|s)\b", text)
    target = float(match.group(1)) if match else None
    visual = [a for a in assets if a.get("type") in {"video", "image"} and a.get("id")]
    audio = [a for a in assets if a.get("type") == "audio" and a.get("id")]
    if not visual:
        return {"duration": 0, "clips": [], "audio_clips": [], "warnings": ["Import at least one video or image to create a timeline draft."]}
    if target is None:
        known = [max(0.1, float(a.get("duration") or 5.0)) for a in visual]
        target = min(60.0, sum(known))
    target = max(1.0, min(target, 600.0))
    dynamic = any(word in text for word in ("dynamic", "fast", "energetic", "montage", "highlight"))
    clips = []
    cursor = 0.0
    for index, asset in enumerate(visual):
        if cursor >= target: break
        source_duration = max(0.1, float(asset.get("duration") or 5.0))
        desired = min(source_duration, 2.5 if dynamic else source_duration)
        clip_duration = min(desired, target - cursor)
        if clip_duration <= 0: break
        clips.append({"assetId": str(asset["id"]), "start": round(cursor, 3), "sourceStart": 0.0,
                      "duration": round(clip_duration, 3), "transition": "fade" if index else "none"})
        cursor += clip_duration
    audio_clips = []
    if audio:
        audio_asset = audio[0]
        audio_duration = max(0.1, float(audio_asset.get("duration") or target))
        audio_clips.append({"assetId": str(audio_asset["id"]), "start": 0.0, "sourceStart": 0.0,
                            "duration": round(min(target, audio_duration), 3), "volume": 0.35})
    warnings = []
    if cursor < target:
        warnings.append(f"The available visual footage covers {cursor:.1f}s of the requested {target:.1f}s. Add more footage or shorten the target.")
    if not audio:
        warnings.append("No separate audio asset was supplied. Existing source audio is not altered by this draft.")
    return {"duration": round(cursor, 3), "target_duration": round(target, 3), "clips": clips,
            "audio_clips": audio_clips, "warnings": warnings,
            "notice": "Starter sequence generated from asset metadata only. Review every cut before rendering."}
