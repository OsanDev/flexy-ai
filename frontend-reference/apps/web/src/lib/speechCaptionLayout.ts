export type SpeechSegment = { id: string; start: number; end: number; text: string; speaker_id?: string; words?: Array<{ word: string; start: number; end: number }> };

export type SpeechCaptionCue = { start: number; end: number; text: string; wordTimed: boolean; wordTimings?: TimedWord[]; speakerId?: string };

type TimedWord = { word: string; start: number; end: number };

/**
 * Turn provider word timestamps into readable, compact caption cues.
 * If word timestamps are unavailable, preserve the provider's segment timing
 * rather than inventing word-level timing.
 */
export function buildSpeechCaptionCues(
  segments: SpeechSegment[],
  options: { maxWords?: number; maxCharacters?: number; maxDuration?: number } = {},
): SpeechCaptionCue[] {
  const maxWords = Math.max(1, Math.min(12, Math.floor(options.maxWords ?? 7)));
  const maxCharacters = Math.max(12, Math.min(80, Math.floor(options.maxCharacters ?? 42)));
  const maxDuration = Math.max(0.8, Math.min(8, options.maxDuration ?? 3.2));
  const cues: SpeechCaptionCue[] = [];

  for (const segment of segments) {
    const words: TimedWord[] = (segment.words ?? []).filter((word) =>
      typeof word.word === "string" && word.word.trim().length > 0 &&
      Number.isFinite(word.start) && Number.isFinite(word.end) && word.end > word.start,
    ).sort((a, b) => a.start - b.start);

    if (!words.length) {
      if (segment.text.trim() && Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end > segment.start) {
        cues.push({ start: segment.start, end: segment.end, text: segment.text.trim(), wordTimed: false, ...(segment.speaker_id ? { speakerId: segment.speaker_id } : {}) });
      }
      continue;
    }

    let group: TimedWord[] = [];
    const flush = () => {
      if (!group.length) return;
      const text = group.map((word) => word.word.trim()).join(" ").replace(/\s+([,.;:!?])/g, "$1");
      const start = Math.max(segment.start, group[0].start);
      const end = Math.min(segment.end, group[group.length - 1].end);
      if (text && end > start) cues.push({ start, end, text, wordTimed: true, wordTimings: group.map((word) => ({ ...word })), ...(segment.speaker_id ? { speakerId: segment.speaker_id } : {}) });
      group = [];
    };

    for (const word of words) {
      const candidate = [...group, word];
      const candidateText = candidate.map((item) => item.word.trim()).join(" ");
      const duration = word.end - (group[0]?.start ?? word.start);
      const hasSentenceStop = /[.!?]["')\]]?$/.test(group[group.length - 1]?.word.trim() ?? "");
      if (group.length && (
        candidate.length > maxWords || candidateText.length > maxCharacters ||
        duration > maxDuration || hasSentenceStop
      )) flush();
      group.push(word);
    }
    flush();
  }

  return cues.sort((a, b) => a.start - b.start || a.end - b.end);
}
