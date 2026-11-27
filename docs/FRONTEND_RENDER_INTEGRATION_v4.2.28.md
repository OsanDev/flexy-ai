# FLEXY AI v4.2.28: Frontend Render Integration Reference

## Scope

The v4.2.27 archive contains backend source and tests only. It does not contain the React/Vite application, editor components, timeline state model, or export button. Therefore this patch adds a standalone TypeScript API client and integration guide. It does **not** claim the actual editor UI is connected.

Reference client:
`frontend-reference/apps/web/src/lib/renderApi.ts`

Copy that file into the matching frontend project and adapt its graph type to the editor's actual export graph.

## Authentication contract

The backend uses:
- `flexy_session`: HttpOnly session cookie.
- `flexy_csrf`: readable CSRF cookie.
- `X-CSRF-Token`: required for state-changing requests protected by CSRF.
- `credentials: "include"`: required for browser cookie authentication.

Do not store session tokens in localStorage or expose them to JavaScript. Do not disable CSRF checks to make requests work.

## Render API contract

| User action | Method | Endpoint | CSRF |
|---|---|---|---|
| Validate export | POST | `/api/projects/{project_id}/render-preflight` | No |
| Start export | POST | `/api/projects/{project_id}/renders` | Yes |
| Render history | GET | `/api/projects/{project_id}/renders` | No |
| Poll progress | GET | `/api/renders/{job_id}` | No |
| Cancel export | POST | `/api/renders/{job_id}/cancel` | Yes |
| Remove finished history item | DELETE | `/api/renders/{job_id}` | Yes |
| Download export | GET | `/api/renders/{job_id}/download` | No |

All API requests are owner-scoped by the backend. A 404 for another user's job is intentional and should not reveal whether that job exists.

## Recommended UI flow

1. On opening the export dialog, call `renderApi.preflight(projectId, graph)`.
2. Show validation errors before enabling the Export action.
3. On Export, call `renderApi.create(projectId, graph)` and retain the returned job ID in component state.
4. Poll `renderApi.status(jobId)` every 1-2 seconds while status is `queued`, `processing`, or `cancelling`. Stop polling on a terminal status.
5. Show `progress` as a percentage. Treat `failed`, `cancelled`, and `interrupted` as terminal states.
6. Offer Cancel only for `queued` or `processing` jobs. A cancellation request is asynchronous; continue polling until a terminal status arrives.
7. Offer Download only when status is `completed`. Use `renderApi.download(jobId)` and create a temporary object URL in the UI; revoke it after the download is initiated.
8. Offer Remove from history only for terminal jobs. The backend returns 409 if a job is not terminal.

## Error handling

- `401`: session expired or user signed out. Return to sign-in.
- `403`: origin/CSRF validation failed. Refresh session state; do not retry in a tight loop.
- `404`: project/job unavailable to this account or export file missing.
- `409`: state conflict, such as trying to remove an active render.
- `422`: invalid render graph or preflight validation issue.
- `503`: endpoint intentionally blocked or service unavailable.

## Required integration checks

- Sign in and verify `flexy_csrf` cookie is present.
- Create an export and confirm `202` plus a job ID.
- Poll status until terminal.
- Cancel a second active export and confirm it reaches `cancelled`.
- Download a completed export with cookies.
- Confirm a second account receives 404 for status, cancel, delete and download.
- Confirm cross-origin requests from an untrusted origin are rejected.

## Known limitations

- The actual frontend source was not included in the v4.2.27 input archive, so no editor component or button was modified.
- The actual render worker/FFmpeg execution has not been proven end-to-end by a browser-driven export.
- The UI must use the same graph structure accepted by `RenderRequest.graph`; this reference deliberately types it as a generic record until the real editor model is available.
- Do not deploy based on this reference alone.


## v4.2.29 UI reference component

A reusable React component is now included at:
`frontend-reference/apps/web/src/components/ExportPanel.tsx`

It provides:
- Preflight summary and warnings
- Start export action
- Progress polling and cancellation
- Current job status and error display
- Recent export history
- Authenticated MP4 download
- Removal of terminal history entries

This component is a drop-in reference. It is not wired into the actual FLEXY editor because the real React/Vite app source is not present in this archive. The project graph is passed in by the host editor through the `graph` prop. Styling classes are intentionally left to the host app's design system.


## v4.2.30 browser harness

