# FLEXY AI

**FLEXY AI** is a browser-based, multi-track video-editing application in active development. The project combines a React + TypeScript + Vite editor with a Python + FastAPI backend and FFmpeg-based media processing.

> **Current package:** `4.6.0` (integrated local-run release candidate)  
> **Release status:** Ready for local setup and team evaluation after dependencies are installed; not certified for public production use. Backend and timeline tests are available, but the full frontend production build and a live browser upload-to-export workflow have not yet been verified in this environment.

> **Team walkthrough:** See [`docs/TEAM_DEMO_GUIDE_2026-11-27.md`](docs/TEAM_DEMO_GUIDE_2026-11-27.md) for a timed demo script, startup commands, verified checks, and release caveats.

## What is in the project

- Multi-track timeline editing for video, audio, and captions.
- Clip selection and editing, including positioning, trimming, source in-points, fades, and transitions.
- Timeline undo/redo, validation, and project save/recovery flows.
- Project and media-library APIs with account ownership checks.
- FFmpeg MP4 rendering, render-job status, and export download endpoints.
- Audio clip gain automation and Dialogue, Music, Effects, and Master bus mixing in preview/export paths.
- Candidate music beat analysis with timeline overlays and magnetic snapping to projected beat positions.
- Authenticated SRT/VTT subtitle export protected by session cookies and CSRF validation.
- Optional AI-assisted planning and media-analysis modules, including speech intelligence reports for speaking rate, long transcript gaps, heuristic English filler phrases, provider-backed speaker labels, and transcript-derived dialogue edit plans with review-only cut candidates. Provider-backed capabilities require server-side credentials, and some API routes remain restricted by the backend's fail-closed route gate.

The feature list describes code included in this development package. It is not a claim that every workflow has passed live-browser or production testing.

## Repository layout

```text
.
├── backend/                       # FastAPI API, storage, media pipeline, pytest suite
│   ├── app/                        # Application modules
│   ├── tests/                      # Backend tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend-reference/
│   └── apps/web/                   # React + TypeScript + Vite editor
│       ├── src/
│       ├── e2e/                    # Playwright browser workflow (mock API)
│       └── scripts/                # Timeline-core checks
├── docs/                           # Integration notes and release notes

```

## Quick start

### Option A: one-command local setup

**macOS / Linux**
```bash
./start-local.sh
```

**Windows PowerShell**
```powershell
.\\start-local.ps1
```

The launcher checks Python, Node.js, FFmpeg, and FFprobe; creates a Python virtual environment; installs backend/frontend dependencies; starts the API and editor; and prints the local editor address. The first run needs internet access for package installation.

Open `http://localhost:5173`. Create an account using a password of at least 12 characters. Local launch sets `FLEXY_COOKIE_SECURE=false` because it uses plain HTTP. Do not reuse this setting for an internet-facing deployment.

### Option B: Docker Compose

Requires Docker Desktop or Docker Engine with the Compose plugin:
```bash
docker compose up --build
```

Open `http://localhost:8080`. Uploaded media, projects, and renders persist in the `flexy_data` volume. Stop with `Ctrl+C`, then `docker compose down` (this keeps the volume). To erase local project data as well, explicitly run `docker compose down -v`.

Optional AI provider configuration can be supplied in the shell before starting Compose, for example:
```bash
export FLEXY_AI_API_KEY="your-server-side-provider-key"
docker compose up --build
```
Never put provider keys in frontend variables or commit them to source control.

## Requirements

- Python 3.11 or newer (CI currently uses Python 3.12).
- Node.js 20 or newer and npm.
- FFmpeg and FFprobe available on `PATH` for media probing and MP4 rendering.
- A modern browser for the editor.

## Run locally

### 1. Start the backend

From the repository root:

```bash
cd backend
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API initializes its SQLite database when the application starts. By default, runtime data is stored under `backend/data/`:

- `flexy.sqlite3` for accounts, sessions, projects, and render-job records.
- `media/` for uploaded media.
- `renders/` for generated exports and render artifacts.

Back up this directory before replacing or redeploying a development instance. Do not commit real user media, database files, credentials, or generated exports.

Check the API health endpoint:

```bash
curl http://127.0.0.1:8000/api/health
```

The health response reports the application version and whether FFmpeg is available. It does not verify every API route or the frontend connection.

### 2. Configure and start the frontend

In a second terminal:

```bash
cd frontend-reference/apps/web
npm install --no-audit --no-fund
```

Create `.env.local` in `frontend-reference/apps/web/` if the API is not served from the same origin:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Then start Vite:

```bash
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`.

The backend must trust the exact frontend origin. For local development, the backend defaults to `http://localhost:5173` and `http://127.0.0.1:5173`. To configure other origins, set `FLEXY_CORS_ORIGINS` on the backend to a comma-separated list of full origins, for example:

