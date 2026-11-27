# FLEXY AI 4.3.5 - Team Handoff

**Purpose:** Internal development handoff for the team. This is not a production-release declaration.

## Verified in this source workspace

- Backend test suite: `464 passed`.
- Python application compilation: passed.
- Timeline-core checks: passed.
- Focused rendering, authenticated export, subtitle export, and recovery checks: `13 passed`.
- Backend includes FastAPI APIs, account/session handling, project and media storage, render jobs, and FFmpeg rendering.
- Frontend source is React + TypeScript + Vite.

## Known blockers before team-wide use

- Frontend dependencies are not installed in this workspace.
- npm registry DNS currently fails with `EAI_AGAIN registry.npmjs.org`.
- Full TypeScript typecheck, Vite production build, and Playwright browser suite have not been run successfully here.
- Playwright's current workflow mocks `/api/**`; it is not a live backend upload-to-export acceptance test.
- Some optional AI capabilities require valid server-side provider credentials.
- The backend intentionally returns HTTP 503 for API routes not included in its fail-closed allowlist. Verify every workflow the team needs against the enabled routes before demoing it.
- No production deployment, load test, or full security review is claimed.

## Local setup

Requirements: Python 3.11+, Node.js 20+, npm, FFmpeg, and FFprobe.

### Backend

```bash
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/api/health`

For local plain-HTTP development only, set `FLEXY_COOKIE_SECURE=false` for the backend process if secure cookies prevent local session testing. Do not use that setting for HTTPS deployment.

### Frontend

In a second terminal:

```bash
cd frontend-reference/apps/web
npm install --no-audit --no-fund
npm run doctor
npm run typecheck
npm run test:timeline
npm run build
npm run dev
```

Open the Vite URL printed in the terminal. Configure `VITE_API_BASE_URL` only when the backend is not served from the same origin. The backend must trust the exact frontend origin through `FLEXY_CORS_ORIGINS`.

## Team acceptance checklist

1. Sign up / sign in / sign out in the target environment.
2. Create a project, rename it, reload, and confirm the project is still present.
3. Import representative video, audio, and image files.
4. Confirm thumbnail/preview playback and timeline placement.
5. Trim, split, move, and delete clips; verify undo/redo and autosave/recovery.
6. Try audio levels, transitions, and subtitles.
7. Export a short MP4; verify the downloaded file plays and its duration/resolution are correct.
8. Repeat with a larger representative media file and record render time and any failure.
9. Verify AI actions only if server credentials and required routes are configured.
10. Record browser, operating system, test media, errors, and screenshots for every failure.

## Release rule

Use this package for internal testing only. Do not promise 8K/60fps or 4K/120fps performance until those exact profiles have been rendered and playback-checked on the intended hardware. Do not call the app production-ready until the frontend build, browser workflow, live backend integration, security review, and deployment checks pass.
