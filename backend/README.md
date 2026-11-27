# FLEXY AI Backend

FastAPI backend for the FLEXY AI video editor. The current source package is **v4.3.5 (development)**.

## Requirements

- Python 3.11+ (CI uses Python 3.12).
- FFmpeg and FFprobe on `PATH` for media probing and MP4 rendering.

## Install and run

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

The application initializes SQLite during startup. Runtime files are written to `backend/data/`:

- `flexy.sqlite3` - user, session, project, media metadata, and render-job records.
- `media/` - uploaded source media.
- `renders/` - render outputs and temporary artifacts.

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Configuration

| Variable | Purpose |
|---|---|
| `FLEXY_CORS_ORIGINS` | Comma-separated list of trusted frontend origins. Defaults to local Vite origins. |
| `FLEXY_COOKIE_SECURE` | Secure attribute for session/CSRF cookies. Keep `true` behind HTTPS; `false` is for local HTTP development only. |
| `FLEXY_AI_API_KEY` | Optional server-side key for compatible AI provider calls. |
| `FLEXY_AI_BASE_URL` | Optional OpenAI-compatible API base URL. |
| `FLEXY_AI_MODEL` | AI Director model name. |
| `FLEXY_VISION_MODEL` | Optional vision model override. |
| `FLEXY_SPEECH_MODEL` | Speech transcription model name. |
| `FLEXY_SPEECH_DIARIZATION_MODEL` | Optional diarization model that returns `diarized_json` with `speaker_id` per segment. |

Never place provider credentials in frontend variables or commit them to source control.

## Run tests

```bash
python -m compileall -q app
python -m pytest -q -rs
```

FFmpeg and FFprobe must be installed for the real MP4 render smoke test. The GitHub Actions workflow installs them before running the suite.

## Security and availability notes

- Project and media operations use authenticated account ownership checks in the integrated routes.
- Session and CSRF cookies are used by the browser API flow.
- The application has a fail-closed API middleware. Routes not explicitly allowlisted return HTTP `503` even if their handler is present in the source. Check `app/main.py` before assuming an endpoint is available.
- Configure exact trusted origins and HTTPS-secure cookies before any shared deployment.
- This development backend has not completed a production security or operational review.

See the repository-root `README.md` for frontend setup, Docker instructions, integration limitations, and release status.