```bash
FLEXY_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Do not use wildcard origins with credentialed session cookies.

## Backend configuration

| Variable | Purpose | Default / notes |
|---|---|---|
| `FLEXY_CORS_ORIGINS` | Comma-separated trusted browser origins | Local Vite origins |
| `FLEXY_COOKIE_SECURE` | Marks session and CSRF cookies Secure | `true`; set `false` only for local plain-HTTP development |
| `FLEXY_AI_API_KEY` | Server-side key for compatible AI provider calls | Unset; optional |
| `FLEXY_AI_BASE_URL` | OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `FLEXY_AI_MODEL` | AI Director model | `gpt-4o-mini` |
| `FLEXY_VISION_MODEL` | Vision model override | Falls back to `FLEXY_AI_MODEL` |
| `FLEXY_SPEECH_MODEL` | Speech transcription model | `whisper-1` |
| `FLEXY_SPEECH_DIARIZATION_MODEL` | Optional provider-supported diarization model; enables speaker labels | Unset; disabled by default |

Keep provider keys on the backend only. Never put secrets in `VITE_*` variables, frontend source files, or committed `.env` files. AI provider features remain unavailable until a valid provider and supported route are configured.

For local HTTP development only, if secure cookies prevent the browser session from being stored, run the backend with:

```bash
FLEXY_COOKIE_SECURE=false uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use secure cookies behind HTTPS in any shared or deployed environment.

## Tests and build checks

### Backend tests

```bash
cd backend
python -m compileall -q app
python -m pytest -q -rs
```

Install FFmpeg and FFprobe before running the real MP4 render smoke test. The current working branch does not yet contain an active GitHub Actions CI workflow, so these checks must be run manually until workflow permissions and configuration are in place.

### Frontend checks

Run the dependency and registry diagnostic first. It reports missing packages and whether the configured npm registry hostname resolves:

```bash
cd frontend-reference/apps/web
npm run doctor
```

Then run the frontend checks:

```bash
npm run typecheck
npm run test:timeline
npm run build
```

`npm run build` runs the TypeScript check before Vite creates the production bundle.

### Playwright workflow

```bash
cd frontend-reference/apps/web
npx playwright install chromium
npm run test:e2e
```

**Important:** The current Playwright workflow mocks `/api/**` responses. It checks the browser UI flow, including sign-in, import interaction, timeline edits, autosave UI, and the download interaction. It is **not** a live-backend end-to-end test. It does not upload real media to a live backend or validate a real exported MP4. The backend real-render smoke test is a separate check.

## Docker backend

The backend image installs FFmpeg and runs Uvicorn as a non-root user:

```bash
docker build -t flexy-ai-backend ./backend
docker run --rm -p 8000:8000 \
  -e FLEXY_CORS_ORIGINS=http://localhost:5173 \
  -e FLEXY_COOKIE_SECURE=false \
  flexy-ai-backend
```

This is a local development example. For persistent data, mount a durable volume at `/app/data`. For deployment, use HTTPS, secure cookies, explicit trusted origins, backups, monitoring, and a reviewed secret-management process. The example intentionally does not configure a production domain or credentials.

## Current limitations and release gates

- Full React-aware TypeScript checking and the Vite production build have not been confirmed in the current development workspace because npm dependency installation was blocked by package-registry DNS/network availability.
- The Playwright workflow uses mocked API responses; a live browser test from real upload through real MP4 download is still required.
- The API uses a fail-closed route allowlist. Registered project, media, render, and assistant endpoints are enabled only when their handlers enforce authenticated ownership; unknown or unreviewed `/api/` paths return HTTP `503`. State-changing browser requests also pass the global CSRF guard, with explicit origin/CSRF checks retained on authentication and subtitle-export routes.
- Optional AI features require valid server-side provider credentials and network access.
- The project has not completed a production security, scalability, accessibility, or deployment review.

Do not expose this development build to public users or store important source media in it until the release gates above are addressed. In particular, the current account flow does not include email verification, password reset, or abuse/rate-limit controls; the SQLite storage design is intended for a single-instance evaluation setup; and the editor footer explicitly identifies this as a development harness.

## Continuous integration

`.github/workflows/ci.yml` defines GitHub Actions checks for:

1. Python compilation and the backend pytest suite, including real MP4 rendering.
2. Frontend dependency installation, TypeScript checking, timeline-core tests, and Vite production build.
3. Playwright Chromium workflow using mocked API responses.

The workflow definition is included in this source package. Its presence does not mean a GitHub Actions run has passed. Check the repository's Actions tab for an actual run result.

## Release notes

See `docs/RELEASE_NOTES_*.md`, `docs/SPEECH_INTELLIGENCE_UPDATE_4.3.5.md`, and the integration notes in `docs/` for milestone-specific implementation details and known limitations.

## Contributing / issue reports

When reporting a bug, include:

- FLEXY AI package version.
- Operating system, browser, Python, and Node.js versions.
- The exact steps to reproduce the issue.
- Relevant terminal output with API keys, cookies, tokens, and personal media paths removed.
- Whether the issue occurs with a real backend or only in the mocked Playwright workflow.

Never attach private session cookies, API keys, passwords, or media you do not have permission to share.
## Export recovery

If an export fails, is cancelled, or is interrupted, the Export panel offers a retry action. Retrying creates a **new render job** using the currently selected timeline, resolution, and frame-rate settings; it does not resume the previous FFmpeg process. Completed exports remain downloadable from export history.

