export type VideoTimelineClip = {
  id: string;
  mediaId: string;
  sourceStart: number;
  duration: number;
  timelineStart: number;
  trackIndex: number;
  transition: "none" | "fade" | "crossfade";
  opacity?: number;
  scale?: number;
  positionX?: number;
  positionY?: number;
  chromaKeyColor?: string;
  chromaKeySimilarity?: number;
  chromaKeyBlend?: number;
  positionKeyframes?: Array<{ time: number; x: number; y: number; confidence?: number }>;
};

export type AudioTimelineClip = {
  id: string;
  mediaId: string;
  sourceStart: number;
  duration: number;
  timelineStart: number;
  trackIndex: number;
  volume: number;
  fadeIn: number;
  fadeOut: number;
  role: "dialogue" | "music" | "other";
  volumeKeyframes?: Array<{ time: number; volume: number }>;
  bus?: "dialogue" | "music" | "effects";
};

export type CaptionStyle = {
  preset: "classic" | "bold" | "minimal" | "neon";
  position: "top" | "bottom";
  fontSize: number;
  color: string;
  backgroundColor: string;
  bold: boolean;
  animation?: "none" | "word" | "karaoke" | "pop" | "fade" | "slide";
  animationDuration?: number;
  alignment?: "left" | "center" | "right";
  outlineColor?: string;
  outlineWidth?: number;
  shadowColor?: string;
  shadowBlur?: number;
  verticalOffset?: number;
};

export type SavedCaptionPreset = {
  id: string;
  name: string;
  style: CaptionStyle;
};

export type CaptionTimelineItem = {
  id: string;
  text: string;
  start: number;
  duration: number;
  style?: CaptionStyle;
  wordTimings?: Array<{ word: string; start: number; end: number }>;
};

export type AudioBusSettings = { gain: number; muted: boolean };
export type AudioMixerSettings = { dialogue: AudioBusSettings; music: AudioBusSettings; effects: AudioBusSettings; master: AudioBusSettings };

export type TimelineDocument = {
  videoClips: VideoTimelineClip[];
  audioClips: AudioTimelineClip[];
  captions: CaptionTimelineItem[];
  captionPresets?: SavedCaptionPreset[];
  width: number;
  height: number;
  frameRate: number;
  exportPreset: "720p" | "1080p" | "4k" | "custom";
  videoBitrate: string;
  ducking: boolean;
  duckingSettings?: { thresholdDb: number; ratio: number; attackMs: number; releaseMs: number };
  hiddenVideoTracks?: number[];
  hiddenAudioTracks?: number[];
  captionsHidden?: boolean;
  soloAudioTrack?: number | null;
  trackNames?: Record<string, string>;
  trackColors?: Record<string, string>;
  audioMixer?: AudioMixerSettings;
};

