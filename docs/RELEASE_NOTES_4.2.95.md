# FLEXY AI v4.2.95 (development)

## End-to-end export verification

- Added an authenticated API integration test that registers an account, creates a project, uploads a real generated MP4, runs export preflight, starts the real background render, downloads the result, and validates the MP4 with FFprobe.
- The test uses a temporary SQLite database and isolated media/render directories.
- The test skips only when FFmpeg, FFprobe, or the `libx264` encoder is unavailable.
- Aligned backend, frontend package, visible editor label, and release contract tests at 4.2.95.

## Verification boundary

This validates the backend API upload-to-download path. It does not replace the still-pending real-browser test against a running backend. Frontend dependency installation, TypeScript checking, and the Vite production build remain pending where npm registry access is unavailable.
