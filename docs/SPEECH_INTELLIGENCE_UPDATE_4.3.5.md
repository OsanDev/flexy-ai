# FLEXY AI 4.3.5 - Speech intelligence extension

## Added
- Transcript analysis is generated alongside provider-backed transcription.
- Reports segment count, estimated word count, available word timestamps, active transcript duration, and estimated speaking rate (words per minute).
- Flags transcript gaps of at least 0.6 seconds with timestamp ranges.
- Counts a small set of common English filler words and phrases.
- Displays the report in the caption-generation panel before captions are imported.

## Boundaries
- Metrics are derived from transcript text and timestamps, not acoustic speaker recognition.
- Filler detection is English-only and heuristic; it can misclassify context and should be reviewed.
- Pause detection uses gaps between provider transcript segments and does not prove silence in the audio.
- Speaking rate is an estimate across the transcript's active time span.
- No transcript or analysis is fabricated when the speech provider is unavailable.

## Verification
- Speech unit tests: 16 passed.
- Backend Python compilation: passed.
- Timeline-core checks: passed.
- Full backend suite: 527 passed, 2 failed due to the existing test database missing the `sessions` table in `test_global_csrf_guard.py`.
- Frontend TypeScript/Vite build remains unverified because frontend dependencies are not installed in the supplied workspace.
