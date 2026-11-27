import type { VideoTimelineClip } from "./timelineGraph";

export type DialoguePauseBoundary = {
  previous_end: number;
  at: number;
  gap_seconds: number;
  reason: string;
};

export type DialoguePauseTrimResult = {
  clips: VideoTimelineClip[];
  changed: boolean;
  removedSeconds: number;
  removedPauses: number;
};

/**
 * Build a non-destructive ripple-inside-clip trim from reviewed long-pause
 * boundaries. A small handle is retained on both sides of each pause so the
 * edit does not cut directly against a word boundary.
 */
export function trimDialoguePauses(
  clip: VideoTimelineClip,
  boundaries: DialoguePauseBoundary[],
  handleSeconds = 0.12,
): DialoguePauseTrimResult {
  const clipStart = clip.sourceStart;
  const clipEnd = clip.sourceStart + clip.duration;
  const safeHandle = Math.max(0, Math.min(0.5, handleSeconds));
  const cuts = boundaries
    .filter((item) => item.reason === "long_pause" && Number.isFinite(item.previous_end) && Number.isFinite(item.at))
    .map((item) => ({ start: item.previous_end + safeHandle, end: item.at - safeHandle }))
    .filter((item) => item.end - item.start >= 0.2 && item.end > clipStart && item.start < clipEnd)
    .sort((a, b) => a.start - b.start);

  const merged: Array<{ start: number; end: number }> = [];
  for (const cut of cuts) {
    const start = Math.max(clipStart, cut.start);
    const end = Math.min(clipEnd, cut.end);
    if (end - start < 0.2) continue;
    const previous = merged[merged.length - 1];
    if (previous && start <= previous.end) previous.end = Math.max(previous.end, end);
    else merged.push({ start, end });
  }
  if (!merged.length) return { clips: [clip], changed: false, removedSeconds: 0, removedPauses: 0 };

  const kept: Array<{ start: number; end: number }> = [];
  let cursor = clipStart;
  for (const cut of merged) {
    if (cut.start - cursor >= 0.12) kept.push({ start: cursor, end: cut.start });
    cursor = Math.max(cursor, cut.end);
  }
  if (clipEnd - cursor >= 0.12) kept.push({ start: cursor, end: clipEnd });
  if (kept.length < 2) return { clips: [clip], changed: false, removedSeconds: 0, removedPauses: 0 };

  let timelineCursor = clip.timelineStart;
  const clips = kept.map((range, index) => {
    const duration = range.end - range.start;
    const next: VideoTimelineClip = {
      ...clip,
      id: index === 0 ? clip.id : `v-pause-trim-${clip.id}-${index}-${Math.round(range.start * 1000)}`,
      sourceStart: range.start,
      duration,
      timelineStart: timelineCursor,
      transition: index === 0 ? clip.transition : "none",
    };
    timelineCursor += duration;
    return next;
  });
  const keptDuration = kept.reduce((sum, range) => sum + range.end - range.start, 0);
  return {
    clips,
    changed: true,
    removedSeconds: Math.max(0, clip.duration - keptDuration),
    removedPauses: merged.length,
  };
}
