export type ShotCandidate = {
  timestamp: number;
  description: string | null;
  objects: string[];
  actions: string[];
  editing_notes: string[];
  available: boolean;
  confidence?: number;
  visual_interest?: number;
};

export type ShotRankingOptions = {
  /** Percentage of the final score contributed by pixel-based visual evidence. */
  visualWeight?: number;
};

export type RankedShot = ShotCandidate & {
  score: number;
  semanticScore: number;
  visualScore: number | null;
  reasons: string[];
};

function clamp01(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
}

export function scoreShot(candidate: ShotCandidate, options: ShotRankingOptions = {}): RankedShot {
  if (!candidate.available) {
    return { ...candidate, score: 0, semanticScore: 0, visualScore: null, reasons: ["AI analysis unavailable"] };
  }
  const description = (candidate.description ?? "").trim();
  const objectCount = candidate.objects.filter(Boolean).length;
  const actionCount = candidate.actions.filter(Boolean).length;
  const noteCount = candidate.editing_notes.filter(Boolean).length;
  const confidence = typeof candidate.confidence === "number" ? clamp01(candidate.confidence) : 0;
  const semanticScore = Math.min(100,
    (description.length >= 35 ? 25 : description.length > 0 ? 12 : 0) +
    Math.min(4, objectCount) * 7 +
    Math.min(3, actionCount) * 8 +
    Math.min(2, noteCount) * 6 +
    confidence * 11
  );
  const hasVisualScore = typeof candidate.visual_interest === "number" && Number.isFinite(candidate.visual_interest);
  const visualScore = hasVisualScore ? clamp01(candidate.visual_interest!) * 100 : null;
  const visualWeight = Math.max(0, Math.min(100, options.visualWeight ?? 25)) / 100;
  // Missing pixel evidence never penalizes a shot or changes the semantic-only score.
  const score = visualScore === null
    ? semanticScore
    : semanticScore * (1 - visualWeight) + visualScore * visualWeight;
  const reasons: string[] = [];
  if (description.length >= 35) reasons.push("Detailed scene description");
  if (objectCount) reasons.push(`${objectCount} visible subject${objectCount === 1 ? "" : "s"}`);
  if (actionCount) reasons.push(`${actionCount} detected action${actionCount === 1 ? "" : "s"}`);
  if (noteCount) reasons.push("Has editing notes");
  if (!reasons.length) reasons.push("Limited visual detail");
  if (visualScore !== null) reasons.push(`Pixel evidence weighted ${Math.round(visualWeight * 100)}%`);
  return { ...candidate, score: Math.round(score), semanticScore: Math.round(semanticScore), visualScore: visualScore === null ? null : Math.round(visualScore), reasons };
}

export function rankShots(candidates: ShotCandidate[], options: ShotRankingOptions = {}): RankedShot[] {
  return candidates.map((candidate) => scoreShot(candidate, options))
    .sort((a, b) => b.score - a.score || a.timestamp - b.timestamp);
}
