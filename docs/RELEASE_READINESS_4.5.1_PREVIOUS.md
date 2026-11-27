# FLEXY AI 4.5.1 release readiness

## Implemented
- Optional provider-backed speech diarization via `FLEXY_SPEECH_DIARIZATION_MODEL`.
- Provider speaker labels retained on normalized transcript segments.
- Per-speaker segment counts, estimated speech duration, word counts, and speaker-turn changes.
- Optional speaker-labelled SRT and WebVTT export.
- Speaker IDs carried through speech caption cue generation.
- Chunk-local speaker IDs are namespaced across long-media chunks; cross-chunk identity is not inferred.

## Verification
- Backend test suite: 539 passed.
- Python application modules compile.
- Frontend Smart Timeline and timeline-core checks passed.
- Frontend typecheck/build not completed: frontend dependencies are absent (`react` and its type declarations cannot be resolved).

## Configuration
- Standard transcription: set `FLEXY_AI_API_KEY`; configure `FLEXY_AI_BASE_URL` and `FLEXY_SPEECH_MODEL` as needed.
- Speaker diarization: additionally set `FLEXY_SPEECH_DIARIZATION_MODEL` to a model supported by the configured provider that returns `diarized_json` with segment-level `speaker_id` values.
- Keep all provider credentials on the backend. Diarization is opt-in and never fabricates speaker labels.

## Not claimed
- No verified real-world identity recognition.
- No automatic removal of pauses or filler words.
- No production frontend build or live-provider acceptance test in this environment.
