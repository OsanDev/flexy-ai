$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ is required." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ is required." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required." }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "FFmpeg is required." }
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { throw "FFprobe is required." }

$Python = Join-Path $RootDir "backend/.venv/Scripts/python.exe"
if (-not (Test-Path $Python)) { python -m venv backend/.venv }
& $Python -m pip install --upgrade pip
& $Python -m pip install -r backend/requirements.txt

$WebDir = Join-Path $RootDir "frontend-reference/apps/web"
if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
    Push-Location $WebDir
    try { npm install --no-audit --no-fund } finally { Pop-Location }
}

$env:FLEXY_CORS_ORIGINS = if ($env:FLEXY_CORS_ORIGINS) { $env:FLEXY_CORS_ORIGINS } else { "http://localhost:5173,http://127.0.0.1:5173" }
$env:FLEXY_COOKIE_SECURE = if ($env:FLEXY_COOKIE_SECURE) { $env:FLEXY_COOKIE_SECURE } else { "false" }
$env:VITE_API_BASE_URL = if ($env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL } else { "http://127.0.0.1:8000" }

$Backend = Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory (Join-Path $RootDir "backend") -PassThru
try {
    Write-Host "FLEXY AI API: http://127.0.0.1:8000"
    Write-Host "Starting editor at http://localhost:5173"
    Push-Location $WebDir
    npm run dev -- --host 0.0.0.0
} finally {
    Pop-Location
    if (-not $Backend.HasExited) { Stop-Process -Id $Backend.Id -Force }
}
