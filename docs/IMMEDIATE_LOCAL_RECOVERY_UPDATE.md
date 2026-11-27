# Immediate local recovery snapshot update

## Change
- Timeline document changes now write a project-scoped local recovery snapshot immediately inside the editor change callback.
- The snapshot includes the document and an `updatedAt` timestamp.
- Snapshot writes are guarded against unavailable/full browser storage and do not prevent cloud autosave from continuing.
- Existing project-loaded and project-ID checks remain in place to avoid writing a snapshot for the wrong project.
- Cloud autosave remains the authoritative persistence path; local recovery is best-effort protection against a tab closing before the next React effect runs.

## Verification
- Backend pytest suite: 464 passed.
- Timeline core checks: passed.
- Python compilation: passed.
- Focused autosave/recovery contract checks: passed.
- Full frontend typecheck, Vite build, and browser E2E remain blocked until npm dependencies can be installed.
