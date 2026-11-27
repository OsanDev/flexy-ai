const API = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
function csrf() {
  const item = document.cookie.split("; ").find((part) => part.startsWith("flexy_csrf="));
  if (!item) throw new Error("Session security token is missing. Sign in again.");
  return decodeURIComponent(item.slice("flexy_csrf=".length));
}
async function json<T>(path: string, init: RequestInit = {}, protect = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (protect) headers.set("X-CSRF-Token", csrf());
  const response = await fetch(`${API}${path}`, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    let message = `Media request failed (${response.status}).`;
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export interface MediaAsset {
  id: string; project_id?: string; filename: string; mime_type: string;
  size_bytes: number; duration: number | null; metadata?: Record<string, unknown>;
}
export interface WaveformData { media_id: string; points?: number[]; samples?: number[]; waveform?: number[]; [key: string]: unknown }
export interface AudioQualityResult {
  media_id: string;
  standard: "EBU R128";
  integrated_lufs: number | null;
  loudness_range_lu: number | null;
  true_peak_dbfs: number | null;
  measurements_available: boolean;
  notice: string;
}
export interface DetectedScene {
  index: number;
  start: number;
  visual_interest?: number;
  visual_evidence?: {
    analysis_type: string;
    edge_strength: number;
    colorfulness: number;
    semantic_recognition: false;
  };
}
export interface SceneDetectionResult {
  media_id: string; threshold: number; scene_count: number;
  visual_scores_included?: boolean; scenes: DetectedScene[];
}
export interface SceneVisionResult {
  media_id: string; timestamp: number;
  analysis: { available: boolean; provider: string | null; model?: string; description: string | null;
    objects: string[]; actions: string[]; editing_notes: string[]; confidence?: number; notice: string };
}
export const mediaApi = {
  list(projectId: string) {
    return json<{media: MediaAsset[]}>(`/api/projects/${encodeURIComponent(projectId)}/media`);
  },
  upload(projectId: string, file: File, signal?: AbortSignal) {
    const body = new FormData(); body.append("file", file);
    return json<MediaAsset>(`/api/projects/${encodeURIComponent(projectId)}/media`, {method:"POST",body,signal}, true);
  },
  async proxyPreview(projectId: string, mediaId: string): Promise<string> {
    const path = `/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/proxy`;
    const response = await fetch(`${API}${path}`, { credentials: "include" });
    if (!response.ok) {
      let message = `Proxy preview failed (${response.status}).`;
      try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch {}
      throw new Error(message);
    }
    return URL.createObjectURL(await response.blob());
  },
  async preview(projectId: string, asset: MediaAsset, timestamp = 0.5): Promise<string | null> {
    let path: string;
    if (asset.mime_type.startsWith("video/"))
      path = `/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(asset.id)}/thumbnail?timestamp=${encodeURIComponent(String(Math.max(0, timestamp)))}`;
    else if (asset.mime_type.startsWith("image/")) path = `/api/media/${encodeURIComponent(asset.id)}`;
    else return null;
    const response = await fetch(`${API}${path}`, {credentials:"include"});
    return response.ok ? URL.createObjectURL(await response.blob()) : null;
  },
  transcribe(projectId: string, mediaId: string) {
    return this.transcribeWithLanguage(projectId, mediaId, "auto");
  },
  transcribeWithLanguage(projectId: string, mediaId: string, language = "auto") {
    const query = language === "auto" ? "" : `?language=${encodeURIComponent(language)}`;
    return json<TranscriptionResult>(
      `/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/transcribe${query}`,
      { method: "POST" }, true,
    );
  },
  dialogueEditPlan(segments: TranscriptionSegment[], pauseThreshold = 1.2, maxBlockDuration = 24) {
    return json<DialogueEditPlan>("/api/assistant/dialogue-edit-plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript_segments: segments, pause_threshold: pauseThreshold, max_block_duration: maxBlockDuration }),
    }, true);
  },
  async exportSubtitles(segments: TranscriptionSegment[], format: "srt" | "vtt"): Promise<Blob> {
    const response = await fetch(`${API}/api/subtitles/export`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
      body: JSON.stringify({ segments, format }),
    });
    if (!response.ok) {
      let message = `Subtitle export failed (${response.status}).`;
      try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch {}
      throw new Error(message);
    }
    return response.blob();
  },
  waveform(projectId: string, mediaId: string) {
    return json<WaveformData>(`/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/waveform`);
  },
  audioQuality(projectId: string, mediaId: string) {
    return json<AudioQualityResult>(`/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/audio-quality`);
  },
  detectScenes(projectId: string, mediaId: string, maxScenes = 50, includeVisualScores = true) {
    const boundedMaxScenes = Math.min(50, Math.max(1, Math.floor(maxScenes)));
    const query = new URLSearchParams({ max_scenes: String(boundedMaxScenes), include_visual_scores: String(includeVisualScores) });
    return json<SceneDetectionResult>(`/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/scenes?${query}`, { method: "POST" });
  },
  sceneVision(projectId: string, mediaId: string, timestamp: number) {
    const query = new URLSearchParams({ timestamp: String(Math.max(0, timestamp)) });
    return json<SceneVisionResult>(`/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/scene-vision?${query}`, { method: "POST" });
  },
};


export interface TranscriptionSegment { id: string; start: number; end: number; text: string; speaker_id?: string; words?: Array<{ word: string; start: number; end: number }> }
export interface DialogueEditPlan {
  available: boolean; block_count: number;
  blocks: Array<{ block_id: string; start: number; end: number; duration: number; text: string; segment_ids: string[]; speaker_ids: string[]; kind: string }>;
  boundary_count: number;
  cut_candidates: Array<{ at: number; previous_end: number; gap_seconds: number; reason: string; review_only: boolean; suggestion: string }>;
  speaker_labels_available: boolean; notice: string;
}
export interface TranscriptionResult {
  media_id: string;
  available: boolean;
  provider: string | null;
  model?: string;
  text: string;
  language?: string;
  segments: TranscriptionSegment[];
  analysis?: { segment_count: number; word_count: number; word_timestamps: number; active_duration_seconds: number; speaking_rate_wpm: number | null; long_pauses: Array<{ start: number; end: number; duration: number }>; filler_word_counts: Record<string, number>; notice: string };
  chunking?: { enabled: boolean; chunk_count: number; chunk_duration_seconds: number };
  notice: string;
}
