# FLEXY AI 4.5.1: Speaker-aware speech intelligence

## Added
- Optional provider-backed speaker diarization through `FLEXY_SPEECH_DIARIZATION_MODEL`.
- Diarized transcription requests ask for `diarized_json` and preserve provider `speaker_id` values.
- Transcript analysis reports speaker count, per-label segment counts, estimated speech duration, word counts, and speaker-turn changes.
- Subtitle export can optionally include speaker labels in SRT or WebVTT voice-cue syntax. The default export remains unchanged.
- Speech caption cue types preserve optional speaker IDs for downstream UI rendering.

## Important behavior
- Diarization is opt-in. Without `FLEXY_SPEECH_DIARIZATION_MODEL`, standard transcription behavior is unchanged.
- The configured provider must support diarized JSON and return speaker labels. FLEXY AI does not invent labels or infer real-world identities.
- Speaker labels from separate long-media chunks are namespaced per chunk because the provider may reset local speaker IDs between requests. Cross-chunk identity matching is not claimed.
- Speaker labels are provider-generated labels, not verified identities. Review them before publication.

## Verification
- Speech unit tests include diarization parsing, speaker analytics, provider request contract, and optional speaker-labelled subtitle export.
- Python compilation and the complete backend suite are run for this build.
- Frontend production build status is reported separately because dependencies may not be available in the build environment.