export function buildRenderGraph(document: TimelineDocument): Record<string, unknown> {
  return {
    clips: [...document.videoClips]
      .filter((clip) => !(document.hiddenVideoTracks ?? []).includes(clip.trackIndex))
      .sort((a, b) => a.timelineStart - b.timelineStart || a.trackIndex - b.trackIndex)
      .map((clip) => ({
        media_id: clip.mediaId,
        source_start: clip.sourceStart,
        duration: clip.duration,
        timeline_start: clip.timelineStart,
        track_index: clip.trackIndex,
        transition: clip.transition,
        opacity: clip.opacity ?? 1,
        scale: clip.scale ?? 1,
        position_x: clip.positionX ?? 0,
        position_y: clip.positionY ?? 0,
        chroma_key_color: clip.chromaKeyColor ?? null,
        chroma_key_similarity: clip.chromaKeySimilarity ?? 0.3,
        chroma_key_blend: clip.chromaKeyBlend ?? 0.1,
        position_keyframes: clip.positionKeyframes ?? [],
      })),
    audio_clips: [...document.audioClips]
      .filter((clip) => !(document.hiddenAudioTracks ?? []).includes(clip.trackIndex))
      .sort((a, b) => a.timelineStart - b.timelineStart)
      .map((clip) => ({
        media_id: clip.mediaId,
        source_start: clip.sourceStart,
        duration: clip.duration,
        timeline_start: clip.timelineStart,
        track_index: clip.trackIndex,
        volume: document.soloAudioTrack !== undefined && document.soloAudioTrack !== null && clip.trackIndex !== document.soloAudioTrack ? 0 : clip.volume,
        fade_in: clip.fadeIn,
        fade_out: clip.fadeOut,
        role: clip.role,
        volume_keyframes: clip.volumeKeyframes ?? [],
        bus: clip.bus ?? (clip.role === "other" ? "effects" : clip.role),
      })),
    captions: (document.captionsHidden ? [] : [...document.captions])
      .sort((a, b) => a.start - b.start)
      .map((caption) => ({
        text: caption.text,
        start: caption.start,
        duration: caption.duration,
        word_timings: caption.wordTimings ?? [],
        style: caption.style ?? { preset: "classic", position: "bottom", fontSize: 28, color: "#ffffff", backgroundColor: "#000000b8", bold: true, animation: "none", animationDuration: 0.45 },
      })),
    width: document.width,
    height: document.height,
    frame_rate: document.frameRate,
    export_preset: document.exportPreset,
    video_bitrate: document.videoBitrate,
    audio_mixer: document.audioMixer ?? {
      dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false },
      effects: { gain: 1, muted: false }, master: { gain: 1, muted: false },
    },
    ducking: document.ducking,
    ducking_settings: document.duckingSettings ? {
      threshold_db: document.duckingSettings.thresholdDb,
      ratio: document.duckingSettings.ratio,
      attack_ms: document.duckingSettings.attackMs,
      release_ms: document.duckingSettings.releaseMs,
    } : undefined,
  };
}

export function getTimelineDuration(document: TimelineDocument): number {
  const videoEnd = document.videoClips.reduce(
    (max, clip) => Math.max(max, clip.timelineStart + clip.duration), 0,
  );
  const audioEnd = document.audioClips.reduce(
    (max, clip) => Math.max(max, clip.timelineStart + clip.duration), 0,
  );
  const captionEnd = document.captions.reduce(
    (max, caption) => Math.max(max, caption.start + caption.duration), 0,
  );
  return Math.max(videoEnd, audioEnd, captionEnd);
}

