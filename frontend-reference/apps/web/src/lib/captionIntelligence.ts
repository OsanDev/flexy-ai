import type { CaptionTimelineItem, TimelineDocument } from "./timelineGraph";

export type CaptionTimingChange = {
  captionId: string;
  patch: Partial<Pick<CaptionTimelineItem, "start" | "duration">>;
  description: string;
};

export type CaptionIntelligenceReport = {
  findings: Array<{ captionId?: string; severity: "info" | "warning"; title: string; detail: string }>;
  changes: CaptionTimingChange[];
  notes: string[];
};

/**
 * Metadata-only caption review. Reading-speed thresholds are editorial heuristics,
 * not universal standards, and timing suggestions do not verify spoken-word sync.
 */
export function analyzeCaptionTiming(document: TimelineDocument): CaptionIntelligenceReport {
  const findings: CaptionIntelligenceReport["findings"] = [];
  const changes: CaptionTimingChange[] = [];
  const notes: string[] = [];
  const visualEnd = document.videoClips.reduce(
    (end, clip) => Math.max(end, clip.timelineStart + clip.duration), 0,
  );
  const ordered = [...document.captions].sort((a, b) => a.start - b.start || a.id.localeCompare(b.id));
  const proposed = new Map<string, CaptionTimelineItem>();

  for (const caption of ordered) {
    const textLength = caption.text.trim().length;
    const end = caption.start + caption.duration;
    const cps = textLength / Math.max(0.1, caption.duration);
    if (cps > 20) {
      findings.push({ captionId: caption.id, severity: "warning", title: "Fast reading speed", detail: `${cps.toFixed(1)} characters/second. Consider a longer display time.` });
      const required = textLength / 20;
      const next = ordered.find((item) => item.start >= end - 0.001 && item.id !== caption.id);
      const availableEnd = Math.min(visualEnd || Infinity, next?.start ?? Infinity);
      if (required > caption.duration && caption.start + required <= availableEnd + 0.001) {
        proposed.set(caption.id, { ...caption, duration: required });
        changes.push({ captionId: caption.id, patch: { duration: required }, description: `Extend caption to ${required.toFixed(2)}s for a maximum of 20 characters/second` });
      }
    } else if (textLength > 0 && cps < 4 && caption.duration >= 4) {
      findings.push({ captionId: caption.id, severity: "info", title: "Long display time", detail: `${cps.toFixed(1)} characters/second. Check whether this caption stays on screen longer than needed.` });
    }
    if (visualEnd > 0 && end > visualEnd + 0.05) {
      findings.push({ captionId: caption.id, severity: "warning", title: "Caption extends past the video", detail: `Ends ${ (end - visualEnd).toFixed(2) }s after the last visual clip.` });
      const safeDuration = visualEnd - caption.start;
      if (safeDuration >= 0.1 && safeDuration < caption.duration) {
        proposed.set(caption.id, { ...(proposed.get(caption.id) ?? caption), duration: safeDuration });
        changes.push({ captionId: caption.id, patch: { duration: safeDuration }, description: `Trim caption to end with the video at ${visualEnd.toFixed(2)}s` });
      }
    }
  }

  for (let index = 1; index < ordered.length; index += 1) {
    const previous = ordered[index - 1];
    const current = ordered[index];
    const previousVersion = proposed.get(previous.id) ?? previous;
    const currentVersion = proposed.get(current.id) ?? current;
    const overlap = previousVersion.start + previousVersion.duration - currentVersion.start;
    if (overlap > 0.05) {
      findings.push({ captionId: current.id, severity: "warning", title: "Caption overlap", detail: `Overlaps the previous caption by ${overlap.toFixed(2)}s.` });
      const shiftedStart = previousVersion.start + previousVersion.duration;
      if (shiftedStart + currentVersion.duration <= (visualEnd || Infinity) + 0.001) {
        const existing = changes.find((change) => change.captionId === current.id);
        if (existing) {
          existing.patch.start = shiftedStart;
          existing.description += `; move start to ${shiftedStart.toFixed(2)}s to remove overlap`;
        } else {
          changes.push({ captionId: current.id, patch: { start: shiftedStart }, description: `Move caption start to ${shiftedStart.toFixed(2)}s to remove overlap` });
        }
        proposed.set(current.id, { ...currentVersion, start: shiftedStart });
      } else {
        notes.push(`Could not safely move caption ${current.id} without extending beyond the video.`);
      }
    }
  }

  if (!ordered.length) notes.push("Add captions to run timing and reading-speed checks.");
  else notes.push("Checks use caption text and timeline metadata only. They cannot hear dialogue or verify word-level speech synchronization.");
  if (ordered.length && findings.length === 0) findings.push({ severity: "info", title: "No obvious timing issues", detail: "No overlaps, out-of-range endings or reading-speed flags were found using the current heuristics." });
  return { findings, changes, notes };
}
