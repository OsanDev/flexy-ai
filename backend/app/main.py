from __future__ import annotations

import uuid
import shutil
import os
import mimetypes
import subprocess
from threading import Lock
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import storage
from .auth_api import router as auth_router, current_user, _csrf_check
from .ai_director import build_edit_plan
from .rendering import RenderCancelledError, RenderValidationError, render_mp4, validate_render_graph
from .media_probe import MediaProbeError, probe_media
from .media_previews import MediaPreviewError, audio_waveform
from .scene_detection import SceneDetectionError, detect_scenes, extract_scene_thumbnail
from .visual_analysis import describe_frame, representative_scene_timestamp
from .vision_model import VisionProviderError, describe_scene
from .speech import SpeechProviderError, transcribe_media, subtitles, detect_silence, build_dialogue_edit_plan
from .recommendations import build_recommendations
from .smart_timeline import build_smart_timeline
from .audio_quality import AudioAnalysisError, analyze_loudness, analyze_beats
from .render_preflight import inspect_render, validate_project_render_graph

APP_VERSION = "4.6.0"


def configured_cors_origins(raw: str | None = None) -> list[str]:
    """Return explicitly configured browser origins, with safe local defaults."""
    value = os.getenv("FLEXY_CORS_ORIGINS", "") if raw is None else raw
    origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage.init_db()
    interrupted = storage.recover_interrupted_jobs()
    # Never expose partial MP4s from jobs that did not survive a restart.
    for job in interrupted:
        storage.safe_storage_path(storage.RENDER_DIR, f"{job['id']}.mp4").unlink(missing_ok=True)
        storage.safe_storage_path(storage.RENDER_DIR, f"{job['id']}.captions.srt").unlink(missing_ok=True)
    yield


app = FastAPI(title="FLEXY AI API", version="4.6.0", lifespan=lifespan)
_proxy_locks: dict[str, Lock] = {}
_proxy_locks_guard = Lock()

def _proxy_lock(media_id: str) -> Lock:
    with _proxy_locks_guard:
        return _proxy_locks.setdefault(media_id, Lock())
app.include_router(auth_router)

@app.middleware("http")
async def fail_closed_unintegrated_routes(request, call_next):
    path = request.url.path
    method = request.method.upper()

    # Defense in depth: every state-changing request made with an authenticated
    # browser session must pass the same double-submit CSRF check. Individual
    # handlers may retain their explicit checks; this guard prevents newly added
    # mutation routes from silently omitting protection. Login/register perform
    # their own origin validation and do not have an authenticated session yet.
    if (path.startswith("/api/") and method not in {"GET", "HEAD", "OPTIONS"}
            and path not in {"/api/auth/login", "/api/auth/register"}
            and request.headers.get("origin")
            and request.cookies.get("flexy_session")):
        try:
            _csrf_check(request)
        except HTTPException as exc:
            return Response(
                content='{"detail":"CSRF validation failed."}',
                status_code=exc.status_code,
                media_type="application/json",
            )

    allowed = (
        path == "/api/health"
        or path.startswith("/api/auth/")
        or (path == "/api/projects" and method in {"GET", "POST"})
        or (path.startswith("/api/projects/") and method == "GET" and path.count("/") == 3)
        or (path.startswith("/api/projects/") and path.endswith("/duplicate") and method == "POST")
        or (path.startswith("/api/projects/") and path.endswith("/organization") and method == "PATCH")
        or (path.startswith("/api/projects/") and method in {"PATCH", "DELETE"}
            and (path.endswith("/name") or path.count("/") == 3))
        or (path.startswith("/api/projects/") and "/media" in path)
        or (path.startswith("/api/projects/") and "/versions" in path and method in {"GET", "POST"})
        or (path.startswith("/api/media/") and method == "GET")
        or (path.startswith("/api/projects/") and "/render-preflight" in path and method == "POST")
        or (path.startswith("/api/projects/") and path.endswith("/renders") and method in {"GET", "POST"})
        or (path.startswith("/api/renders/") and method in {"GET", "POST", "DELETE"})
        or (path == "/api/assistant/plan" and method == "POST")
        or (path == "/api/assistant/recommendations" and method == "POST")
        or (path == "/api/assistant/dialogue-edit-plan" and method == "POST")
        or (path == "/api/assistant/smart-timeline" and method == "POST")
        or (path == "/api/subtitles/export" and method == "POST")
    )
    if path.startswith("/api/") and not allowed:
        return Response(
            content='{"detail":"This endpoint is temporarily disabled while account ownership protection is integrated."}',
            status_code=503, media_type="application/json"
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
ALLOWED_PREFIXES = ("video/", "audio/", "image/")

def resolve_upload_media_type(filename: str | None, supplied_type: str | None) -> str | None:
    """Use the browser MIME when useful, otherwise infer from the filename extension.

    The inferred value is only a classification hint: probe_media still validates
    the uploaded bytes and rejects files without a readable media stream.
    """
    # Do not pass playlist/container-manifest files or SVG through the media
    # probing and FFmpeg pipeline. Playlists can reference remote/local resources,
    # while SVG can contain external references. A spoofed browser MIME must not
    # override these extension-level exclusions.
    suffix = Path(filename or "").suffix.lower()
    blocked_suffixes = {".m3u", ".m3u8", ".pls", ".xspf", ".asx", ".ism", ".mpd", ".svg", ".svgz"}
    if suffix in blocked_suffixes:
        return None
    supplied = (supplied_type or "").split(";", 1)[0].strip().lower()
    if supplied.startswith(ALLOWED_PREFIXES) and supplied != "image/svg+xml":
        return supplied
    guessed, _encoding = mimetypes.guess_type(filename or "")
    if guessed and guessed.startswith(ALLOWED_PREFIXES):
        return guessed
    return None

class ProjectRequest(BaseModel):
    name: str = Field(default="Untitled project", min_length=1, max_length=120)
    project: dict[str, Any]
    expected_revision: int = Field(default=0, ge=0)

class DuplicateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)

class ProjectRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)

class ProjectOrganizationRequest(BaseModel):
    folder_name: str | None = Field(default=None, max_length=80)
    is_favorite: bool | None = None

class EditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    project_id: str = Field(min_length=1, max_length=80)
    project: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    transcript: str = Field(default="", max_length=12000)

class RenderRequest(BaseModel):
    graph: dict[str, Any]

class RecommendationRequest(BaseModel):
    scenes: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    duration: float | None = Field(default=None, ge=0)
    style: str = Field(default="balanced", pattern="^(balanced|dynamic|calm)$")

class SmartTimelineRequest(BaseModel):
    assets: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    scenes: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    target_duration: float = Field(default=30, ge=1, le=600)
    style: str = Field(default="balanced", pattern="^(balanced|dynamic|calm)$")
    max_shot_duration: float | None = Field(default=None, ge=0.5, le=15)
    min_shot_duration: float | None = Field(default=None, ge=0.5, le=10)
    beat_times: list[float] = Field(default_factory=list, max_length=5000)

class DialogueEditPlanRequest(BaseModel):
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    pause_threshold: float = Field(default=1.2, ge=0.2, le=10)
    max_block_duration: float = Field(default=24.0, ge=3, le=120)


class SubtitleExportRequest(BaseModel):
    segments: list[dict[str, Any]] = Field(default_factory=list)
    format: str = Field(default="srt", pattern="^(srt|vtt)$")
    include_speaker_labels: bool = False

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "FLEXY AI", "version": APP_VERSION,
            "ffmpeg_available": __import__("shutil").which("ffmpeg") is not None}

@app.post("/api/projects")
def put_project(request: ProjectRequest, user=Depends(current_user)):
    project_id = str(request.project.get("id") or uuid.uuid4())
    project_payload = dict(request.project)
    # Ownership is server-controlled and never accepted from the project payload.
    project_payload.pop("owner_id", None)
    try:
        row = storage.save_project_for_owner(
            user.id, project_id, request.name, project_payload, request.expected_revision
        )
    except storage.ProjectVersionConflict as exc:
        current = storage.get_project_for_owner(user.id, project_id)
        raise HTTPException(409, detail={
            "code": "PROJECT_VERSION_CONFLICT", "message": str(exc),
            "current_revision": current["revision"] if current else 0,
            "updated_at": current["updated_at"] if current else None,
        }) from exc
    except KeyError as exc:
        raise HTTPException(404, "Project not found.") from exc
    return {"id": row["id"], "name": row["name"], "updated_at": row["updated_at"],
            "revision": row["revision"]}

