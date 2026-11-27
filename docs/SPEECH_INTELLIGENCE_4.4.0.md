# Speech Intelligence — v4.4.0

## Processing flow

1. The authenticated media endpoint verifies that the asset belongs to the requesting user and project and contains an audio stream.
2. The backend validates the requested language tag and checks that speech credentials are configured.
3. Media within the provider request limit is sent directly. Larger media is inspected with FFprobe and converted into bounded mono 16 kHz audio chunks using FFmpeg.
4. Each chunk is transcribed independently. Segment and word timestamps are offset by the chunk's source start time.
5. The merged transcript is normalized and analyzed for word count, estimated speaking rate, long pauses, and a limited English filler vocabulary.
6. In the editor, word timestamps are grouped into readable caption cues. The user reviews the draft and explicitly imports it into the timeline.

## Operational requirements

- Set `FLEXY_AI_API_KEY` on the backend only. Never expose provider credentials in browser code.
- Optionally configure `FLEXY_AI_BASE_URL` and `FLEXY_SPEECH_MODEL` for an OpenAI-compatible speech endpoint.
- Install FFmpeg and FFprobe on the backend host for large-media transcription.
- Current chunk size is eight minutes; source media is limited to twelve hours per transcription request.

## Accuracy and safety notes

- Word-level cue timing is only used when the provider returns valid word timestamps.
- If word timestamps are absent, original segment timing is retained.
- Chunk-boundary words, punctuation, names, and language detection should be reviewed.
- The feature does not identify speakers.
