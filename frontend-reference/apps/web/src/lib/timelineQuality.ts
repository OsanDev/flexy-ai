import type { MediaAsset } from "./mediaApi";
import type { TimelineDocument } from "./timelineGraph";

export type QualityFinding = {
  severity: "warning" | "info";
  category: "structure" | "duration" | "source" | "audio" | "captions" | "transitions";
  title: string;
  detail: string;
  clipId?: string;
};

export type TimelineQualityReport = {
  score: number;
  grade: "Excellent" | "Good" | "Needs review" | "Incomplete";
  findings: QualityFinding[];
  checks: { label: string; passed: boolean; detail: string }[];
};

/**
 * Deterministic editorial checklist based on timeline metadata.
 * It does not listen to audio, inspect semantic meaning, or verify lip-sync.
 */
export function analyzeTimelineQuality(document: TimelineDocument, assets: MediaAsset[]): TimelineQualityReport {
  const findings: QualityFinding[] = [];
  const videos = [...document.videoClips].sort((a, b) => a.timelineStart - b.timelineStart);
  const audios = [...document.audioClips];
  const captions = [...document.captions];
  const assetById = new Map(assets.map((asset) => [asset.id, asset]));
  const end = Math.max(0, ...videos.map((clip) => clip.timelineStart + clip.duration));
  if (!videos.length) findings.push({ severity: "warning", category: "structure", title: "No visual sequence", detail: "Add at least one video or image clip before export." });
  if (videos.length && videos[0].timelineStart > 0.05) findings.push({ severity: "warning", category: "structure", title: "Opening starts late", detail: `The first visual begins at ${videos[0].timelineStart.toFixed(1)}s.` });
  videos.forEach((clip) => {
    const asset = assetById.get(clip.mediaId);
    if (asset?.duration !== null && asset?.duration !== undefined && clip.sourceStart + clip.duration > asset.duration + 0.05) {
      findings.push({ severity: "warning", category: "source", title: "Source range exceeds media", detail: `${asset.filename}: selected source ends beyond its reported duration.`, clipId: clip.id });
    }
    if (clip.duration < 0.75) findings.push({ severity: "info", category: "duration", title: "Very short shot", detail: `This ${clip.duration.toFixed(2)}s shot may feel abrupt. Review it in playback.`, clipId: clip.id });
    if (clip.duration > 15) findings.push({ severity: "info", category: "duration", title: "Long shot", detail: `This ${clip.duration.toFixed(1)}s shot may benefit from a pacing review.`, clipId: clip.id });
  });
  for (let index = 1; index < videos.length; index += 1) {
    const previous = videos[index - 1], current = videos[index];
    if (previous.trackIndex !== current.trackIndex) continue;
    const delta = current.timelineStart - (previous.timelineStart + previous.duration);
    if (delta > 0.15) findings.push({ severity: "warning", category: "structure", title: "Visual gap", detail: `${delta.toFixed(1)}s gap before the next shot.`, clipId: current.id });
    if (delta < -0.15) findings.push({ severity: "info", category: "structure", title: "Overlapping shots", detail: `${Math.abs(delta).toFixed(1)}s overlap. Confirm this is intentional.`, clipId: current.id });
    if (delta >= -0.15 && delta <= 0.15 && current.transition === "none") findings.push({ severity: "info", category: "transitions", title: "Hard cut", detail: "Review whether a hard cut is the intended visual rhythm.", clipId: current.id });
  }
  const audioEnd = Math.max(0, ...audios.map((clip) => clip.timelineStart + clip.duration));
  if (videos.length && !audios.length) findings.push({ severity: "info", category: "audio", title: "No audio clips", detail: "No separate audio is placed on the timeline." });
  if (audioEnd > end + 0.15) findings.push({ severity: "warning", category: "audio", title: "Audio outlasts visuals", detail: `Audio continues ${(audioEnd - end).toFixed(1)}s beyond the last visual.` });
  if (audios.some((clip) => clip.fadeIn + clip.fadeOut > clip.duration)) findings.push({ severity: "warning", category: "audio", title: "Invalid audio fade range", detail: "At least one audio clip has combined fades longer than its duration." });
  if (videos.length && !captions.length) findings.push({ severity: "info", category: "captions", title: "No captions", detail: "Consider captions if this edit relies on spoken content." });
  captions.forEach((caption) => {
    if (caption.start + caption.duration > end + 0.15) findings.push({ severity: "warning", category: "captions", title: "Caption outlasts visuals", detail: `Caption “${caption.text.slice(0, 36)}” ends after the visual sequence.`, clipId: caption.id });
  });
  const checks = [
    { label: "Visual sequence", passed: videos.length > 0, detail: `${videos.length} visual clips` },
    { label: "Opening alignment", passed: videos.length > 0 && videos[0].timelineStart <= 0.05, detail: videos.length ? `Starts at ${videos[0].timelineStart.toFixed(1)}s` : "No opening shot" },
    { label: "Source ranges", passed: !findings.some((item) => item.category === "source"), detail: "Compared with reported media durations where available" },
    { label: "Timeline continuity", passed: !findings.some((item) => item.category === "structure" && item.severity === "warning"), detail: "Checks same-track gaps" },
    { label: "Audio ending", passed: !findings.some((item) => item.category === "audio" && item.severity === "warning"), detail: "Checks timeline duration, not sound content" },
    { label: "Caption timing", passed: !findings.some((item) => item.category === "captions" && item.severity === "warning"), detail: "Checks captions against visual end" },
  ];
  const warnings = findings.filter((item) => item.severity === "warning").length;
  const score = videos.length ? Math.max(0, 100 - warnings * 14 - findings.filter((item) => item.severity === "info").length * 3) : 0;
  return { score, grade: !videos.length ? "Incomplete" : score >= 90 ? "Excellent" : score >= 75 ? "Good" : "Needs review", findings: findings.slice(0, 30), checks };
}
