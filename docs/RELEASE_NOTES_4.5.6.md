# FLEXY AI 4.5.6: Dialogue Audio and Caption Synchronization

## Added
- Added a pure timeline synchronization helper for reviewed dialogue pause trims.
- Dialogue-role audio is split/remapped to retained video source windows, preserving source offsets and moving retained sections to their compacted timeline positions.
- Dialogue audio volume keyframes are filtered and retimed per retained section.
- Captions are remapped to retained timeline positions after a dialogue trim.
- Captions spanning a removed pause are retained as a single cue and explicitly flagged for editorial review because text-only caption data cannot safely split the spoken words.
- Music and effects clips are intentionally left unchanged.

## Safety and editing behavior
- This helper is non-destructive and does not apply edits automatically.
- Only dialogue-role audio is eligible for synchronization.
- Captions crossing removed gaps receive a review warning rather than silently pretending word-level alignment is known.

## Verification
- `npm run test:timeline` passes, including new dialogue-audio remapping, music preservation, caption timing, and cross-gap review-warning assertions.
- Full React production build was not run in this environment.