The `frontend-reference/apps/web` directory is now a minimal Vite + React app. It includes account registration/sign-in, project ID and render graph inputs, and mounts the `ExportPanel` component. This is a standalone integration lab, not the full editing application. It still requires an existing backend, account, project and valid owned media graph.


## v4.2.31 timeline-to-render graph bridge

- `frontend-reference/apps/web/src/lib/timelineGraph.ts` defines typed video, audio and caption timeline items.
- `buildRenderGraph()` serializes the timeline to the backend field names expected by `RenderRequest.graph`.
- `validateTimelineDocument()` checks required media IDs, clip durations, time positions, track indices, audio gain/fades, captions and the 30-minute project cap.
- `TimelineComposer.tsx` provides simple video/image, audio and caption lanes, clip removal, export preset/frame-rate selection, and a generated graph preview.
- `App.tsx` mounts the composer and passes its graph directly to the export panel. Advanced JSON mode remains available.

Limitations: this is a basic timeline composer, not a full NLE. It does not yet upload/import media, support drag-and-drop trimming, waveform editing, keyframes, transitions UI, or persist timeline changes to project storage. Existing project-owned media IDs are required. The TypeScript/Vite build was not verified because npm dependency installation timed out in this environment.


## v4.2.32 media asset library

Added `mediaApi.ts` for authenticated project media listing and multipart upload, plus private preview and waveform retrieval. `AssetLibrary.tsx` imports multiple video/audio/image files, refreshes the project library, displays file metadata, video/image previews and available waveforms. `TimelineComposer.tsx` now selects owned project assets rather than requiring manually typed media IDs. The app mounts the library above the timeline composer.

Limitations: no media deletion, chunked/resumable uploads, drag-and-drop, or full browser build verification.


## v4.2.33 interactive timeline controls

`TimelineComposer.tsx` now supports pointer-based horizontal clip movement, left/right trim handles, splitting at a clickable playhead, per-item deletion, zoom, and independently rendered video/audio tracks. Audio timeline items now carry `trackIndex`, serialize it as `track_index`, and validate the supported 0-7 range. Captions can also be moved, trimmed and split.

The current interaction layer is a basic timeline foundation. It does not yet provide frame-accurate snapping, undo/redo, keyboard shortcuts, playback preview, persistent project timeline saves, or real browser/device validation.


## v4.2.34 playback preview foundation

Added `PlaybackPreview.tsx` to the timeline composer. It selects the highest-index active video clip at the playhead, loads video/image media from the authenticated media endpoint, maps timeline time to source time, displays active captions, and exposes play/pause, restart, mute and seek controls. Audio elements are synchronized to their timeline offsets while playback is active. This is a first browser-preview layer, not a frame-accurate playback engine; verify authenticated media range requests and audio synchronization in a running browser before relying on it for client work.


## v4.2.35 editing experience upgrade

Added an in-memory 50-state undo/redo history to timeline document edits, with Ctrl/Cmd+Z, Ctrl/Cmd+Y and Ctrl/Cmd+Shift+Z. Arrow keys and on-screen buttons step the playhead by one project frame. Playback preview now offers 0.25× through 2× speed applied to video and audio elements. Audio clips expose fade-in/fade-out fields, which are validated and serialized through the existing render graph; preview audio gain follows an approximate fade envelope.


## v4.2.36 project persistence and autosave

Added a frontend project API for loading an existing owner-scoped project and saving the project payload with `expected_revision`. The backend project-read route now requires the authenticated user and resolves through `get_project_for_owner`; the fail-closed middleware explicitly permits this authenticated GET route. Timeline state is persisted in the existing project JSON under `timeline_document`, preserving other project properties. The browser loads the timeline when a project ID is connected and debounces autosaves by 1.2 seconds. Save statuses and revision conflicts are surfaced to the user. A changed document during an in-flight save schedules another save attempt.


## v4.2.37 project dashboard and management

Added `ProjectDashboard.tsx` with account-scoped project listing, create, name search, open, rename, duplicate and delete actions. New projects receive an empty timeline document so the v4.2.36 persistence workflow can load them immediately. Duplicate media references are remapped to copied media IDs. The duplicate API now requires the authenticated account and the storage layer verifies the source owner and writes the same owner ID onto the copy. Delete uses a confirmation prompt and relies on the backend's active-export protection. Project cards currently use a branded placeholder instead of a generated thumbnail.
