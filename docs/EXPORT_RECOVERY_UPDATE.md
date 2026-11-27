# Export recovery update

## Change
- Added a retry action for failed, cancelled, and interrupted render jobs in the current-job panel.
- Added a retry action beside terminal failed/cancelled/interrupted items in export history.
- Retry starts a new render using the current timeline and current export settings. It does not resume a previous FFmpeg process.
- Completed exports remain available through their existing download action.

## Verification status
- Source-level edit completed.
- Full React typecheck and Vite build remain unverified because frontend dependencies are unavailable in this environment.
- Browser interaction for retry remains pending the production frontend/browser test gate.
