# FLEXY AI 4.2.87 - Project-safe autosave

## Changes

- Autosave is now gated by the identity of the project that has actually finished loading.
- A project ID change cannot cause the previous project's timeline document to be submitted to the newly selected project while its load is pending.
- Autosave requests are tracked per project, so a pending save for one project does not block edits in another project.
- Late success or failure responses from a project that is no longer active no longer overwrite the active project's save status or revision state.
- A newer edit made while a save is in flight schedules a follow-up save for that same project.

## Verification

Run the backend suite with `python -m pytest -q -p no:cacheprovider` from `backend`.
Run the web production build with `npm install && npm run build` from `frontend-reference/apps/web`.

This release is still a development integration harness. A successful backend suite does not replace browser-based editing and export verification.
