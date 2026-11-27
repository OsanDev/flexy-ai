# FLEXY AI 4.2.99: Configurable dialogue-aware ducking

## Added
- Added user-adjustable sidechain ducking threshold, compression ratio, attack, and release controls to the audio timeline panel.
- Serialized ducking settings into the render graph and validated all values server-side.
- Applied the validated settings to FFmpeg's sidechain compressor during MP4 rendering.
- Preserved defaults matching the previous fixed compressor behavior for older projects.

## Safety and behavior
- Ducking remains opt-in. Existing projects with `ducking: false` are unchanged.
- Settings are bounded on the server even if a client bypasses the UI.
- The controls affect rendered output only when dialogue and music tracks are both present and ducking is enabled.
- The feature does not alter source media files.

## Verification
- Backend validation tests cover defaults, bounds, invalid types, and frontend serialization contracts.
- Full backend and frontend build verification remains subject to the existing dependency-installation limitation.
