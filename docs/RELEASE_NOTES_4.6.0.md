# FLEXY AI 4.6.0: Integrated Local-Run Release Candidate

## Release packaging
- Added one-command local launch scripts for macOS/Linux and Windows PowerShell.
- Added example backend and frontend environment files with safe local-only defaults.
- Added Docker Compose for a local single-instance stack: FastAPI + FFmpeg backend, Nginx-served Vite frontend, API reverse proxy, and persistent data volume.
- Added frontend container build and Nginx SPA/API proxy configuration.
- Updated release identity to 4.6.0 across frontend and backend metadata.

## Integrated dialogue workflow
- Preserved v4.5.6 dialogue trim synchronization: reviewed video pause trims remap matching dialogue audio and captions in the same undoable timeline update.
- Music/effects remain unchanged; captions spanning removed gaps are flagged for review.

## Verification completed in this environment
- Backend pytest suite: 556 passed.
- Python backend compilation: passed.
- Timeline-core TypeScript compilation and tests: passed.
- FFmpeg and FFprobe are available in this environment; the backend suite includes an authenticated upload-to-MP4-download integration test.
- ZIP archive integrity checked after packaging.

## Verification not completed
- Full React-aware TypeScript check and Vite production build could not run because npm registry access timed out and React dependencies were not installed.
- Playwright browser workflow was not run.
- Docker image/Compose startup was not run in this environment.
- No real AI provider key was supplied, so provider-backed AI, transcription, vision, and diarization calls were not live-tested.
- No public deployment, production security review, load test, or external HTTPS configuration was performed.

## Intended use
This release is a local-run/team-evaluation candidate, not a public production release. The account flow currently lacks email verification, password reset, and abuse/rate-limit controls. Use the documented local setup only until those production gates are completed.
