# Scene Detection Resource Guard — 4.3.5

Date: 2026-11-27

## Change

FFmpeg scene detection now receives an explicit `-frames:v <max_scenes>` output limit. The API already limited the number of returned scene timestamps; this change also bounds the number of selected frames emitted through FFmpeg's `showinfo` diagnostics. This reduces avoidable stderr growth and processing work on videos with very frequent cuts.

## Validation

- `max_scenes` remains constrained to 1–2000.
- Regression tests assert the FFmpeg frame limit is passed for the default and caller-selected limits.
- Backend suite: 496 passed.
- Python compilation: passed.
- Frontend timeline-core checks: passed.

## Scope

This bounds selected-frame processing, not total video decoding time. FFmpeg still needs to decode frames to identify scene changes. The scene-analysis endpoint retains its five-minute subprocess timeout.
