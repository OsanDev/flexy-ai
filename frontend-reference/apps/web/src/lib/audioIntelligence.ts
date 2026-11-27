import type { AudioTimelineClip } from "./timelineGraph";
import type { WaveformData } from "./mediaApi";

export type AudioFinding = {
  severity: "warning" | "info";
  title: string;
  detail: string;
  clipId?: string;
};

export type AudioClipProfile = {
  clipId: string;
  mediaId: string;
  averagePeak: number;
  silentBuckets: number;
  bucketCount: number;
  hasQuietOpening: boolean;
  hasQuietEnding: boolean;
};

export type AudioIntelligenceReport = {
  findings: AudioFinding[];
  profiles: AudioClipProfile[];
  analyzedClips: number;
  unavailable: string[];
};

/** Analyze normalized waveform peak buckets. This is not speech recognition or a loudness meter. */
export function analyzeAudioWaveforms(
  clips: AudioTimelineClip[],
  waveforms: Record<string, WaveformData>,
): AudioIntelligenceReport {
  const findings: AudioFinding[] = [];
  const profiles: AudioClipProfile[] = [];
  const unavailable: string[] = [];
  for (const clip of clips) {
    const waveform = waveforms[clip.mediaId];
    const points = waveform?.points ?? waveform?.samples ?? waveform?.waveform ?? [];
    if (!points.length) {
      unavailable.push(clip.mediaId);
      continue;
    }
    const normalized = points.map((value) => Math.max(0, Math.min(1, Number(value) || 0)));
    const silentBuckets = normalized.filter((value) => value <= 0.025).length;
    const edgeCount = Math.max(1, Math.ceil(normalized.length * 0.08));
    const hasQuietOpening = normalized.slice(0, edgeCount).every((value) => value <= 0.04);
    const hasQuietEnding = normalized.slice(-edgeCount).every((value) => value <= 0.04);
    const averagePeak = normalized.reduce((sum, value) => sum + value, 0) / normalized.length;
    const profile = { clipId: clip.id, mediaId: clip.mediaId, averagePeak: Math.round(averagePeak * 100) / 100,
      silentBuckets, bucketCount: normalized.length, hasQuietOpening, hasQuietEnding };
    profiles.push(profile);
    if (silentBuckets / normalized.length >= 0.25) {
      findings.push({ severity: "info", title: "Quiet or silent sections", detail: `${Math.round(silentBuckets / normalized.length * 100)}% of waveform buckets are near-silent. Listen to confirm whether pauses are intentional.`, clipId: clip.id });
    }
    if (hasQuietOpening) findings.push({ severity: "info", title: "Quiet audio opening", detail: "The first sampled waveform region is very quiet. Check whether the clip needs a fade-in or a trim.", clipId: clip.id });
    if (hasQuietEnding) findings.push({ severity: "info", title: "Quiet audio ending", detail: "The final sampled waveform region is very quiet. Check whether the clip needs a fade-out or a trim.", clipId: clip.id });
    if (averagePeak >= 0.98) findings.push({ severity: "warning", title: "Very high waveform peaks", detail: "Some peak buckets approach digital full scale. Listen for clipping; this estimate is not a true loudness measurement.", clipId: clip.id });
  }
  const ordered = [...clips].sort((a, b) => a.timelineStart - b.timelineStart);
  for (let index = 0; index < ordered.length; index += 1) {
    const current = ordered[index];
    for (let nextIndex = index + 1; nextIndex < ordered.length; nextIndex += 1) {
      const next = ordered[nextIndex];
      if (next.timelineStart >= current.timelineStart + current.duration) break;
      if (current.role === "dialogue" && next.role === "music" || current.role === "music" && next.role === "dialogue") {
        findings.push({ severity: "info", title: "Dialogue and music overlap", detail: `Dialogue and music overlap for ${Math.min(current.timelineStart + current.duration, next.timelineStart + next.duration) - next.timelineStart > 0 ? (Math.min(current.timelineStart + current.duration, next.timelineStart + next.duration) - Math.max(current.timelineStart, next.timelineStart)).toFixed(1) : "some"}s. Consider listening and adjusting levels or ducking.`, clipId: current.role === "dialogue" ? next.id : current.id });
      }
    }
  }
  return { findings: findings.slice(0, 40), profiles, analyzedClips: profiles.length, unavailable };
}
