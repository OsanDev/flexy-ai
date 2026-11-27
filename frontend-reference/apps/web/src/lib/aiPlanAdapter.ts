import type { MediaAsset } from "./mediaApi";
import { validateTimelineDocument, type TimelineDocument, type VideoTimelineClip, type AudioTimelineClip } from "./timelineGraph";

type RawDraftClip = {
  assetId?: unknown; start?: unknown; sourceStart?: unknown; duration?: unknown;
  transition?: unknown; volume?: unknown; fadeIn?: unknown; fadeOut?: unknown; role?: unknown;
};
export type DirectorTimelineDraft = {
  clips?: unknown; audio_clips?: unknown; warnings?: unknown;
};
export type DirectorTimelinePreview = {
  nextDocument: TimelineDocument;
  summary: string;
  changes: string[];
  warnings: string[];
};

function finite(value: unknown, label: string, minimum = 0): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum) {
    throw new Error(`${label} must be a finite number greater than or equal to ${minimum}.`);
  }
  return value;
}

function list(value: unknown, label: string): RawDraftClip[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 200) throw new Error(`${label} must be an array with at most 200 items.`);
  return value as RawDraftClip[];
}

function makeId(prefix: string, index: number): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID() : `${Date.now()}-${index}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${random}`;
}

/** Converts untrusted AI output into a validated, undoable timeline preview. */
export function adaptDirectorDraftToTimeline(
  draft: DirectorTimelineDraft | undefined,
  current: TimelineDocument,
  assets: MediaAsset[],
): DirectorTimelinePreview {
  if (!draft || typeof draft !== "object") throw new Error("The AI Director did not return a timeline draft.");
  const assetById = new Map(assets.map((asset) => [asset.id, asset]));
  const rawVideo = list(draft.clips, "Visual clips");
  const rawAudio = list(draft.audio_clips, "Audio clips");
  if (!rawVideo.length) throw new Error("No visual clips were supplied. Import a video or image and create a new plan.");
  const videoClips: VideoTimelineClip[] = rawVideo.map((raw, index) => {
    if (typeof raw.assetId !== "string" || !raw.assetId.trim()) throw new Error(`Visual clip ${index + 1} has no asset ID.`);
    const asset = assetById.get(raw.assetId);
    if (!asset || !(asset.mime_type.startsWith("video/") || asset.mime_type.startsWith("image/"))) {
      throw new Error(`Visual clip ${index + 1} references media that is not in this project's video/image library.`);
    }
    const sourceStart = finite(raw.sourceStart ?? 0, `Visual clip ${index + 1} source start`);
    const duration = finite(raw.duration, `Visual clip ${index + 1} duration`, 0.1);
    const timelineStart = finite(raw.start, `Visual clip ${index + 1} timeline start`);
    if (asset.duration !== null && asset.duration !== undefined && sourceStart + duration > asset.duration + 0.001) {
      throw new Error(`Visual clip ${index + 1} exceeds the available source duration.`);
    }
    const transition = raw.transition ?? "none";
    if (transition !== "none" && transition !== "fade" && transition !== "crossfade") {
      throw new Error(`Visual clip ${index + 1} has an unsupported transition.`);
    }
    return { id: makeId("ai-video", index), mediaId: asset.id, sourceStart, duration, timelineStart, trackIndex: 0, transition };
  });
  const audioClips: AudioTimelineClip[] = rawAudio.map((raw, index) => {
    if (typeof raw.assetId !== "string" || !raw.assetId.trim()) throw new Error(`Audio clip ${index + 1} has no asset ID.`);
    const asset = assetById.get(raw.assetId);
    if (!asset || !(asset.mime_type.startsWith("audio/") || asset.mime_type.startsWith("video/"))) {
      throw new Error(`Audio clip ${index + 1} references media that is not in this project's audio/video library.`);
    }
    const sourceStart = finite(raw.sourceStart ?? 0, `Audio clip ${index + 1} source start`);
    const duration = finite(raw.duration, `Audio clip ${index + 1} duration`, 0.1);
    const timelineStart = finite(raw.start, `Audio clip ${index + 1} timeline start`);
    if (asset.duration !== null && asset.duration !== undefined && sourceStart + duration > asset.duration + 0.001) {
      throw new Error(`Audio clip ${index + 1} exceeds the available source duration.`);
    }
    const volume = raw.volume === undefined ? 1 : finite(raw.volume, `Audio clip ${index + 1} volume`);
    const fadeIn = raw.fadeIn === undefined ? 0 : finite(raw.fadeIn, `Audio clip ${index + 1} fade in`);
    const fadeOut = raw.fadeOut === undefined ? 0 : finite(raw.fadeOut, `Audio clip ${index + 1} fade out`);
    const role = raw.role ?? "music";
    if (volume > 2 || fadeIn + fadeOut > duration || !["dialogue", "music", "other"].includes(String(role))) {
      throw new Error(`Audio clip ${index + 1} has invalid volume, fades, or role.`);
    }
    return { id: makeId("ai-audio", index), mediaId: asset.id, sourceStart, duration, timelineStart,
      trackIndex: 0, volume, fadeIn, fadeOut, role: role as AudioTimelineClip["role"] };
  });
  const warnings = Array.isArray(draft.warnings)
    ? draft.warnings.filter((item): item is string => typeof item === "string").slice(0, 12)
    : [];
  const nextDocument: TimelineDocument = {
    ...current,
    videoClips,
    audioClips,
    captions: [...current.captions],
  };
  const validationErrors = validateTimelineDocument(nextDocument);
  if (validationErrors.length) throw new Error(`The proposed timeline is not valid: ${validationErrors.join(" ")}`);
  const changes = [
    `Replace ${current.videoClips.length} existing visual clip(s) with ${videoClips.length} AI-planned clip(s) on video track 1.`,
    `Replace ${current.audioClips.length} existing audio clip(s) with ${audioClips.length} AI-planned audio clip(s).`,
    `Keep all ${current.captions.length} existing caption(s) unchanged.`,
  ];
  return { nextDocument, summary: `Preview contains ${videoClips.length} visual clip(s) and ${audioClips.length} audio clip(s).`,
    changes, warnings };
}
