import type { MediaAsset } from "./mediaApi";
import type { TimelineDocument } from "./timelineGraph";

export type TimelineInsight = {
  kind: "info" | "warning";
  title: string;
  detail: string;
  clipId?: string;
  clipType?: "video" | "audio" | "caption";
};

export type TimelineIntelligenceReport = {
  duration: number;
  videoCount: number;
  audioCount: number;
  captionCount: number;
  visualCoverage: number;
  insights: TimelineInsight[];
  clipNotes: Array<{ id: string; name: string; start: number; end: number; track: number; transition: string }>;
};

/**
 * Metadata-only timeline analysis. It does not inspect image pixels or decode audio.
 * Reports structural timing and coverage facts from the current edit document.
 */
export function analyzeTimeline(document: TimelineDocument, assets: MediaAsset[]): TimelineIntelligenceReport {
  const assetNames = new Map(assets.map((asset) => [asset.id, asset.filename]));
  const videos = [...document.videoClips].sort((a, b) => a.timelineStart - b.timelineStart);
  const audios = [...document.audioClips].sort((a, b) => a.timelineStart - b.timelineStart);
  const duration = Math.max(
    0,
    ...videos.map((clip) => clip.timelineStart + clip.duration),
    ...audios.map((clip) => clip.timelineStart + clip.duration),
    ...document.captions.map((caption) => caption.start + caption.duration),
  );
  const insights: TimelineInsight[] = [];
  const clipNotes = videos.map((clip, index) => ({
    id: clip.id,
    name: assetNames.get(clip.mediaId) ?? clip.mediaId,
    start: clip.timelineStart,
    end: clip.timelineStart + clip.duration,
    track: clip.trackIndex,
    transition: clip.transition,
  }));

  if (!videos.length) {
    insights.push({ kind: "warning", title: "No visual clips", detail: "Add a video or image to create a visual sequence." });
  } else {
    const first = videos[0];
    if (first.timelineStart > 0.05) {
      insights.push({ kind: "warning", title: "Opening gap", detail: `The video starts ${first.timelineStart.toFixed(1)}s after the timeline begins.`, clipId: first.id, clipType: "video" });
    }
    for (let index = 1; index < videos.length; index += 1) {
      const previous = videos[index - 1];
      const current = videos[index];
      const previousEnd = previous.timelineStart + previous.duration;
      const delta = current.timelineStart - previousEnd;
      if (delta > 0.15) {
        insights.push({ kind: "warning", title: "Visual gap", detail: `${(delta).toFixed(1)}s gap before ${assetNames.get(current.mediaId) ?? current.mediaId}.`, clipId: current.id, clipType: "video" });
      } else if (delta < -0.15 && current.trackIndex === previous.trackIndex) {
        insights.push({ kind: "info", title: "Clip overlap", detail: `${Math.abs(delta).toFixed(1)}s overlap between adjacent clips on the same track.`, clipId: current.id, clipType: "video" });
      }
    }
    const visualEnd = Math.max(...videos.map((clip) => clip.timelineStart + clip.duration));
    const audioEnd = audios.length ? Math.max(...audios.map((clip) => clip.timelineStart + clip.duration)) : 0;
    if (audioEnd > visualEnd + 0.25) {
      insights.push({ kind: "warning", title: "Audio extends past video", detail: `Audio continues ${(audioEnd - visualEnd).toFixed(1)}s beyond the visual sequence.`, clipType: "audio" });
    }
    for (const caption of document.captions) {
      if (caption.start + caption.duration > visualEnd + 0.25) {
        insights.push({ kind: "warning", title: "Caption outside visual sequence", detail: `“${caption.text.slice(0, 48)}” ends after the last visual clip.`, clipId: caption.id, clipType: "caption" });
      }
    }
    if (videos.length > 1 && videos.slice(0, -1).every((clip) => clip.transition === "none")) {
      insights.push({ kind: "info", title: "No transitions configured", detail: "All non-final visual clips use hard cuts. Add fades or crossfades if that suits your edit." });
    }
  }

  const covered = videos.reduce((total, clip) => total + clip.duration, 0);
  const visualCoverage = duration > 0 ? Math.min(100, (covered / duration) * 100) : 0;
  if (videos.length && !audios.length) {
    insights.push({ kind: "info", title: "No audio track", detail: "The timeline has no separate audio clips." });
  }
  if (videos.length && !document.captions.length) {
    insights.push({ kind: "info", title: "No captions", detail: "No caption items are currently placed on the timeline." });
  }

  return {
    duration,
    videoCount: videos.length,
    audioCount: audios.length,
    captionCount: document.captions.length,
    visualCoverage,
    insights: insights.slice(0, 20),
    clipNotes,
  };
}
