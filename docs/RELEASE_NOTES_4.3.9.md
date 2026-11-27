# FLEXY AI v4.3.9 — Long-media Speech Intelligence

Date: 2026-11-27

## Added

- Long media files above the speech provider 25 MB request limit are now converted into audio-only chunks using FFmpeg.
- Chunk size is bounded to eight-minute windows, encoded mono at 16 kHz / 48 kbps, and independently checked against the provider limit.
- Segment and word timestamps are offset back onto the original media timeline before the transcript is returned.
- Combined transcript analysis is calculated from the merged timestamped segments.
- A 12-hour safety ceiling prevents unbounded synchronous transcription requests.
- Clear setup errors are returned when FFmpeg/FFprobe is missing or extraction fails.

## Existing behavior preserved

- Provider-backed transcription remains opt-in through server-side `FLEXY_AI_API_KEY`.
- No fabricated transcript is returned when speech AI is not configured.
- Existing segment/word timestamp normalization and SRT/VTT export remain in place.

## Verification

- Long-media chunking and timestamp restoration tests added.
- Full backend test suite and frontend timeline tests must be rerun for this candidate.
- Frontend build remains dependent on npm packages being available.