@app.get("/api/projects")
def list_projects(folder: str | None = Query(default=None, max_length=80),
                 favorites_only: bool = Query(default=False),
                 search: str | None = Query(default=None, max_length=120),
                 sort: str = Query(default="updated_desc", pattern="^(updated_desc|created_asc|created_desc|name_asc|name_desc)$"),
                 user=Depends(current_user)):
    projects = storage.list_projects_for_owner(user.id)
    if folder is not None:
        projects = [item for item in projects if item.get("folder_name", "") == folder]
    if favorites_only:
        projects = [item for item in projects if item.get("is_favorite")]
    if search:
        needle = search.casefold().strip()
        projects = [item for item in projects if needle in item["name"].casefold()]
    sorters = {
        "updated_desc": lambda x: x.get("updated_at", ""),
        "created_asc": lambda x: x.get("created_at", ""),
        "created_desc": lambda x: x.get("created_at", ""),
        "name_asc": lambda x: x.get("name", "").casefold(),
        "name_desc": lambda x: x.get("name", "").casefold(),
    }
    projects.sort(key=sorters[sort], reverse=sort in {"updated_desc", "created_desc", "name_desc"})
    folders = sorted({item.get("folder_name", "") for item in projects if item.get("folder_name")})
    return {"projects": projects, "folders": folders, "sort": sort}

