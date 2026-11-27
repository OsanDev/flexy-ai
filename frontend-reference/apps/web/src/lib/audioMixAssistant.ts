import type { AudioTimelineClip, TimelineDocument, CaptionTimelineItem } from "./timelineGraph";
import { normalizeVolumeKeyframes, volumeAtTime } from "./audioAutomation";
type AudioClipProfile = { clipId: string; averagePeak: number; hasQuietOpening: boolean; hasQuietEnding: boolean };

export type AudioMixChange = {
  clipId?: string;
  patch?: Partial<AudioTimelineClip>;
  enableDucking?: boolean;
  description: string;
};

export type AudioMixPlan = { changes: AudioMixChange[]; notes: string[] };

/** Build clip-relative gain automation around supplied caption/dialogue windows. */
export function buildDialogueDuckKeyframes(
  clip: AudioTimelineClip,
  captions: readonly CaptionTimelineItem[],
  duckGain = 0.35,
  attackSeconds = 0.12,
  releaseSeconds = 0.2,
): Array<{ time: number; volume: number }> {
  if (![clip.timelineStart, clip.duration, duckGain, attackSeconds, releaseSeconds].every(Number.isFinite) ||
      clip.duration <= 0 || duckGain < 0 || duckGain > 1 || attackSeconds < 0 || releaseSeconds < 0) return [];
  const windows = captions.flatMap((caption) => {
    if (![caption.start, caption.duration].every(Number.isFinite) || caption.duration <= 0 || !caption.text.trim()) return [];
    const start = Math.max(clip.timelineStart, caption.start);
    const end = Math.min(clip.timelineStart + clip.duration, caption.start + caption.duration);
    return end > start ? [{ start: start - clip.timelineStart, end: end - clip.timelineStart }] : [];
  }).sort((a, b) => a.start - b.start);
  if (!windows.length) return [];

  // Merge nearby speech windows so overlapping captions do not create duplicate points.
  const merged: Array<{ start: number; end: number }> = [];
  for (const window of windows) {
    const last = merged[merged.length - 1];
    if (last && window.start <= last.end + 0.04) last.end = Math.max(last.end, window.end);
    else merged.push({ ...window });
  }

  const existing = normalizeVolumeKeyframes(clip.volumeKeyframes ?? [], clip.duration);
  const generated: Array<{ time: number; volume: number }> = [];
  const duckRegions: Array<{ start: number; end: number }> = [];
  for (const window of merged) {
    const rampStart = Math.max(0, window.start - attackSeconds);
    const rampEnd = Math.min(clip.duration, window.end + releaseSeconds);
    duckRegions.push({ start: rampStart, end: rampEnd });
    const baselineAt = (time: number) => volumeAtTime(existing, time, 1);
    generated.push(
      { time: rampStart, volume: baselineAt(rampStart) },
      { time: window.start, volume: baselineAt(window.start) * duckGain },
      { time: window.end, volume: baselineAt(window.end) * duckGain },
      { time: rampEnd, volume: baselineAt(rampEnd) },
    );
  }
  const preserved = existing.filter((point) => !duckRegions.some((region) => point.time >= region.start && point.time <= region.end));
  return normalizeVolumeKeyframes([...preserved, ...generated], clip.duration);
}

/** Conservative, review-first mix suggestions based on clip roles, timing, captions and waveform summaries. */
export function recommendAudioMix(document: TimelineDocument, profiles: AudioClipProfile[]): AudioMixPlan {
  const changes: AudioMixChange[] = [];
  const notes: string[] = [];
  const profileByClip = new Map(profiles.map((profile) => [profile.clipId, profile]));
  const dialogue = document.audioClips.filter((clip) => clip.role === "dialogue");
  const music = document.audioClips.filter((clip) => clip.role === "music");
  const overlaps = (a: AudioTimelineClip, b: AudioTimelineClip) =>
    Math.min(a.timelineStart + a.duration, b.timelineStart + b.duration) - Math.max(a.timelineStart, b.timelineStart) > 0.05;
  const musicUnderDialogue = music.filter((musicClip) => dialogue.some((voiceClip) => overlaps(musicClip, voiceClip)) ||
    document.captions.some((caption) => Number.isFinite(caption.start) && Number.isFinite(caption.duration) && caption.duration > 0 &&
      Math.min(musicClip.timelineStart + musicClip.duration, caption.start + caption.duration) - Math.max(musicClip.timelineStart, caption.start) > 0.05));
  if (musicUnderDialogue.length) {
    notes.push(`${musicUnderDialogue.length} music clip(s) overlap dialogue or caption timing. Listen to confirm the balance.`);
    for (const clip of musicUnderDialogue) {
      const hasCaptionOverlap = document.captions.some((caption) => Number.isFinite(caption.start) && Number.isFinite(caption.duration) && caption.duration > 0 &&
        Math.min(clip.timelineStart + clip.duration, caption.start + caption.duration) > Math.max(clip.timelineStart, caption.start));
      if (hasCaptionOverlap) {
        const keyframes = buildDialogueDuckKeyframes(clip, document.captions);
        if (keyframes.length) {
          changes.push({ clipId: clip.id, patch: { volumeKeyframes: keyframes }, description: `Create dialogue-timed music dips for ${clip.id} using caption timing` });
        }
      } else if (!document.ducking) {
        changes.push({ enableDucking: true, description: "Enable dialogue-aware music ducking for overlapping dialogue tracks" });
      }
      if (clip.volume > 0.3 && !hasCaptionOverlap) {
        const target = 0.3;
        changes.push({ clipId: clip.id, patch: { volume: target }, description: `Lower overlapping music from ${clip.volume.toFixed(2)} to ${target.toFixed(2)}` });
      }
    }
  }
  for (const clip of document.audioClips) {
    const profile = profileByClip.get(clip.id);
    if (!profile) continue;
    if (!profile.hasQuietOpening && clip.fadeIn < 0.15 && clip.duration >= 1.5) {
      changes.push({ clipId: clip.id, patch: { fadeIn: 0.15 }, description: `Add a subtle 0.15s fade-in to ${clip.role}` });
    }
    if (!profile.hasQuietEnding && clip.fadeOut < 0.2 && clip.duration >= 1.5) {
      changes.push({ clipId: clip.id, patch: { fadeOut: 0.2 }, description: `Add a subtle 0.20s fade-out to ${clip.role}` });
    }
    if (profile.averagePeak > 0.9) {
      notes.push(`${clip.role} clip ${clip.id} has high average peak buckets. Listen for harshness or clipping before changing its level.`);
    }
  }
  if (!musicUnderDialogue.length && dialogue.length && music.length) {
    notes.push("Dialogue and music do not currently overlap on the timeline. No dialogue/music level change is proposed.");
  }
  if (!document.audioClips.length) notes.push("Add audio clips before requesting a mix recommendation.");
  if (document.captions.length && !musicUnderDialogue.length) notes.push("Caption timing is available, but no music clip overlaps those caption windows.");
  return { changes, notes };
}
