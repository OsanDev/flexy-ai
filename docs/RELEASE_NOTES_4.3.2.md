# FLEXY AI v4.3.2 development notes

## Professional audio bus mixer
- Added independent dialogue, music, effects, and master bus gain (0-200%) and mute controls.
- Audio clips can be routed to dialogue, music, or effects buses. Existing clips infer a compatible default bus from their role.
- Render-graph validation now checks bus names, gain bounds, and mute flags.
- FFmpeg export applies clip automation, bus gain/mute, dialogue-aware music ducking by routed bus, and master gain/mute in the rendered audio path.
- The mixer intentionally does not display fabricated live peak meters. Accurate peak metering requires decoded playback analysis and is a separate follow-up.

## Verification scope
Backend validation and real FFmpeg export tests are run for this release. Frontend dependency installation, full TypeScript checking, Vite build, and browser testing remain dependent on npm registry access.