@app.patch("/api/projects/{project_id}/name")
def rename_project(project_id: str, request: ProjectRenameRequest, user=Depends(current_user)):
    row = storage.rename_project_for_owner(user.id, project_id, request.name)
    if not row:
        raise HTTPException(404, "Project not found.")
    return row

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user=Depends(current_user)):
    try:
        deleted = storage.delete_project_for_owner(user.id, project_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    if deleted is None:
        raise HTTPException(404, "Project not found.")
    for filename in deleted["media_files"]:
        storage.safe_storage_path(storage.MEDIA_DIR, filename).unlink(missing_ok=True)
    for filename in deleted["render_files"]:
        storage.safe_storage_path(storage.RENDER_DIR, filename).unlink(missing_ok=True)
    return {"id": project_id, "deleted": True}

@app.patch("/api/projects/{project_id}/organization")
def update_project_organization(project_id: str, request: ProjectOrganizationRequest,
                                user=Depends(current_user)):
    if request.folder_name is None and request.is_favorite is None:
        raise HTTPException(422, "Provide a folder name or favorite state.")
    row = storage.update_project_organization_for_owner(
        user.id, project_id, folder_name=request.folder_name, is_favorite=request.is_favorite
    )
    if not row:
        raise HTTPException(404, "Project not found.")
    return row


@app.post("/api/projects/{project_id}/duplicate", status_code=201)
def duplicate_project(project_id: str, request: DuplicateProjectRequest, user=Depends(current_user)):
    """Duplicate a project and its media into an independent project."""
    source = storage.get_project_for_owner(user.id, project_id)
    if not source:
        raise HTTPException(404, "Project not found.")

    new_id = str(uuid.uuid4())
    new_name = request.name or f"{source['name']} copy"
    media_records = storage.get_project_media_records(project_id)
    id_map: dict[str, str] = {}
    copied_media: list[dict[str, Any]] = []
    copied_paths: list[Path] = []

    try:
        for media in media_records:
            new_media_id = str(uuid.uuid4())
            suffix = Path(media["stored_name"]).suffix
            new_stored_name = f"{new_media_id}{suffix}"
            source_path = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
            destination = storage.MEDIA_DIR / new_stored_name
            if not source_path.is_file():
                raise FileNotFoundError(f"Media file is missing: {media['filename']}")
            shutil.copy2(source_path, destination)
            copied_paths.append(destination)
            id_map[media["id"]] = new_media_id
            copied_media.append({**media, "id": new_media_id, "stored_name": new_stored_name})

        def remap_media_references(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: remap_media_references(item) for key, item in value.items()}
            if isinstance(value, list):
                return [remap_media_references(item) for item in value]
            if isinstance(value, str) and value in id_map:
                return id_map[value]
            return value

        cloned_project = remap_media_references(source["project"])
        cloned_project["id"] = new_id
        row = storage.duplicate_project_for_owner(user.id, project_id, new_id, new_name, cloned_project, copied_media)
    except KeyError as exc:
        for path in copied_paths:
            path.unlink(missing_ok=True)
        raise HTTPException(404, "Project not found.") from exc
    except FileNotFoundError as exc:
        for path in copied_paths:
            path.unlink(missing_ok=True)
        raise HTTPException(409, str(exc)) from exc
    except Exception:
        for path in copied_paths:
            path.unlink(missing_ok=True)
        raise

    return {"id": row["id"], "name": row["name"], "revision": row["revision"],
            "source_project_id": project_id, "media_count": len(copied_media)}


@app.get("/api/projects/{project_id}/media")
def list_project_media(project_id: str, user=Depends(current_user)):
    media = storage.list_project_media_for_owner(user.id, project_id)
    if media is None:
        raise HTTPException(404, "Project not found.")
    return {"media": media}

@app.get("/api/projects/{project_id}/versions")
def list_project_versions(project_id: str, user=Depends(current_user)):
    versions = storage.list_project_versions_for_owner(user.id, project_id)
    if versions is None:
        raise HTTPException(404, "Project not found.")
    return {"versions": versions}


@app.get("/api/projects/{project_id}/versions/{revision}")
def read_project_version(project_id: str, revision: int, user=Depends(current_user)):
    if revision < 1:
        raise HTTPException(422, "Revision must be at least 1.")
    version = storage.get_project_version_for_owner(user.id, project_id, revision)
    if not version:
        raise HTTPException(404, "Project version not found.")
    return version


@app.post("/api/projects/{project_id}/versions/{revision}/restore")
def restore_project_version(project_id: str, revision: int,
                            expected_revision: int = Query(..., ge=1),
                            user=Depends(current_user)):
    """Restore an account-owned snapshot as a new revision, never rewind history."""
    if revision < 1:
        raise HTTPException(422, "Revision must be at least 1.")
    snapshot = storage.get_project_version_for_owner(user.id, project_id, revision)
    if not snapshot:
        raise HTTPException(404, "Project version not found.")
    try:
        restored = storage.save_project_for_owner(
            user.id, project_id, snapshot["name"], snapshot["project"], expected_revision
        )
    except storage.ProjectVersionConflict as exc:
        latest = storage.get_project_for_owner(user.id, project_id)
        raise HTTPException(409, detail={
            "code": "PROJECT_VERSION_CONFLICT", "message": str(exc),
            "current_revision": latest["revision"] if latest else 0,
            "updated_at": latest["updated_at"] if latest else None,
        }) from exc
    except KeyError as exc:
        raise HTTPException(404, "Project not found.") from exc
    return {"id": restored["id"], "revision": restored["revision"],
            "restored_from_revision": revision, "name": restored["name"]}


@app.get("/api/projects/{project_id}")
def read_project(project_id: str, user=Depends(current_user)):
    result = storage.get_project_for_owner(user.id, project_id)
    if not result:
        raise HTTPException(404, "Project not found.")
    return result

@app.post("/api/projects/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...), user=Depends(current_user)):
    if not storage.get_project_for_owner(user.id, project_id):
        raise HTTPException(404, "Create the project before uploading media.")
    effective_media_type = resolve_upload_media_type(file.filename, file.content_type)
    if not effective_media_type:
        raise HTTPException(415, "Only video, audio and image uploads are accepted. Use a recognizable media file extension.")
    media_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload.bin").suffix[:12]
    stored_name = f"{media_id}{suffix}"
    destination = storage.MEDIA_DIR / stored_name
    size = 0
    try:
        storage.ensure_dirs()
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Upload exceeds the 1 GB development limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    try:
        metadata = probe_media(destination)
    except MediaProbeError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(415, str(exc)) from exc
    duration = metadata.get("duration")
    media = {"id": media_id, "project_id": project_id, "filename": file.filename or "upload",
             "stored_name": stored_name, "mime_type": effective_media_type, "size_bytes": size,
             "duration": duration, "metadata": metadata}
    try:
        storage.add_media_for_owner(user.id, media)
    except KeyError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(404, "Project not found.") from exc
    return {"id": media_id, "filename": media["filename"], "mime_type": media["mime_type"],
            "size_bytes": size, "duration": duration, "metadata": metadata}

@app.get("/api/projects/{project_id}/media/{media_id}/thumbnail")
def read_media_thumbnail(project_id: str, media_id: str, timestamp: float = Query(default=0.5, ge=0),
                         user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if not media["mime_type"].startswith("video/"):
        raise HTTPException(415, "Thumbnails are available for video assets.")
    if media.get("duration") is not None and timestamp > float(media["duration"]) + 0.1:
        raise HTTPException(422, "Thumbnail timestamp is outside the media duration.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    preview_dir = storage.DATA_DIR / "thumbnails"
    preview_path = preview_dir / f"{media_id}-{int(timestamp * 1000)}.jpg"
    if not preview_path.is_file():
        try:
            extract_scene_thumbnail(source, timestamp, preview_path)
        except SceneDetectionError as exc:
            raise HTTPException(422, str(exc)) from exc
    return FileResponse(preview_path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})

@app.get("/api/projects/{project_id}/media/{media_id}/proxy")
def read_media_proxy(project_id: str, media_id: str, user=Depends(current_user)):
    """Create or reuse a lightweight 540p editing proxy for responsive browser playback."""
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if not media["mime_type"].startswith("video/"):
        raise HTTPException(415, "Playback proxies are available for video assets.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(503, "FFmpeg is required to create a playback proxy.")
    proxy_dir = storage.DATA_DIR / "proxies"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    stat = source.stat()
    proxy_path = proxy_dir / f"{media_id}-{stat.st_size}-{stat.st_mtime_ns}.mp4"
    with _proxy_lock(media_id):
        if not proxy_path.is_file() or proxy_path.stat().st_size == 0:
            temporary = proxy_dir / f"{media_id}-{uuid.uuid4().hex}.tmp.mp4"
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                "-map", "0:v:0", "-map", "0:a?", "-vf",
                "scale=w='min(960,iw)':h=-2:force_original_aspect_ratio=decrease,fps=30",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-maxrate", "1800k", "-bufsize", "3600k",
                "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(temporary),
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=240)
                if result.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
                    raise RuntimeError((result.stderr or "Proxy encoding failed.")[-1200:])
                temporary.replace(proxy_path)
                for stale in proxy_dir.glob(f"{media_id}-*.mp4"):
                    if stale != proxy_path and ".tmp." not in stale.name:
                        stale.unlink(missing_ok=True)
            except subprocess.TimeoutExpired as exc:
                temporary.unlink(missing_ok=True)
                raise HTTPException(504, "Proxy generation exceeded the four-minute limit.") from exc
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                if isinstance(exc, HTTPException):
                    raise
                raise HTTPException(422, f"Could not create playback proxy: {str(exc)[:900]}") from exc
    return FileResponse(proxy_path, media_type="video/mp4",
                        headers={"Cache-Control": "private, max-age=86400",
                                 "X-FLEXY-Proxy": "540p"})


@app.get("/api/projects/{project_id}/media/{media_id}/waveform")
def read_media_waveform(project_id: str, media_id: str, user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if not media["mime_type"].startswith(("audio/", "video/")):
        raise HTTPException(415, "Waveforms are available for audio and video assets.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    try:
        return {"media_id": media_id, **audio_waveform(source)}
    except MediaPreviewError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.get("/api/media/{media_id}")
def read_media(media_id: str, user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id)
    if not media:
        raise HTTPException(404, "Media asset not found.")
    path = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not path.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    return FileResponse(path, media_type=media["mime_type"], filename=media["filename"],
                        headers={"Cache-Control": "private, no-store"})

@app.post("/api/projects/{project_id}/media/{media_id}/scenes")
def analyze_media_scenes(project_id: str, media_id: str, threshold: float = 0.35,
                         max_scenes: int = 500, include_visual_scores: bool = False,
                         user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    streams = media.get("metadata", {}).get("streams", [])
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise HTTPException(415, "Scene detection is available for video assets only.")
    path = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if include_visual_scores and max_scenes > 50:
        raise HTTPException(422, "Visual scoring is limited to 50 scenes per request.")
    try:
        scenes = detect_scenes(path, threshold=threshold, max_scenes=max_scenes)
        if include_visual_scores:
            thumbnail_dir = storage.DATA_DIR / "thumbnails"
            for index, scene in enumerate(scenes):
                timestamp = representative_scene_timestamp(
                    scenes, index, float(media.get("duration") or 0) or None
                )
                scene["visual_sample_time"] = timestamp
                thumbnail_path = thumbnail_dir / f"{media_id}-{int(timestamp * 1000)}.jpg"
                if not thumbnail_path.is_file():
                    extract_scene_thumbnail(path, timestamp, thumbnail_path)
                insights = describe_frame(thumbnail_path)
                scene["visual_interest"] = insights["visual_interest"]
                scene["visual_evidence"] = {
                    "analysis_type": insights["analysis_type"],
                    "edge_strength": insights["edge_strength"],
                    "colorfulness": insights["colorfulness"],
                    "semantic_recognition": False,
                }
    except (SceneDetectionError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"media_id": media_id, "threshold": threshold, "scene_count": len(scenes),
            "visual_scores_included": include_visual_scores, "scenes": scenes}

@app.get("/api/projects/{project_id}/media/{media_id}/scene-thumbnail")
def read_scene_thumbnail(project_id: str, media_id: str, timestamp: float = 0.0,
                         user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if timestamp < 0 or timestamp > float(media.get("duration") or 0) + 1:
        raise HTTPException(422, "Thumbnail timestamp is outside the media duration.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    thumbnail_dir = storage.DATA_DIR / "thumbnails"
    thumbnail_path = thumbnail_dir / f"{media_id}-{int(timestamp * 1000)}.jpg"
    try:
        if not thumbnail_path.is_file():
            extract_scene_thumbnail(source, timestamp, thumbnail_path)
    except SceneDetectionError as exc:
        raise HTTPException(422, str(exc)) from exc
    return FileResponse(thumbnail_path, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400"})

@app.get("/api/projects/{project_id}/media/{media_id}/scene-insights")
def read_scene_insights(project_id: str, media_id: str, timestamp: float = 0.0,
                        user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if timestamp < 0 or timestamp > float(media.get("duration") or 0) + 1:
        raise HTTPException(422, "Frame timestamp is outside the media duration.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    thumbnail_dir = storage.DATA_DIR / "thumbnails"
    thumbnail_path = thumbnail_dir / f"{media_id}-{int(timestamp * 1000)}.jpg"
    try:
        if not thumbnail_path.is_file():
            extract_scene_thumbnail(source, timestamp, thumbnail_path)
        return {"media_id": media_id, "timestamp": timestamp, "insights": describe_frame(thumbnail_path)}
    except (SceneDetectionError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/projects/{project_id}/media/{media_id}/scene-vision")
def read_scene_vision(project_id: str, media_id: str, timestamp: float = 0.0,
                      user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    if timestamp < 0 or timestamp > float(media.get("duration") or 0) + 1:
        raise HTTPException(422, "Thumbnail timestamp is outside the media duration.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    thumbnail_dir = storage.DATA_DIR / "thumbnails"
    thumbnail_path = thumbnail_dir / f"{media_id}-{int(timestamp * 1000)}.jpg"
    try:
        if not thumbnail_path.is_file():
            extract_scene_thumbnail(source, timestamp, thumbnail_path)
        return {"media_id": media_id, "timestamp": timestamp, "analysis": describe_scene(thumbnail_path)}
    except SceneDetectionError as exc:
        raise HTTPException(422, str(exc)) from exc
    except VisionProviderError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.get("/api/projects/{project_id}/media/{media_id}/audio-quality")
def read_audio_quality(project_id: str, media_id: str, user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    streams = media.get("metadata", {}).get("streams", [])
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise HTTPException(415, "Audio quality analysis requires an audio stream.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    try:
        result = analyze_loudness(source)
    except AudioAnalysisError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"media_id": media_id, **result}

@app.get("/api/projects/{project_id}/media/{media_id}/beats")
def read_audio_beats(project_id: str, media_id: str, user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    streams = media.get("metadata", {}).get("streams", [])
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise HTTPException(415, "Beat detection requires an audio stream.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    try:
        result = analyze_beats(source)
    except AudioAnalysisError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"media_id": media_id, **result}

@app.get("/api/projects/{project_id}/media/{media_id}/silence")
def read_media_silence(project_id: str, media_id: str, noise_db: float = Query(default=-35.0), min_duration: float = Query(default=0.4), user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    streams = media.get("metadata", {}).get("streams", [])
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise HTTPException(415, "Silence detection requires media containing an audio stream.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    try:
        result = detect_silence(source, noise_db=noise_db, min_duration=min_duration)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SpeechProviderError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"media_id": media_id, **result}


@app.post("/api/projects/{project_id}/media/{media_id}/transcribe")
def transcribe_project_media(project_id: str, media_id: str, language: str | None = Query(default=None, min_length=2, max_length=20), user=Depends(current_user)):
    media = storage.get_media_for_owner(user.id, media_id, project_id)
    if not media:
        raise HTTPException(404, "Media asset not found in this project.")
    streams = media.get("metadata", {}).get("streams", [])
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise HTTPException(415, "Transcription requires media containing an audio stream.")
    source = storage.safe_storage_path(storage.MEDIA_DIR, media["stored_name"])
    if not source.is_file():
        raise HTTPException(404, "Stored media file is missing.")
    try:
        result = transcribe_media(source, language=language)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SpeechProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    if not result.get("available"):
        raise HTTPException(503, result.get("notice", "Speech provider is not configured."))
    return {"media_id": media_id, **result}

@app.post("/api/subtitles/export")
def export_subtitles(request: SubtitleExportRequest, http_request: Request, user=Depends(current_user)):
    _csrf_check(http_request)
    try:
        content = subtitles(request.segments, request.format, include_speaker_labels=request.include_speaker_labels)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    media_type = "text/vtt; charset=utf-8" if request.format == "vtt" else "application/x-subrip; charset=utf-8"
    return Response(content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=flexy-captions.{request.format}"})



def run_render_job(job_id: str, graph: dict[str, Any]) -> None:
    """Render a previously owner-authorized immutable graph in the background."""
    output_name = f"{job_id}.mp4"
    output_path = storage.RENDER_DIR / output_name
    try:
        if not storage.start_job(job_id):
            return

        def cancelled() -> bool:
            job = storage.get_job(job_id)
            return not job or job.get("status") in ("cancelling", "cancelled")

        def progress(value: int) -> None:
            storage.update_job_progress(job_id, value)

        render_mp4(graph, output_path, progress_callback=progress, cancel_check=cancelled)
        if not storage.complete_job_if_processing(job_id, output_name):
            output_path.unlink(missing_ok=True)
            storage.update_job(job_id, status="cancelled", progress=0, output_name=None,
                               error="Render cancelled.")
    except RenderCancelledError:
        output_path.unlink(missing_ok=True)
        storage.update_job(job_id, status="cancelled", progress=0, output_name=None,
                           error="Render cancelled.")
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        storage.update_job(job_id, status="failed", progress=0, output_name=None,
                           error=str(exc)[:3000])


@app.post("/api/projects/{project_id}/render-preflight")
def render_preflight(project_id: str, request: RenderRequest, user=Depends(current_user)):
    try:
        return inspect_render(project_id, request.graph, owner_id=user.id)
    except RenderValidationError as exc:
        message = str(exc)
        status = 404 if message == "Project not found." else 422
        raise HTTPException(status, message) from exc


@app.post("/api/projects/{project_id}/renders", status_code=202)
def create_render(project_id: str, request: RenderRequest,
                  background_tasks: BackgroundTasks, user=Depends(current_user)):
    try:
        graph, _ = validate_project_render_graph(project_id, request.graph, owner_id=user.id)
    except RenderValidationError as exc:
        message = str(exc)
        status = 404 if message == "Project not found." else 422
        raise HTTPException(status, message) from exc
    job_id = str(uuid.uuid4())
    if not storage.create_job_for_owner(user.id, job_id, project_id):
        raise HTTPException(404, "Project not found.")
    background_tasks.add_task(run_render_job, job_id, graph)
    return {"id": job_id, "status": "queued", "status_url": f"/api/renders/{job_id}"}


@app.get("/api/projects/{project_id}/renders")
def list_project_renders(project_id: str, user=Depends(current_user)):
    jobs = storage.list_project_renders_for_owner(user.id, project_id)
    if jobs is None:
        raise HTTPException(404, "Project not found.")
    items = []
    for job in jobs:
        result = {key: job[key] for key in ("id", "project_id", "status", "progress", "error", "created_at", "updated_at")}
        if job["status"] == "completed" and job["output_name"]:
            result["download_url"] = f"/api/renders/{job['id']}/download"
        items.append(result)
    return {"renders": items}


@app.delete("/api/renders/{job_id}")
def delete_render_record(job_id: str, user=Depends(current_user)):
    job = storage.get_job_for_owner(user.id, job_id)
    if not job:
        raise HTTPException(404, "Render job not found.")
    if job["status"] not in ("completed", "failed", "cancelled", "interrupted"):
        raise HTTPException(409, "Only finished render jobs can be removed from history.")
    output_name = Path(job["output_name"]).name if job.get("output_name") else None
    deleted = storage.delete_terminal_job_for_owner(user.id, job_id)
    if not deleted:
        raise HTTPException(409, "Render history changed. Refresh and try again.")
    if output_name:
        storage.safe_storage_path(storage.RENDER_DIR, output_name).unlink(missing_ok=True)
    return {"id": job_id, "deleted": True}


@app.get("/api/renders/{job_id}")
def render_status(job_id: str, user=Depends(current_user)):
    job = storage.get_job_for_owner(user.id, job_id)
    if not job:
        raise HTTPException(404, "Render job not found.")
    result = {key: job[key] for key in ("id", "project_id", "status", "progress", "error", "created_at", "updated_at")}
    if job["status"] == "completed":
        result["download_url"] = f"/api/renders/{job_id}/download"
    return result


@app.post("/api/renders/{job_id}/cancel")
def cancel_render(job_id: str, user=Depends(current_user)):
    job = storage.request_job_cancel_for_owner(user.id, job_id)
    if not job:
        raise HTTPException(404, "Render job not found.")
    if job["status"] == "cancelling":
        return {"id": job_id, "status": "cancelling", "message": "Cancellation requested."}
    if job["status"] == "cancelled":
        return {"id": job_id, "status": "cancelled", "message": "Render is already cancelled."}
    if job["status"] in ("completed", "failed", "interrupted"):
        raise HTTPException(409, f"Cannot cancel a render that is already {job['status']}.")
    return {"id": job_id, "status": job["status"], "message": "Cancellation requested."}


@app.get("/api/renders/{job_id}/download")
def download_render(job_id: str, user=Depends(current_user)):
    job = storage.get_job_for_owner(user.id, job_id)
    if not job or job["status"] != "completed" or not job["output_name"]:
        raise HTTPException(404, "Completed render not found.")
    filename = Path(job["output_name"]).name
    path = storage.safe_storage_path(storage.RENDER_DIR, filename).resolve()
    if path.parent != storage.RENDER_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Rendered file is missing.")
    return FileResponse(path, media_type="video/mp4", filename="flexy-export.mp4",
                        headers={"Cache-Control": "private, no-store"})


@app.post("/api/assistant/plan")
def plan_edit(request: EditRequest, http_request: Request, user=Depends(current_user)):
    _csrf_check(http_request)
    # The project must belong to the signed-in account. Client-supplied project
    # metadata is treated as context only, never as proof of ownership.
    owned = storage.get_project_for_owner(user.id, request.project_id)
    if not owned:
        raise HTTPException(404, "Project not found.")
    project = dict(request.project)
    project["id"] = request.project_id
    # Keep provider input to bounded, non-file metadata. Media bytes are never
    # uploaded to the language model by this endpoint.
    safe_assets = []
    for asset in request.assets[:200]:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id", ""))[:120]
        mime_type = str(asset.get("mime_type", ""))[:120]
        kind = "video" if mime_type.startswith("video/") else "audio" if mime_type.startswith("audio/") else "image" if mime_type.startswith("image/") else ""
        if not asset_id or not kind:
            continue
        try:
            duration = max(0.0, min(86400.0, float(asset.get("duration") or 0)))
        except (TypeError, ValueError):
            duration = 0.0
        safe_assets.append({"id": asset_id, "type": kind, "duration": duration,
                            "filename": str(asset.get("filename", ""))[:180]})
    plan = build_edit_plan(request.instruction, safe_assets, project, request.transcript)
    plan["message"] = "Edit plan generated. Review suggestions before applying any timeline changes."
    return plan


@app.post("/api/assistant/recommendations")
def edit_recommendations(request: RecommendationRequest, http_request: Request, user=Depends(current_user)):
    """Return non-destructive edit suggestions for an authenticated editing session."""
    _csrf_check(http_request)
    try:
        return build_recommendations(request.scenes, request.transcript_segments, request.duration, request.style)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/assistant/dialogue-edit-plan")
def dialogue_edit_plan(request: DialogueEditPlanRequest, http_request: Request, user=Depends(current_user)):
    """Group transcript into dialogue beats and suggest review-only cut boundaries."""
    _csrf_check(http_request)
    try:
        return build_dialogue_edit_plan(request.transcript_segments,
                                        pause_threshold=request.pause_threshold,
                                        max_block_duration=request.max_block_duration)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/assistant/smart-timeline")
def smart_timeline(request: SmartTimelineRequest, http_request: Request, user=Depends(current_user)):
    """Build a non-destructive first cut for an authenticated editing session."""
    _csrf_check(http_request)
    try:
        return build_smart_timeline(request.assets, request.scenes, request.transcript_segments,
                                    request.target_duration, request.style, request.max_shot_duration, request.min_shot_duration, request.beat_times)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
