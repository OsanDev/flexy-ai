export type VolumeKeyframe = { time: number; volume: number };

/** Clamp and sort automation points, keeping the last point at duplicate timestamps. */
export function normalizeVolumeKeyframes(points: VolumeKeyframe[], duration: number): VolumeKeyframe[] {
  const safeDuration = Number.isFinite(duration) ? Math.max(0, duration) : 0;
  const byTime = new Map<number, VolumeKeyframe>();
  for (const point of points) {
    if (!Number.isFinite(point.time) || !Number.isFinite(point.volume)) continue;
    const time = Math.min(safeDuration, Math.max(0, point.time));
    byTime.set(Math.round(time * 1000) / 1000, { time, volume: Math.min(2, Math.max(0, point.volume)) });
  }
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

/** Piecewise-linear gain at a clip-relative time. */
export function volumeAtTime(points: VolumeKeyframe[], time: number, fallback = 1): number {
  const ordered = [...points].filter((p) => Number.isFinite(p.time) && Number.isFinite(p.volume)).sort((a, b) => a.time - b.time);
  if (!ordered.length) return Math.min(2, Math.max(0, fallback));
  if (time <= ordered[0].time) return ordered[0].volume;
  if (time >= ordered[ordered.length - 1].time) return ordered[ordered.length - 1].volume;
  for (let index = 1; index < ordered.length; index += 1) {
    const right = ordered[index];
    const left = ordered[index - 1];
    if (time <= right.time) {
      const span = right.time - left.time;
      const progress = span <= 0 ? 1 : (time - left.time) / span;
      return left.volume + (right.volume - left.volume) * progress;
    }
  }
  return fallback;
}
