# FLEXY AI 4.3.0: Audio volume automation foundations

## Added
- Optional per-audio-clip volume keyframes in the render graph.
- Strict validation for keyframe shape, time ordering, clip bounds, and gain range.
- Frame-evaluated piecewise-linear volume automation in FFmpeg exports.
- Frontend timeline graph serialization for optional audio volume keyframes.
- Backward compatibility: clips without keyframes retain their existing constant volume behavior.

## Verification
- Backend validation tests cover valid curves and malformed, out-of-range, duplicate, and unordered keyframes.
- A real FFmpeg smoke test exports an MP4 with an animated audio gain curve and verifies its AAC audio stream with FFprobe.

## Known limitations
- The selected-audio inspector exposes basic keyframe add, gain-edit, and remove controls. A graphical automation curve drawn directly over the waveform is a future UI enhancement.
- Full React typechecking and Vite production build remain blocked in this environment because DNS cannot resolve the npm registry. No placeholder React typings or fake build result are used.
- GitHub publication remains pending; this is a local development source package.

## Verification results for this source snapshot
- Backend test suite: 452 passed.
- Real FFmpeg MP4 smoke tests include the volume-keyframe export path.
- Timeline core checks include keyframe serialization and invalid-keyframe rejection.
- Strict TypeScript check of standalone `src/lib/*.ts` modules passed with a temporary local `ImportMeta.env` declaration.
- TypeScript/TSX syntax transpilation passed for 22 source files.
- Full app typecheck and Vite build were attempted but remain blocked by missing npm packages and unavailable DNS resolution for `registry.npmjs.org`.
