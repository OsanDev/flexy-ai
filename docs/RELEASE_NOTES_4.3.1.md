# FLEXY AI 4.3.1

## Visual audio automation curve

- Added a dedicated volume automation curve preview to the selected audio clip inspector.
- Added per-point time and gain controls, removal controls, and playhead gain readout.
- The curve displays gain from 0× to 2× and follows the playhead relative to the selected clip.
- Added pure helpers to normalize automation points, clamp gain and time, sort points, resolve duplicate timestamps, and calculate piecewise-linear gain.
- Preserved the existing constant-volume fallback when a clip has no keyframes.

## Verification

- Backend suite: 452 passed.
- Timeline core checks: passed, including automation normalization and interpolation.
- Python compilation: pending release packaging check.
- Full React typecheck and Vite build remain blocked because npm registry DNS lookup for registry.npmjs.org returns EAI_AGAIN in this environment. No dependency stubs were added.

## Environment limitation

A fresh `npm install --no-audit --no-fund --fetch-retries=0 --fetch-timeout=15000` attempt failed with `EAI_AGAIN` while resolving `registry.npmjs.org`. Running `npm run typecheck` therefore reports missing `react`, `react-dom`, and `react/jsx-runtime` packages/types; the resulting JSX and implicit-any diagnostics cascade from those missing types. `npm run build` cannot proceed until the local dependencies are installed. TypeScript transpile-only syntax validation passed for all 24 non-declaration TS/TSX source files; this is not a substitute for full typechecking.
