# FLEXY AI v4.3.4 development notes

## Audio routing reliability
- Audio clip routing changes now reconnect the live Web Audio gain node to the selected Dialogue, Music, or Effects bus during playback.
- Removed audio clips now disconnect their Web Audio nodes so stale sources do not remain attached to the mixer graph.
- Existing clip gain, fade, automation, bus gain, mute, and master processing remain in the preview and export paths.

## Verification
- Backend test suite and timeline-core checks pass.
- TypeScript/TSX files pass syntax transpilation.
- Full React-aware TypeScript type checking, Vite production build, and real-browser testing remain blocked because npm package registry DNS is unavailable in this environment.
