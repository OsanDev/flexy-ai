const API = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function csrfToken(): string {
  const item = document.cookie.split("; ").find((part) => part.startsWith("flexy_csrf="));
  if (!item) throw new Error("Session security token is missing. Sign in again.");
  return decodeURIComponent(item.slice("flexy_csrf=".length));
}

export interface SmartTimelineAsset {
  id: string;
  type: "video" | "audio" | "image";
  duration?: number | null;
  name?: string;
  scenes?: SmartTimelineScene[];
}

export interface SmartTimelineScene {
  start: number;
  visual_interest?: number;
  subject_presence?: number;
  motion_suitability?: number;
  visual_sample_time?: number;
  visual_evidence?: Record<string, unknown>;
}

export interface SmartTimelineClip {
  assetId: string;
  start: number;
  sourceStart: number;
  duration: number;
  transition: string;
  evidence: {
    scene_start: number;
    dialogue_overlap_seconds: number;
    contains_transcript: boolean;
    dialogue_density: number;
    duration_fit: number;
    visual_signals: Record<string, number>;
    visual_score: number | null;
    shot_score: number;
    beat_aligned?: boolean;
    beats_per_shot?: number | null;
    beat_interval_seconds?: number | null;
  };
  reason: string;
}

export interface SmartTimelineDraft {
  engine: string;
  style: "balanced" | "dynamic" | "calm";
  clips: SmartTimelineClip[];
  audio_clips: Array<{ assetId: string; start: number; sourceStart: number; duration: number; volume: number }>;
  duration: number;
  target_duration: number;
  max_shot_duration?: number | null;
  min_shot_duration?: number | null;
  beat_sync?: boolean;
  beat_interval_seconds?: number | null;
  warnings: string[];
}

/** Requests a non-destructive first-cut draft. The caller decides whether to apply it. */
export async function requestSmartTimeline(input: {
  assets: SmartTimelineAsset[];
  scenes?: SmartTimelineScene[];
  transcriptSegments?: Array<{ start: number; end: number; text: string }>;
  targetDuration: number;
  style?: "balanced" | "dynamic" | "calm";
  maxShotDuration?: number;
  minShotDuration?: number;
  /** Optional beat timestamps in seconds from an upstream audio analyzer. */
  beatTimes?: number[];
}): Promise<SmartTimelineDraft> {
  const response = await fetch(`${API}/api/assistant/smart-timeline`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
    body: JSON.stringify({
      assets: input.assets,
      scenes: input.scenes ?? [],
      transcript_segments: input.transcriptSegments ?? [],
      target_duration: input.targetDuration,
      style: input.style ?? "balanced",
      max_shot_duration: input.maxShotDuration,
      min_shot_duration: input.minShotDuration,
      beat_times: input.beatTimes ?? [],
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "FLEXY AI could not build a Smart Timeline draft.";
    throw new Error(detail);
  }
  return payload as SmartTimelineDraft;
}

export interface AudioBeatAnalysis {
  media_id: string;
  detector: "energy-onset-v1";
  beats: number[];
  estimated_bpm: number | null;
  confidence: number;
  duration_analyzed: number;
  truncated?: boolean;
  notice: string;
}

/** Detects candidate beat timestamps from an uploaded audio/video asset. */
export async function requestAudioBeatAnalysis(projectId: string, mediaId: string): Promise<AudioBeatAnalysis> {
  const response = await fetch(
    `${API}/api/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(mediaId)}/beats`,
    { method: "GET", credentials: "include" },
  );
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "FLEXY AI could not analyse this audio.";
    throw new Error(detail);
  }
  return payload as AudioBeatAnalysis;
}
