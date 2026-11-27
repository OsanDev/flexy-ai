# FLEXY AI 4.3.5 Release Readiness

Last checked: 2026-11-27

## Verified in this environment

- Backend test suite: **462 passed** (`pytest -q backend/tests`).
- Timeline core checks: **passed**, including move, trim/duration, audio level, graph serialization, configurable ducking, volume automation, bus routing, mixer serialization, peak dBFS conversion, meter scaling, and invalid-command rollback.
- Frontend environment diagnostic runs successfully and correctly identifies missing prerequisites.
- Node.js: v22.16.0; npm: 10.9.2.

## Release blockers

The frontend dependencies are not installed:

- react 18.3.1
- react-dom 18.3.1
- @types/react 18.3.18
- @types/react-dom 18.3.5
- @vitejs/plugin-react 4.3.4
- typescript 5.7.3 (a global TypeScript installation is available, but the project-local dependency is absent)
- vite 5.4.14
- @playwright/test 1.56.1

A direct request to `https://registry.npmjs.org/react` failed with `curl: (6) Could not resolve host: registry.npmjs.org`. The frontend environment diagnostic reports registry DNS unavailable (`EAI_AGAIN`). No usable npm package cache or project lockfile was found, so an offline install cannot currently be completed.

Consequences:

- Full project TypeScript typecheck: **not run successfully**.
- Vite production build: **not run**.
- Production frontend served in Chromium: **not verified**.
- Real browser media upload/edit/playback/export workflow: **not verified**.

## Commands to run when npm registry access is restored

From `frontend-reference/apps/web`:

```bash
npm install --no-audit --no-fund
npm run typecheck
npm run build
npm run test:timeline
npm run test:e2e
```

Then serve the built app with the project's deployment configuration and verify authentication, media upload, timeline edits, playback, audio routing, and MP4 export against a running backend.

## Release decision

**Not production-ready yet.** Do not mark v4.3.5 as a completed production release until dependency installation, typechecking, Vite build, and real-browser workflow checks all pass. No source-code or application-version bump is made by this readiness report.
