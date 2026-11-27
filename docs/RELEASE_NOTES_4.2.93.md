# FLEXY AI v4.2.93 (development)

## CI and release verification improvements

- Aligned backend API and frontend package versions at 4.2.93.
- Added manual workflow dispatch and per-ref concurrency cancellation to avoid wasting runner time on superseded commits.
- CI installs FFmpeg explicitly and runs the real renderer smoke test with FFprobe validation as part of the backend suite.
- Frontend CI verifies installed top-level dependency versions, runs strict TypeScript checking and timeline-core tests, builds the production bundle, then runs the Playwright browser workflow.
- CI retains the production `dist` bundle on success and Playwright diagnostics on failure.
- Renamed the Playwright test description to state clearly that its API is mocked. The test verifies UI workflow and download handling, not live backend rendering.
- Replaced the stale top-level README with current setup instructions and explicit verification boundaries.

## Verification in this workspace

- Backend: 420 tests passed on this exact v4.2.93 source package.
- Real MP4: the FFmpeg/FFprobe smoke test passed locally (1 passed); it is also included in the backend suite and CI installs FFmpeg explicitly.
- Timeline core: `npm run test:timeline` passed using the globally available TypeScript compiler. Frontend typecheck failed because React and its type packages are not installed; `npm install` timed out because the npm registry was unreachable. Vite production build and Playwright were not run locally.
- Browser test: mocked API workflow only; live-backend browser integration remains outstanding.

## Release gate

Do not mark this build production-ready until GitHub Actions passes on the committed source and a live deployed-backend browser test completes real media upload, timeline editing, render completion and MP4 playback.
