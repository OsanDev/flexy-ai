export interface BeatTimelineAudioClip {
  mediaId: string;
  sourceStart: number;
  duration: number;
  timelineStart: number;
}

/** Map source-relative beat candidates onto every matching timeline audio instance. */
export function projectBeatMarkers(
  beats: readonly number[],
  clips: readonly BeatTimelineAudioClip[],
  mediaId: string,
): number[] {
  const markers: number[] = [];
  for (const clip of clips) {
    if (clip.mediaId !== mediaId) continue;
    if (![clip.sourceStart, clip.duration, clip.timelineStart].every(Number.isFinite) || clip.duration < 0) continue;
    const sourceEnd = clip.sourceStart + clip.duration;
    for (const beat of beats) {
      if (!Number.isFinite(beat) || beat < clip.sourceStart || beat > sourceEnd) continue;
      const timelineTime = clip.timelineStart + (beat - clip.sourceStart);
      if (Number.isFinite(timelineTime) && timelineTime >= 0) {
        markers.push(Math.round(timelineTime * 1000) / 1000);
      }
    }
  }
  return [...new Set(markers)].sort((a, b) => a - b);
}
