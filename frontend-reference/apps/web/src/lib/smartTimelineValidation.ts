export interface SmartTimelineValidationAsset {
  id: string;
  type: "video" | "audio" | "image";
  duration?: number | null;
}

export interface SmartTimelineValidationResult {
  valid: boolean;
  errors: string[];
}

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

/** Validate an untrusted Smart Timeline response before it can mutate the editor. */
export function validateSmartTimelineDraft(
  draft: unknown,
  assets: SmartTimelineValidationAsset[],
  targetDuration: number,
): SmartTimelineValidationResult {
  const errors: string[] = [];
  if (!draft || typeof draft !== "object") return { valid: false, errors: ["Draft response is not an object."] };
  const value = draft as Record<string, unknown>;
  if (!Array.isArray(value.clips)) errors.push("Draft video clips are missing.");
  if (!Array.isArray(value.audio_clips)) errors.push("Draft audio clips are missing.");
  if (!finite(value.duration) || value.duration < 0 || value.duration > targetDuration + 0.25) {
    errors.push("Draft duration is invalid or exceeds the requested duration.");
  }
  if (!finite(targetDuration) || targetDuration < 1 || targetDuration > 600) errors.push("Requested duration is invalid.");
  const assetById = new Map(assets.map((asset) => [asset.id, asset]));

  if (Array.isArray(value.clips)) {
    let previousEnd = 0;
    value.clips.forEach((raw, index) => {
      if (!raw || typeof raw !== "object") { errors.push(`Video clip ${index + 1} is invalid.`); return; }
      const clip = raw as Record<string, unknown>;
      const asset = typeof clip.assetId === "string" ? assetById.get(clip.assetId) : undefined;
      if (!asset || asset.type !== "video") errors.push(`Video clip ${index + 1} references an unknown video asset.`);
      for (const field of ["start", "sourceStart", "duration"] as const) {
        if (!finite(clip[field])) errors.push(`Video clip ${index + 1} has an invalid ${field}.`);
      }
      if (!finite(clip.start) || !finite(clip.sourceStart) || !finite(clip.duration)) return;
      if (clip.start < 0 || clip.sourceStart < 0 || clip.duration <= 0) errors.push(`Video clip ${index + 1} has negative timing or zero duration.`);
      if (clip.start + clip.duration > targetDuration + 0.25) errors.push(`Video clip ${index + 1} exceeds the requested timeline duration.`);
      if (clip.start + 0.001 < previousEnd) errors.push(`Video clip ${index + 1} overlaps or is out of order.`);
      previousEnd = clip.start + clip.duration;
      if (asset && finite(asset.duration) && clip.sourceStart + clip.duration > asset.duration + 0.25) {
        errors.push(`Video clip ${index + 1} exceeds its source media duration.`);
      }
    });
  }

  if (Array.isArray(value.audio_clips)) {
    value.audio_clips.forEach((raw, index) => {
      if (!raw || typeof raw !== "object") { errors.push(`Audio clip ${index + 1} is invalid.`); return; }
      const clip = raw as Record<string, unknown>;
      const asset = typeof clip.assetId === "string" ? assetById.get(clip.assetId) : undefined;
      if (!asset || asset.type !== "audio") errors.push(`Audio clip ${index + 1} references an unknown audio asset.`);
      for (const field of ["start", "sourceStart", "duration", "volume"] as const) {
        if (!finite(clip[field])) errors.push(`Audio clip ${index + 1} has an invalid ${field}.`);
      }
      if (!finite(clip.start) || !finite(clip.sourceStart) || !finite(clip.duration) || !finite(clip.volume)) return;
      if (clip.start < 0 || clip.sourceStart < 0 || clip.duration <= 0 || clip.volume < 0 || clip.volume > 2) {
        errors.push(`Audio clip ${index + 1} has out-of-range timing or volume.`);
      }
      if (clip.start + clip.duration > targetDuration + 0.25) errors.push(`Audio clip ${index + 1} exceeds the requested timeline duration.`);
      if (asset && finite(asset.duration) && clip.sourceStart + clip.duration > asset.duration + 0.25) {
        errors.push(`Audio clip ${index + 1} exceeds its source media duration.`);
      }
    });
  }
  return { valid: errors.length === 0, errors };
}
