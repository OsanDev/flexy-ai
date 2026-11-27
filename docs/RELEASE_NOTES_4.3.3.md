# FLEXY AI v4.3.3 development notes

## Live audio peak monitoring
- Added real-time browser playback peak meters for Dialogue, Music, Effects, and Master.
- Audio preview now uses a Web Audio routing graph with per-clip gain, per-bus gain, and master gain stages, matching the export mixer controls.
- Clip volume automation and fade envelopes are applied during browser preview playback.
- Peak readings are sampled from analyser nodes and displayed in dBFS. The meter math is isolated and covered by deterministic tests.
- If Web Audio is unavailable, playback falls back to native media-element volume and the UI identifies that metering is unavailable rather than fabricating readings.

## Verification scope
- The previous backend/export behavior is retained.
- Frontend type checking, Vite production build, and real-browser tests remain blocked while npm registry DNS resolution is unavailable and dependencies cannot be installed.
