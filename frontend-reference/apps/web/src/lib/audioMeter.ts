/** Convert a sampled linear audio peak to dBFS. Silence is represented by -90 dBFS. */
export function peakToDbfs(peak: number): number {
  if (!Number.isFinite(peak) || peak <= 0) return -90;
  return Math.max(-90, Math.min(0, 20 * Math.log10(Math.min(1, peak))));
}

/** Map the visible -60..0 dBFS meter range to a 0..100 percent bar. */
export function dbfsToMeterPercent(dbfs: number): number {
  if (!Number.isFinite(dbfs)) return 0;
  return Math.max(0, Math.min(100, ((dbfs + 60) / 60) * 100));
}
