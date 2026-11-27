# FLEXY AI — Team Demo Handoff

**Package:** 4.3.5 development  
**Purpose:** Internal engineering/product walkthrough, not a public release.

## Suggested 8–10 minute walkthrough

1. **Product direction (1 min):** FLEXY AI is an AI-assisted editor where AI proposes changes and the creator keeps an editable timeline.
2. **Editor foundation (2 min):** Show imported assets, multi-track timeline, clip editing, preview, and the existing export workflow in the local app if dependencies are installed.
3. **Smart Timeline (2 min):** Show Balanced/Dynamic/Calm styles, target duration, min/max shot duration, ranking influence, draft review, and accept/discard. Emphasize that a generated draft is reviewed before it replaces the video sequence.
4. **Visual evidence (1 min):** Explain scene-level pixel measurements and representative-frame sampling. These are image statistics, not semantic object/person recognition.
5. **Music intelligence (2 min):** Analyze an audio/video asset, review candidate beat timestamps and BPM confidence, then show the projected markers across timeline tracks. Demonstrate Magnetic snap against candidate beat positions and use the markers in a Smart Timeline draft. Explain that onset-based markers are candidates and should be reviewed; they are not guaranteed musical downbeats.
6. **Close (1 min):** Show current test status and the remaining release gates below.

## Local startup

### Backend

From the repository root:

```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
pip install pytest
FLEXY_COOKIE_SECURE=false uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check in another terminal:

```bash
curl http://127.0.0.1:8000/api/health
```

FFmpeg and FFprobe must be installed and available on PATH for media analysis/rendering.

### Frontend

In another terminal:

```bash
cd frontend-reference/apps/web
npm install --no-audit --no-fund
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). For a separate backend origin, create `.env.local` with:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend must trust the frontend origin in `FLEXY_CORS_ORIGINS`. For local development, the default origins include localhost and 127.0.0.1 on port 5173.

## Verified in this handoff workspace

- Backend: `python -m compileall -q app` passed.
- Backend pytest: **527 passed**.
- Frontend standalone timeline checks: passed. This covers timeline-core operations, audio controls/mixing, validation, graph serialization, upload validation, command rollback, and Smart Timeline API/draft-safety contracts.
- Frontend environment diagnostic: Node v22.16.0 and npm 10.9.2 detected, but all eight declared frontend packages are missing. npm registry DNS returned `EAI_AGAIN`.

## Important demo caveats

- A successful standalone timeline test is not a successful React production build.
- The full Vite/TypeScript build is **not verified** in this workspace.
- Existing Playwright workflow uses mocked API responses; it is not proof of a live authenticated upload-to-export journey.
- Real browser upload → edit → preview → MP4 download has not been certified end-to-end.
- Android project/APK and physical-device validation are not complete.
- Provider-backed AI features require server-side credentials and only supported routes are available; do not present optional provider features as active unless configured and demonstrated live.
- Beat detection is lightweight FFmpeg-decoded signal/onset analysis. Treat timestamps as candidates and review them against the music.
- Visual interest is pixel-statistics-based, not semantic vision.
- Do not use production media, credentials, or a public deployment for this internal demo.

## Release gates still open

1. Restore frontend dependencies from a reachable trusted npm registry/cache; create and commit a lockfile.
2. Pass React TypeScript check and Vite production build.
3. Run a live authenticated browser test using real media, then verify the exported MP4 with FFprobe.
4. Complete auth/CSRF/ownership, upload, storage, worker isolation, rate-limit, backup, monitoring, accessibility, and deployment reviews.
5. Package Android with Capacitor, build APK/AAB, and test installation, permissions, editing and export on physical devices.

**Status:** Suitable as an internal engineering walkthrough only after the local environment starts successfully. Not release-ready.
