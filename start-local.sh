#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

command -v python3 >/dev/null || { echo "Python 3.11+ is required."; exit 1; }
command -v node >/dev/null || { echo "Node.js 20+ is required."; exit 1; }
command -v npm >/dev/null || { echo "npm is required."; exit 1; }
command -v ffmpeg >/dev/null || { echo "FFmpeg is required. Install it and retry."; exit 1; }
command -v ffprobe >/dev/null || { echo "FFprobe is required. Install it and retry."; exit 1; }

PYTHON_BIN="backend/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv backend/.venv
fi
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r backend/requirements.txt

if [[ ! -d "frontend-reference/apps/web/node_modules" ]]; then
  (cd frontend-reference/apps/web && npm install --no-audit --no-fund)
fi

export FLEXY_CORS_ORIGINS="${FLEXY_CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173}"
export FLEXY_COOKIE_SECURE="${FLEXY_COOKIE_SECURE:-false}"
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8000}"

(
  cd backend
  exec ../backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "FLEXY AI API: http://127.0.0.1:8000"
echo "FLEXY AI health: http://127.0.0.1:8000/api/health"
echo "Starting editor at http://localhost:5173"
cd frontend-reference/apps/web
npm run dev -- --host 0.0.0.0
