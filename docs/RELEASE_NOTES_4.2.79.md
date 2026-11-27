# FLEXY AI v4.2.79 - Speech Intelligence foundation

## Added
- Speech transcription accepts an optional language hint; automatic detection remains the default.
- Transcription requests segment and word timestamp granularities from compatible OpenAI-style speech endpoints.
- Word-level timestamps returned separately by compatible providers are associated with their containing transcript segments.
- The captions workspace exposes a spoken-language selector and reports the number of returned word timestamps.
- Transcription results can be exported as SRT or WebVTT directly from the captions workspace.
- Added regression tests for multipart language/timestamp parameters, word timestamp normalization, and SRT/WebVTT formatting.

## Configuration
Set `FLEXY_AI_API_KEY` in the backend environment. Optional:
- `FLEXY_AI_BASE_URL` (defaults to `https://api.openai.com/v1`)
- `FLEXY_SPEECH_MODEL` (defaults to `whisper-1`)

The selected speech endpoint must support the OpenAI-compatible `/audio/transcriptions` request and the requested timestamp granularity. If word timestamps are not supported, segment transcription remains available.

## Verification
- Speech test module: 7 passed.
- Full backend suite: 354 passed, 27 failed in this environment. The failures are concentrated in legacy unauthenticated project/render tests and a render-preflight dependency-injection test; they are not being marked as passed.
- Frontend production build could not be verified because this source archive contains no `node_modules` or lockfile, and npm's offline cache does not contain the React dependencies. Run `npm install` then `npm run build` in `frontend-reference/apps/web` in a network-enabled development environment.

## Release status
This is an incremental development build, not a claim of production readiness. Configure a real speech provider, run the frontend build, and complete end-to-end media upload, transcription, caption import, SRT/VTT download, render, and export checks before deploying to users.
