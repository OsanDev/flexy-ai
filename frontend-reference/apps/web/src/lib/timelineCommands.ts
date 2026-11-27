import { validateTimelineDocument, type TimelineDocument } from "./timelineGraph";

export type TimelineCommandPlan = {
  summary: string;
  changes: string[];
  nextDocument: TimelineDocument;
  error?: string;
};

const cloneDocument = (document: TimelineDocument): TimelineDocument => ({
  ...document,
  videoClips: document.videoClips.map((clip) => ({ ...clip })),
  audioClips: document.audioClips.map((clip) => ({ ...clip })),
  captions: document.captions.map((caption) => ({ ...caption })),
});

/**
 * Deterministic first-pass command interpreter. It deliberately supports a small,
 * transparent command vocabulary and returns a preview instead of mutating state.
 */
function planSingleTimelineCommand(document: TimelineDocument, rawCommand: string): TimelineCommandPlan {
  const command = rawCommand.trim().toLowerCase().replace(/[.!?]+$/g, "");
  const nextDocument = cloneDocument(document);
  const changes: string[] = [];
  const noChange = (error: string): TimelineCommandPlan => ({
    summary: "No edits prepared",
    changes: [],
    nextDocument,
    error,
  });

  if (!command) return noChange("Type an editing command first.");

  if (/\b(4k|uhd)\b/.test(command)) {
    nextDocument.exportPreset = "4k";
    nextDocument.width = 3840;
    nextDocument.height = 2160;
    changes.push("Set project output to 4K UHD.");
  } else if (/\b1080p\b/.test(command)) {
    nextDocument.exportPreset = "1080p";
    nextDocument.width = 1920;
    nextDocument.height = 1080;
    changes.push("Set project output to 1080p.");
  } else if (/\b720p\b/.test(command)) {
    nextDocument.exportPreset = "720p";
    nextDocument.width = 1280;
    nextDocument.height = 720;
    changes.push("Set project output to 720p.");
  }

  if (/\b(crossfade|smooth transitions?|smooth cuts?)\b/.test(command)) {
    if (!nextDocument.videoClips.length) return noChange("Add video or image clips before applying transitions.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => ({ ...clip, transition: "crossfade" }));
    changes.push(`Applied crossfade transitions to ${nextDocument.videoClips.length} video clip(s).`);
  } else if (/\b(fade transitions?|fade in and out)\b/.test(command)) {
    if (!nextDocument.videoClips.length) return noChange("Add video or image clips before applying transitions.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => ({ ...clip, transition: "fade" }));
    changes.push(`Applied fade transitions to ${nextDocument.videoClips.length} video clip(s).`);
  }

  if (/\b(cinema(tic)?|film look)\b/.test(command)) {
    if (!nextDocument.videoClips.length) return noChange("Add video or image clips before applying a cinematic edit.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => ({ ...clip, transition: "fade" }));
    changes.push("Applied a fade transition style across video clips.");
    if (nextDocument.audioClips.length) {
      nextDocument.audioClips = nextDocument.audioClips.map((clip) => ({
        ...clip,
        fadeIn: Math.min(1.2, clip.duration / 2),
        fadeOut: Math.min(1.2, clip.duration / 2),
      }));
      changes.push("Added gentle audio fades.");
    }
  }

  if (/\b(mute|silence)\s+(the\s+)?(music|audio)\b/.test(command)) {
    const music = nextDocument.audioClips.filter((clip) => clip.role === "music");
    if (!music.length) return noChange("No music clips are on the timeline yet.");
    nextDocument.audioClips = nextDocument.audioClips.map((clip) => clip.role === "music" ? { ...clip, volume: 0 } : clip);
    changes.push(`Muted ${music.length} music clip(s).`);
  } else if (/\b(increase|boost|raise|louder)\b.*\b(music|audio)\b/.test(command)) {
    const music = nextDocument.audioClips.filter((clip) => clip.role === "music");
    if (!music.length) return noChange("No music clips are on the timeline yet.");
    nextDocument.audioClips = nextDocument.audioClips.map((clip) => clip.role === "music" ? { ...clip, volume: Math.min(2, Math.round((clip.volume + 0.2) * 10) / 10) } : clip);
    changes.push(`Raised music volume on ${music.length} clip(s), up to the supported 2.0x limit.`);
  } else if (/\b(lower|reduce|decrease|quieter)\b.*\b(music|audio)\b/.test(command)) {
    const music = nextDocument.audioClips.filter((clip) => clip.role === "music");
    if (!music.length) return noChange("No music clips are on the timeline yet.");
    nextDocument.audioClips = nextDocument.audioClips.map((clip) => clip.role === "music" ? { ...clip, volume: Math.max(0, Math.round((clip.volume - 0.2) * 10) / 10) } : clip);
    changes.push(`Lowered music volume on ${music.length} clip(s).`);
  }

  if (/\b(fade music|music fade|fade the audio)\b/.test(command)) {
    const music = nextDocument.audioClips.filter((clip) => clip.role === "music");
    if (!music.length) return noChange("No music clips are on the timeline yet.");
    nextDocument.audioClips = nextDocument.audioClips.map((clip) => clip.role === "music" ? {
      ...clip, fadeIn: Math.min(1.5, clip.duration / 2), fadeOut: Math.min(1.5, clip.duration / 2),
    } : clip);
    changes.push(`Added fade-in and fade-out to ${music.length} music clip(s).`);
  }

  const trimMatch = command.match(/\btrim\s+(?:the\s+)?first\s+(\d+(?:\.\d+)?)\s+seconds?\b/);
  if (trimMatch) {
    const amount = Number(trimMatch[1]);
    const first = [...nextDocument.videoClips].sort((a, b) => a.timelineStart - b.timelineStart)[0];
    if (!first) return noChange("Add a video or image clip before trimming.");
    if (!Number.isFinite(amount) || amount <= 0 || amount >= first.duration) return noChange("The trim amount must be greater than zero and shorter than the first clip.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => clip.id === first.id
      ? { ...clip, sourceStart: clip.sourceStart + amount, timelineStart: Math.max(0, clip.timelineStart + amount), duration: clip.duration - amount }
      : clip);
    changes.push(`Trimmed ${amount}s from the beginning of the first video clip.`);
  }

  // Targeted refinements address existing clips without rebuilding the whole timeline.
  const moveMatch = command.match(/\b(?:move|shift|reposition)\s+(?:the\s+)?(?:video\s+)?clip\s+(\d+)\s+(?:to|at)\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b/);
  if (moveMatch) {
    const index = Number(moveMatch[1]) - 1;
    const target = Number(moveMatch[2]);
    const ordered = [...nextDocument.videoClips].sort((a, b) => a.timelineStart - b.timelineStart);
    const targetClip = ordered[index];
    if (!targetClip) return noChange(`There is no video clip ${index + 1} on the timeline.`);
    if (!Number.isFinite(target) || target < 0) return noChange("The new clip position must be zero or greater.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => clip.id === targetClip.id
      ? { ...clip, timelineStart: target } : clip);
    changes.push(`Moved video clip ${index + 1} to ${target}s.`);
  }

  const durationMatch = command.match(/\b(?:set|make|change)\s+(?:the\s+)?(?:video\s+)?clip\s+(\d+)\s+duration\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b/);
  if (durationMatch) {
    const index = Number(durationMatch[1]) - 1;
    const target = Number(durationMatch[2]);
    const ordered = [...nextDocument.videoClips].sort((a, b) => a.timelineStart - b.timelineStart);
    const targetClip = ordered[index];
    if (!targetClip) return noChange(`There is no video clip ${index + 1} on the timeline.`);
    if (!Number.isFinite(target) || target <= 0) return noChange("Clip duration must be greater than zero.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => clip.id === targetClip.id
      ? { ...clip, duration: target } : clip);
    changes.push(`Set video clip ${index + 1} duration to ${target}s.`);
  }

  const volumeMatch = command.match(/\b(?:set|make|change)\s+(?:the\s+)?(?:music|audio)\s+volume\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(%|x)?(?=\s|$)/);
  if (volumeMatch) {
    const requested = Number(volumeMatch[1]);
    const target = volumeMatch[2] === "%" ? requested / 100 : requested;
    const music = nextDocument.audioClips.filter((clip) => clip.role === "music");
    if (!music.length) return noChange("There are no music clips on the timeline to adjust.");
    if (!Number.isFinite(target) || target < 0 || target > 2) return noChange("Music volume must be between 0 and 2. Use a percentage such as 40% or a value such as 0.4.");
    nextDocument.audioClips = nextDocument.audioClips.map((clip) => clip.role === "music" ? { ...clip, volume: target } : clip);
    changes.push(`Set music volume to ${Math.round(target * 100)}% on ${music.length} clip(s).`);
  }

  if (/\b(?:remove|clear|disable|turn off)\s+(?:all\s+)?(?:video\s+)?transitions?\b|\bno\s+transitions?\b/.test(command)) {
    if (!nextDocument.videoClips.length) return noChange("There are no video clips on the timeline yet.");
    nextDocument.videoClips = nextDocument.videoClips.map((clip) => ({ ...clip, transition: "none" }));
    changes.push(`Removed transitions from ${nextDocument.videoClips.length} video clip(s).`);
  }

  if (!changes.length) {
    return noChange("I couldn't match that command yet. Try: “move clip 2 to 5 seconds”, “set clip 1 duration to 3 seconds”, “set music volume to 40%”, “remove transitions”, “trim first 2 seconds”, or “export in 4K”.");
  }
  const validationErrors = validateTimelineDocument(nextDocument);
  if (validationErrors.length) return noChange(`This edit would make the timeline invalid: ${validationErrors.join(" ")}`);
  return { summary: `Prepared ${changes.length} edit${changes.length === 1 ? "" : "s"}.`, changes, nextDocument };
}

/**
 * Splits a natural-language request into ordered, atomic editing steps.
 * A failed step cancels the whole plan, so the user never applies a partial request.
 */
function splitEditingSteps(rawCommand: string): string[] {
  const normalized = rawCommand.trim()
    .replace(/\s+and\s+then\s+/gi, ";")
    .replace(/\s+then\s+/gi, ";")
    .replace(/[;\n]+/g, ";")
    // Split "A and B" only when B begins with a known editing action.
    .replace(/\s+and\s+(?=(?:move|shift|reposition|set|make|change|trim|mute|silence|increase|boost|raise|lower|reduce|decrease|fade|remove|clear|disable|turn\s+off|export|apply)\b)/gi, ";");
  return normalized.split(";").map((step) => step.trim()).filter(Boolean);
}

export function planTimelineCommand(document: TimelineDocument, rawCommand: string): TimelineCommandPlan {
  const steps = splitEditingSteps(rawCommand);
  if (!steps.length) {
    return {
      summary: "No edits prepared",
      changes: [],
      nextDocument: cloneDocument(document),
      error: "Type an editing command first.",
    };
  }
  if (steps.length > 8) {
    return {
      summary: "Request is too long",
      changes: [],
      nextDocument: cloneDocument(document),
      error: "Please split this into 8 editing steps or fewer so each change can be reviewed clearly.",
    };
  }

  let working = cloneDocument(document);
  const changes: string[] = [];
  for (let index = 0; index < steps.length; index += 1) {
    const result = planSingleTimelineCommand(working, steps[index]);
    if (result.error || !result.changes.length) {
      return {
        summary: "Multi-step plan not applied",
        changes: [],
        nextDocument: cloneDocument(document),
        error: `Step ${index + 1} (“${steps[index]}”) could not be prepared. ${result.error ?? "No supported edit was found."} No steps have been applied.`,
      };
    }
    working = result.nextDocument;
    changes.push(...result.changes.map((change) => `Step ${index + 1}: ${change}`));
  }

  const validationErrors = validateTimelineDocument(working);
  if (validationErrors.length) {
    return {
      summary: "Multi-step plan not applied",
      changes: [],
      nextDocument: cloneDocument(document),
      error: `The combined edit plan failed validation: ${validationErrors.join(" ")} No steps have been applied.`,
    };
  }
  return {
    summary: `Prepared ${steps.length} ordered step(s) with ${changes.length} edit(s).`,
    changes,
    nextDocument: working,
  };
}

