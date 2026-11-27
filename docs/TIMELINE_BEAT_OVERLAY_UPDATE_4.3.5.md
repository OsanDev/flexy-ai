# FLEXY AI 4.3.5 development update: timeline beat overlays

## Existing capability confirmed
The supplied source already included FFmpeg-based candidate beat analysis, a protected project-media endpoint, a visible beat-analysis panel, and Smart Timeline beat-duration alignment. This patch does not duplicate those systems.

## Added in this update
- Project source-relative beat timestamps onto each matching audio clip instance in the timeline.
- Account for each clip's source in-point and timeline start when calculating marker positions.
- Render subtle beat-candidate lines across video, audio, and caption track rails so editors can see cross-track timing references.
- Include projected beat positions in magnetic snap points, allowing clip edges to snap to candidate music beats when Magnetic snap is enabled.
- Keep markers informational and non-interactive; they do not modify the audio or claim perfect musical downbeats.
- Add a pure projection helper with tests for multiple clip instances, source offsets, sorting/deduplication, and invalid clip timing.

## Verification
- `npm run test:timeline`: passed, including the new beat projection checks.
- Full React TypeScript check: blocked because React and its type packages are not installed in the supplied workspace.
- Vite production build and live browser upload/edit/export workflow: not verified.

## Limitations
Beat candidates come from the existing lightweight energy-onset detector. They are not guaranteed musical downbeats. Markers appear only where the analyzed media is present on the current timeline and should be reviewed by listening.
