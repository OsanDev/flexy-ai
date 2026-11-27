# FLEXY AI v4.2.88

## Autosave recovery improvements
- Added a browser navigation warning while the active, loaded project has unsaved timeline edits.
- Added a manual Retry save control after an autosave failure. Retrying reuses the existing serialized autosave path and current project revision rather than creating a separate write path.
- Added an accessible live region for cloud save status.
- Added source-contract tests for the navigation guard and retry control.

## Verification and limitations
- Backend tests include the frontend source-contract checks.
- The frontend package still has no lockfile. An attempted dependency installation timed out in this environment, so a full TypeScript/Vite production build and browser test are not claimed.
- The navigation warning is a browser-provided prompt; browsers control its exact wording and may suppress it in some situations.
- This remains a development build, not production approval.
