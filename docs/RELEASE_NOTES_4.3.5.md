# FLEXY AI v4.3.5 development notes

## Authenticated subtitle export
- Enabled the subtitle export endpoint through the backend's explicit route gate.
- Required an authenticated session and origin-checked CSRF token for subtitle export.
- Updated the browser API client to send the CSRF token with SRT/VTT export requests.
- Added API tests for unauthenticated requests, missing CSRF protection, and successful SRT/VTT exports.

## Verification
- Backend test suite includes the authenticated subtitle export tests.
- Live upload-to-MP4 and real FFmpeg smoke tests are run separately as part of the backend suite.
- Full frontend type checking, Vite production build, and Playwright browser checks remain pending while npm registry DNS is unavailable.

## Export recovery refinement
- Added retry actions for failed, cancelled, and interrupted exports.
- Retry creates a new render job using the current timeline and export settings; it does not resume an interrupted FFmpeg process.
- Added documentation in `docs/EXPORT_RECOVERY_UPDATE.md`.

## Immediate local recovery hardening
- Write project-scoped local recovery snapshots synchronously when the timeline editor emits a document change.
- Keep browser-storage failures non-fatal so cloud autosave can continue.
- Added regression contracts for immediate snapshot persistence and storage-failure handling.

## Smart timeline dialogue anchoring update

- Smart timeline drafts now anchor selected shots near supplied transcript dialogue when dialogue occurs later within a detected scene, instead of always taking the scene's opening frames.
- The selected shot remains inside its detected scene and records overlap evidence for the actual selected interval.
- Non-finite transcript timestamps and scene boundaries are ignored; non-finite target durations are rejected.
- Regression coverage includes late-in-scene dialogue anchoring and malformed non-finite timing values.
