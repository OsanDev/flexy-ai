# FLEXY AI v4.2.92

## Frontend build readiness and export verification

- Aligned the FastAPI application version, health endpoint version, and frontend package version at `4.2.92`.
- Added a dedicated `npm run typecheck` script using the strict TypeScript project configuration.
- Changed the frontend production build to run the TypeScript check before Vite bundling.
- Updated GitHub Actions to report type-check failures separately from Vite build failures.
- Added a Node-based timeline-core smoke test covering clip positioning, duration edits, audio level edits, validation, render-graph serialization, timeline duration and invalid-command rollback.
- Added a Playwright Chromium workflow test covering sign-in, media import, timeline editing, undo/redo, autosave, render creation and MP4 download.
- Added a real FFmpeg render smoke test and FFprobe verification for generated MP4 output.

## Verification status

- Backend suite: 413 tests passed in the local environment, including a real FFmpeg MP4 render smoke test.
- Timeline editing core: compiled and exercised with Node using the TypeScript compiler.
- MP4 render: generated and verified a sample H.264 MP4 using FFmpeg and FFprobe.
- React/Vite type-check, production build and Playwright browser test: not executed locally because the pinned npm dependencies are not cached and registry DNS resolution is unavailable. GitHub Actions is configured to install the dependencies and run these checks on a network-enabled runner after the source is pushed.

## Limitations

This remains a development build. A successful sample render does not prove every codec, GPU encoder, resolution, frame rate, or user project works. The browser workflow test must pass in CI and be followed by testing against a running backend with real uploaded media before production release.
