import type { AudioTimelineClip, CaptionTimelineItem, VideoTimelineClip } from "./timelineGraph";

export type DialogueTrimSyncResult = {
  audioClips: AudioTimelineClip[];
  captions: CaptionTimelineItem[];
  warnings: string[];
  remappedAudioClips: number;
  remappedCaptions: number;
};

type RetainedWindow = {
  oldStart: number;
  oldEnd: number;
  newStart: number;
  sourceStart: number;
};

function mapTime(time: number, windows: RetainedWindow[]): number | null {
  const match = windows.find((window) => time >= window.oldStart - 0.0001 && time <= window.oldEnd + 0.0001);
  if (!match) return null;
  return match.newStart + Math.max(0, Math.min(match.oldEnd - match.oldStart, time - match.oldStart));
}

/**
 * Remap dialogue audio and captions after a reviewed video pause trim.
 * Only dialogue-role audio is touched. Music/effects and unrelated clips stay intact.
 * A caption spanning a removed gap is compressed to the retained interval and flagged
 * for review because text-only caption data cannot safely split its words.
 */
export function synchronizeDialogueAfterTrim(
  original: VideoTimelineClip,
  retainedClips: VideoTimelineClip[],
  audioClips: AudioTimelineClip[],
  captions: CaptionTimelineItem[],
): DialogueTrimSyncResult {
  const windows: RetainedWindow[] = retainedClips
    .filter((clip) => clip.duration > 0)
    .map((clip) => ({
      oldStart: original.timelineStart + (clip.sourceStart - original.sourceStart),
      oldEnd: original.timelineStart + (clip.sourceStart - original.sourceStart) + clip.duration,
      newStart: clip.timelineStart,
      sourceStart: clip.sourceStart,
    }))
    .sort((a, b) => a.oldStart - b.oldStart);

  if (!windows.length) return { audioClips: [...audioClips], captions: [...captions], warnings: [], remappedAudioClips: 0, remappedCaptions: 0 };

  const outputAudio: AudioTimelineClip[] = [];
  let remappedAudioClips = 0;
  for (const clip of audioClips) {
    if (clip.role !== "dialogue" || clip.mediaId !== original.mediaId) {
      outputAudio.push(clip);
      continue;
    }
    const clipEnd = clip.timelineStart + clip.duration;
    const overlaps = windows.map((window) => ({
      window,
      start: Math.max(clip.timelineStart, window.oldStart),
      end: Math.min(clipEnd, window.oldEnd),
    })).filter((part) => part.end - part.start >= 0.05);
    if (!overlaps.length) {
      outputAudio.push(clip);
      continue;
    }
    const fullyContained = overlaps.length === 1 &&
      overlaps[0].start <= clip.timelineStart + 0.0001 &&
      overlaps[0].end >= clipEnd - 0.0001 &&
      Math.abs(overlaps[0].window.newStart - overlaps[0].window.oldStart) < 0.0001;
    if (fullyContained) {
      outputAudio.push(clip);
      continue;
    }
    remappedAudioClips += 1;
    overlaps.forEach((part, index) => {
      const duration = part.end - part.start;
      const timelineStart = part.window.newStart + (part.start - part.window.oldStart);
      const sourceStart = clip.sourceStart + (part.start - clip.timelineStart);
      const fadeIn = Math.min(clip.fadeIn, duration);
      const fadeOut = Math.min(clip.fadeOut, Math.max(0, duration - fadeIn));
      const volumeKeyframes = (clip.volumeKeyframes ?? [])
        .filter((point) => point.time >= part.start - clip.timelineStart && point.time <= part.end - clip.timelineStart)
        .map((point) => ({ ...point, time: Math.max(0, Math.min(duration, point.time - (part.start - clip.timelineStart))) }));
      outputAudio.push({
        ...clip,
        id: index === 0 ? clip.id : `${clip.id}-sync-${index}-${Math.round(timelineStart * 1000)}`,
        sourceStart,
        timelineStart,
        duration,
        fadeIn,
        fadeOut,
        volumeKeyframes,
      });
    });
  }

  const outputCaptions: CaptionTimelineItem[] = [];
  const warnings: string[] = [];
  let remappedCaptions = 0;
  for (const caption of captions) {
    const start = caption.start;
    const end = caption.start + caption.duration;
    const overlapping = windows.filter((window) => end > window.oldStart && start < window.oldEnd);
    if (!overlapping.length) {
      outputCaptions.push(caption);
      continue;
    }
    const mappedStart = mapTime(start, windows);
    const mappedEnd = mapTime(end, windows);
    const first = overlapping[0];
    const last = overlapping[overlapping.length - 1];
    const clippedStart = mappedStart ?? first.newStart;
    const clippedEnd = mappedEnd ?? (last.newStart + Math.min(last.oldEnd - last.oldStart, end - last.oldStart));
    if (clippedEnd <= clippedStart + 0.03) {
      remappedCaptions += 1;
      continue;
    }
    const spansRemovedGap = overlapping.length > 1;
    const nextStart = clippedStart;
    const nextDuration = clippedEnd - clippedStart;
    if (Math.abs(nextStart - caption.start) > 0.0001 || Math.abs(nextDuration - caption.duration) > 0.0001) remappedCaptions += 1;
    outputCaptions.push({ ...caption, start: nextStart, duration: nextDuration });
    if (spansRemovedGap) warnings.push(`Caption ${caption.id} spans a removed pause. Its timing was compressed; review its text against the audio.`);
  }

  return {
    audioClips: outputAudio.sort((a, b) => a.timelineStart - b.timelineStart),
    captions: outputCaptions.sort((a, b) => a.start - b.start),
    warnings: [...new Set(warnings)],
    remappedAudioClips,
    remappedCaptions,
  };
}