export function validateTimelineDocument(document: TimelineDocument): string[] {
  const errors: string[] = [];
  if (!document.videoClips.length) errors.push("Add at least one video or image clip.");
  for (const clip of document.videoClips) {
    if (!clip.mediaId.trim()) errors.push(`Video clip ${clip.id} needs a media ID.`);
    if (clip.duration <= 0 || clip.sourceStart < 0 || clip.timelineStart < 0) {
      errors.push(`Video clip ${clip.id} has an invalid time range.`);
    }
    if (!Number.isInteger(clip.trackIndex) || clip.trackIndex < 0 || clip.trackIndex > 7) {
      errors.push(`Video clip ${clip.id} must use a track from 0 to 7.`);
    }
    if (clip.opacity !== undefined && (!Number.isFinite(clip.opacity) || clip.opacity < 0 || clip.opacity > 1)) errors.push(`Video clip ${clip.id} opacity must be between 0 and 1.`);
    if (clip.scale !== undefined && (!Number.isFinite(clip.scale) || clip.scale < 0.1 || clip.scale > 3)) errors.push(`Video clip ${clip.id} scale must be between 0.1 and 3.`);
    if (clip.positionX !== undefined && (!Number.isFinite(clip.positionX) || Math.abs(clip.positionX) > 7680)) errors.push(`Video clip ${clip.id} horizontal position is out of range.`);
    if (clip.positionY !== undefined && (!Number.isFinite(clip.positionY) || Math.abs(clip.positionY) > 7680)) errors.push(`Video clip ${clip.id} vertical position is out of range.`);
    if (clip.chromaKeyColor !== undefined && !/^#[0-9a-fA-F]{6}$/.test(clip.chromaKeyColor)) errors.push(`Video clip ${clip.id} chroma key color must be a six-digit hex color.`);
    if (clip.chromaKeySimilarity !== undefined && (!Number.isFinite(clip.chromaKeySimilarity) || clip.chromaKeySimilarity < 0 || clip.chromaKeySimilarity > 1)) errors.push(`Video clip ${clip.id} chroma key similarity must be between 0 and 1.`);
    if (clip.chromaKeyBlend !== undefined && (!Number.isFinite(clip.chromaKeyBlend) || clip.chromaKeyBlend < 0 || clip.chromaKeyBlend > 1)) errors.push(`Video clip ${clip.id} chroma key blend must be between 0 and 1.`);
    let previousTrackingTime = -1;
    for (const point of clip.positionKeyframes ?? []) {
      if (!Number.isFinite(point.time) || point.time < 0 || point.time > clip.duration ||
          !Number.isFinite(point.x) || point.x < 0 || point.x > 1 ||
          !Number.isFinite(point.y) || point.y < 0 || point.y > 1 ||
          point.time <= previousTrackingTime) {
        errors.push(`Video clip ${clip.id} has invalid motion tracking keyframes.`);
        break;
      }
      previousTrackingTime = point.time;
    }
  }
  for (const clip of document.audioClips) {
    if (!clip.mediaId.trim()) errors.push(`Audio clip ${clip.id} needs a media ID.`);
    if (clip.duration <= 0 || clip.sourceStart < 0 || clip.timelineStart < 0) {
      errors.push(`Audio clip ${clip.id} has an invalid time range.`);
    }
    if (!Number.isInteger(clip.trackIndex) || clip.trackIndex < 0 || clip.trackIndex > 7) {
      errors.push(`Audio clip ${clip.id} must use a track from 0 to 7.`);
    }
    if (clip.volume < 0 || clip.volume > 2 || clip.fadeIn < 0 || clip.fadeOut < 0 ||
        clip.fadeIn + clip.fadeOut > clip.duration) {
      errors.push(`Audio clip ${clip.id} has invalid volume or fade settings.`);
    }
    if (clip.bus !== undefined && !["dialogue", "music", "effects"].includes(clip.bus)) {
      errors.push(`Audio clip ${clip.id} has an invalid output bus.`);
    }
    let previousKeyframeTime = -1;
    for (const point of clip.volumeKeyframes ?? []) {
      if (!Number.isFinite(point.time) || point.time < 0 || point.time > clip.duration ||
          !Number.isFinite(point.volume) || point.volume < 0 || point.volume > 2 ||
          point.time <= previousKeyframeTime) {
        errors.push(`Audio clip ${clip.id} has invalid volume automation keyframes.`);
        break;
      }
      previousKeyframeTime = point.time;
    }
  }
  if (document.audioMixer) {
    for (const bus of ["dialogue", "music", "effects", "master"] as const) {
      const settings = document.audioMixer[bus];
      if (!settings || !Number.isFinite(settings.gain) || settings.gain < 0 || settings.gain > 2 || typeof settings.muted !== "boolean") {
        errors.push(`Audio mixer ${bus} bus has invalid gain or mute settings.`);
      }
    }
  }
  if (document.duckingSettings) {
    const settings = document.duckingSettings;
    if (!Number.isFinite(settings.thresholdDb) || settings.thresholdDb < -40 || settings.thresholdDb > -6) {
      errors.push("Ducking threshold must be between -40 and -6 dB.");
    }
    if (!Number.isFinite(settings.ratio) || settings.ratio < 1 || settings.ratio > 20) {
      errors.push("Ducking ratio must be between 1 and 20.");
    }
    if (!Number.isFinite(settings.attackMs) || settings.attackMs < 1 || settings.attackMs > 200) {
      errors.push("Ducking attack must be between 1 and 200 ms.");
    }
    if (!Number.isFinite(settings.releaseMs) || settings.releaseMs < 50 || settings.releaseMs > 2000) {
      errors.push("Ducking release must be between 50 and 2000 ms.");
    }
  }
  for (const caption of document.captions) {
    if (!caption.text.trim()) errors.push(`Caption ${caption.id} needs text.`);
    if (caption.start < 0 || caption.duration <= 0) errors.push(`Caption ${caption.id} has an invalid time range.`);
  }
  if (getTimelineDuration(document) > 1800) errors.push("Timeline exceeds the 30-minute development limit.");
  return [...new Set(errors)];
}
