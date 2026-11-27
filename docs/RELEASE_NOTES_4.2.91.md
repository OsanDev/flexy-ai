# FLEXY AI v4.2.91

## Project-session guarded autosave
- Added a monotonically increasing project-session identity for each project load lifecycle.
- Project load success, failure, and completion handlers now ignore responses from an earlier project session.
- Autosave callbacks now update revision, dirty state, error state, and retry scheduling only when they belong to the currently active load session.
- Reopening the same project while a previous save is still in flight can no longer let that old response mutate the new editing session.
- In-flight saves still update the revision within the same session, even if the user makes another edit while the request is pending.

## Verification
- Added regression contracts for session identity and stale save response guards.
- Backend suite and frontend source-contract checks are run for this release.
- Full React/Vite production build remains unverified because this environment cannot reach the npm registry and the package cache does not contain the pinned React toolchain.
