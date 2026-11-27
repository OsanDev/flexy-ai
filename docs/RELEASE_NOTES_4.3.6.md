# FLEXY AI v4.3.6 development update

## Music-driven transition suggestions

- Added a review-first transition suggestion engine using projected beat markers.
- Suggestions are limited to adjacent clips on the same video track whose incoming cut is within 120 ms of a detected beat.
- Existing overlap of at least 50 ms suggests `crossfade`; otherwise the suggestion is `fade`.
- Already-transitioned clips are left unchanged.
- Invalid beat timestamps and invalid clip timing are ignored.
- Added a Timeline Composer review panel to inspect suggested cut time, nearest beat, and timing offset before applying.
- Applying suggestions changes only the existing transition field. It does not move, trim, or retime clips.

## Verification

- `npm run test:timeline`: passed, including beat projection and music-transition suggestion cases.
- Full React/TypeScript typecheck: blocked because React and its type packages are not installed in this workspace.
- Vite production build and live-browser workflow: not verified.
- This remains a development update, not a production release.
