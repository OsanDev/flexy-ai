# FLEXY AI v4.4.0 — Speech Intelligence and Smart Caption Layout

## New in this milestone

- Long-media transcription uses FFprobe duration detection and FFmpeg audio-only chunks when the source exceeds the provider request-size threshold.
- Chunk timestamps and word timestamps are restored to the original media timeline before transcript analysis.
- Chunking is bounded to 12 hours per source, uses temporary files, and rejects invalid/empty chunks.
- Smart caption layout groups provider word timestamps into readable cues with configurable word, character, and duration limits.
- Sentence punctuation, word timing, and source clip boundaries are respected during cue generation/import.
- When word timing is unavailable, caption import preserves the provider segment timing rather than fabricating word-level timestamps.
- The captions panel now reports the number of smart caption cues before import.

## Validation

- Backend speech unit tests cover transcription, language validation, word timestamps, long-media chunking, timestamp restoration, and missing FFprobe handling.
- Frontend timeline checks cover word-timed cue grouping and safe fallback behavior.
- Live provider transcription requires `FLEXY_AI_API_KEY` and a configured compatible speech endpoint.
- Long-media processing requires FFmpeg and FFprobe on the backend host.

## Limitations

- This milestone does not claim speaker diarization, emotion recognition, or perfect punctuation.
- Machine-generated captions require human review before publishing.
- Full frontend production build and live upload-to-export acceptance remain separate release gates.
