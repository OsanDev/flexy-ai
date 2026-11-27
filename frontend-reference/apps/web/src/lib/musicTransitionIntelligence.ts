import type { VideoTimelineClip } from "./timelineGraph";

export type MusicTransitionProposal = {
  clipId: string;
  transition: "fade" | "crossfade";
  cutTime: number;
  beatTime: number;
  offsetSeconds: number;
  reason: string;
};

type TransitionClip = Pick<VideoTimelineClip, "id" | "timelineStart" | "duration" | "trackIndex" | "transition">;

/**
 * Suggest a transition only when an existing same-track cut is close to a
 * detected music beat. This is review-first: it never moves or trims clips.
 */
export function proposeMusicTransitions(
  clips: readonly TransitionClip[],
  beatMarkers: readonly number[],
  toleranceSeconds = 0.12,
): MusicTransitionProposal[] {
  if (!Number.isFinite(toleranceSeconds) || toleranceSeconds < 0) return [];
  const beats = [...new Set(beatMarkers.filter((beat) => Number.isFinite(beat) && beat >= 0))]
    .sort((a, b) => a - b);
  if (!beats.length) return [];

  const tracks = new Map<number, TransitionClip[]>();
  for (const clip of clips) {
    if (![clip.timelineStart, clip.duration].every(Number.isFinite) || clip.duration <= 0) continue;
    const list = tracks.get(clip.trackIndex) ?? [];
    list.push(clip);
    tracks.set(clip.trackIndex, list);
  }

  const proposals: MusicTransitionProposal[] = [];
  for (const trackClips of tracks.values()) {
    const ordered = [...trackClips].sort((a, b) => a.timelineStart - b.timelineStart);
    for (let index = 1; index < ordered.length; index += 1) {
      const previous = ordered[index - 1];
      const incoming = ordered[index];
      if (incoming.transition !== "none") continue;
      const cutTime = incoming.timelineStart;
      let nearestBeat = beats[0];
      let nearestOffset = Math.abs(cutTime - nearestBeat);
      for (const beat of beats.slice(1)) {
        const offset = Math.abs(cutTime - beat);
        if (offset < nearestOffset) {
          nearestBeat = beat;
          nearestOffset = offset;
        }
      }
      if (nearestOffset > toleranceSeconds) continue;
      const previousEnd = previous.timelineStart + previous.duration;
      const hasOverlap = previousEnd - cutTime >= 0.05;
      proposals.push({
        clipId: incoming.id,
        transition: hasOverlap ? "crossfade" : "fade",
        cutTime,
        beatTime: nearestBeat,
        offsetSeconds: Math.round(nearestOffset * 1000) / 1000,
        reason: hasOverlap
          ? `Existing overlap meets a beat within ${nearestOffset.toFixed(3)}s; crossfade is suggested.`
          : `Cut meets a beat within ${nearestOffset.toFixed(3)}s; a fade is suggested.`,
      });
    }
  }
  return proposals.sort((a, b) => a.cutTime - b.cutTime);
}
