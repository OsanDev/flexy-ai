# FLEXY AI 4.5.4 release readiness

## Verified in this package
- Backend pytest suite: 545 passed.
- Python source compilation: verified.
- Dialogue planner: groups transcript segments into dialogue beats and returns review-only boundaries for long pauses, speaker changes, and duration limits.
- Speaker metadata is used only when provider-supplied labels exist.
- ZIP archive integrity: verified after packaging.

## Not verified / limitations
- The new dialogue planner is exposed through an authenticated backend endpoint; a dedicated frontend panel is not yet connected.
- Provider-backed transcription and diarization require compatible server credentials and provider support.
- Frontend dependency installation, typecheck, production build, and live upload-to-export browser acceptance have not been verified in this environment.
- This package has not been pushed to GitHub.

## Endpoint
`POST /api/assistant/dialogue-edit-plan`

Request fields: `transcript_segments`, `pause_threshold` (0.2 to 10 seconds), and `max_block_duration` (3 to 120 seconds). All returned cut candidates are review-only; no timeline changes are applied automatically.
