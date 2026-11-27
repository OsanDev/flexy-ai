# FLEXY AI 4.3.5 — Current Readiness Check

Date: 2026-11-27 (updated after dialogue-aware smart-timeline improvement)

## Verified in this workspace

- Backend pytest suite: **498 passed** (`python -m pytest -q -rs` from `backend/`).
- Speech transcription multipart headers use a fixed safe filename, and language tags are validated before being inserted into multipart fields. Regression tests cover header-injection payloads and valid normalized tags.
- Assistant recommendations and smart-timeline endpoints are explicitly allowlisted, require an authenticated session, and enforce CSRF checks.
- Added a route-security inventory regression test: every non-public API route is checked for an authenticated-user dependency or an explicit auth-route guard.
- Backend application compilation: **passed** (`python -m compileall -q app` from `backend/`).
- Frontend timeline-core checks: **passed** (`npm run test:timeline` from `frontend-reference/apps/web/`).
- FFmpeg is installed in this workspace (`ffmpeg 7.1.5`). Backend test suite includes real MP4 rendering tests.
- Smart timeline selection now anchors a chosen shot near supplied transcript dialogue when that dialogue occurs later within a detected scene. Evidence overlap is calculated against the actual selected interval, and non-finite timing values are rejected or ignored safely. Regression tests cover late dialogue and malformed timestamps.
- Scene detection now passes an explicit FFmpeg selected-frame cap (`-frames:v max_scenes`) in addition to limiting returned timestamps; regression tests verify both default and custom limits. This bounds selected-frame diagnostics/work, while full decode time remains governed by the existing timeout.

## Frontend dependency blocker

The frontend declares eight packages: `react`, `react-dom`, `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `typescript`, `vite`, and `@playwright/test`.

`npm run doctor` confirms all eight are missing. The configured registry is `https://registry.npmjs.org/`; DNS lookup fails with `EAI_AGAIN`. A fresh `npm install --no-audit --no-fund` did not complete in this environment. The npm cache is empty, so offline installation is not available.

The timeline-core test passes because it runs as a standalone Node script and does not require React/Vite dependencies. It does **not** substitute for a React typecheck or production build.

## Not verified / release blockers

- React-aware TypeScript typecheck.
- Vite production build.
- Playwright browser workflow. The included Playwright suite uses mocked API responses.
- Live browser workflow with real media upload, editing, playback, and MP4 download.
- Production security, deployment, accessibility, and performance review.
- Android packaging and physical-device testing. This package is a browser-based web source tree; no verified APK is included.

## Repository status

The public repository `OsanDev/flexy-ai` currently reports an empty repository: no branches and no source files. This workspace package has **not** been pushed to GitHub.

## Next actions

1. Restore npm registry DNS/network access or provide a trusted dependency mirror.
2. Install the declared frontend packages.
3. Run `npm run typecheck`, `npm run build`, and `npm run test:e2e`.
4. Run the editor against a live backend and verify real media upload → timeline edit → preview → MP4 export.
5. Review authentication, route availability, secrets, storage persistence, and deployment configuration.
6. Continue auditing CSRF protection on state-changing project/media/render routes. The route inventory confirms authentication dependencies, but CSRF is not yet proven consistently across all state-changing project/media/render routes; do not assume complete CSRF coverage.
7. Continue checking project/media ownership and upload/render resource limits.
8. Only then prepare a release candidate.

**Status: development source package, not production-ready.** Do not present it as a verified installable release.

## 2026-11-27 engineering update: visual-analysis-aware shot ranking

- Smart Timeline now consumes optional upstream per-scene `visual_interest`, `subject_presence`, and `motion_suitability` signals normalized to [0, 1].
- The ranker blends supplied visual evidence with its existing dialogue/duration score (75% existing score, 25% visual score) and exposes the contributing signals in clip evidence.
- Invalid/non-finite visual signals are ignored; finite values are clamped to [0, 1].
- This is evidence-aware deterministic ranking, not an embedded or trained computer-vision model. A separate analyzer must supply these scene signals.
- Verification: backend suite 502 passed; Python app compilation passed; frontend timeline core checks passed.
- Frontend production build, live browser upload-to-export workflow, Android APK/device validation, and production deployment review remain outstanding.

## 2026-11-27 engineering update: optional pixel-based scene scoring

- `describe_frame` now computes normalized `visual_interest` from image contrast, edge strength, and channel spread/colorfulness. The score is clamped to [0, 1] and is deterministic.
- Scene detection accepts `include_visual_scores=true` to attach `visual_interest` plus transparent pixel-evidence metadata to each detected scene. This option is capped at 50 scenes per request to bound thumbnail extraction work; ordinary scene detection remains unchanged by default.
- The score is not semantic understanding: no subject presence, object identity, action, or motion suitability is inferred from a still frame. Smart Timeline can consume the returned `visual_interest` as one optional upstream signal.
- Verification on this workspace: **504 backend tests passed**; Python application compilation passed; frontend timeline-core checks passed.
- Frontend dependency installation remains blocked by npm registry DNS/network access. Production build, live browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding.

## 2026-11-27 engineering update: storyboard consumes pixel scene scores

- The web media API now requests optional pixel visual scores when building a scene storyboard and clamps the requested scene count to the backend's 50-scene scoring limit.
- The storyboard matches each sampled AI-understood frame to the nearest detected cut (within 0.75 seconds) and carries the pixel `visual_interest` score into the shot-ranking view and AI Director's edit brief.
- The UI explicitly separates AI-detail review scores from pixel visual-interest measurements. Pixel scores describe contrast/edge/colour statistics only; they are not a measure of aesthetic quality or semantic recognition.
- Regression contract tests were updated to verify the bounded API request and the UI's transparent score labels.
- Verification: **504 backend tests passed**; Python application compilation passed; frontend timeline-core checks passed.
- React typecheck and production build remain blocked by unavailable frontend dependencies/network access. Live browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding.

## 2026-11-27 engineering update: representative in-shot visual sampling

- Optional pixel visual scoring now samples the midpoint of each detected shot interval rather than sampling the cut boundary itself; this reduces the chance of measuring a transition frame as representative of the shot.
- Each scored scene includes `visual_sample_time` so the exact sampled timestamp is inspectable. The final scene uses media duration when available; if duration is unknown or the interval is degenerate, sampling safely falls back to the scene start.
- Added regression coverage for midpoint sampling, unknown/tiny intervals, and invalid indices.
- Verification: **507 backend tests passed**; Python application compilation passed; frontend timeline-core checks passed.
- Frontend production build remains blocked by missing npm dependencies and registry DNS/network access. Live browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding.

## 2026-11-27 engineering update: visible Smart Timeline workflow

Added a Smart Timeline first-cut panel to the timeline composer. It lets an editor choose Balanced, Dynamic, or Calm style and a target duration (1–600 seconds), requests scene detection with optional pixel-based visual-interest evidence for each imported video, then submits the per-asset scene metadata to the authenticated Smart Timeline endpoint. The result is displayed as a non-destructive shot-by-shot preview with source in-points, durations, ranking scores, evidence notes, and warnings. Applying the draft creates editable timeline clips in one timeline update; discarding leaves the current timeline unchanged. Existing audio clips are retained when the generated draft contains no audio clips.

Verification in this update: backend suite 507 passed; Python compileall passed; frontend standalone timeline/API contract checks passed. The React production typecheck/build remains unverified because frontend dependencies are not installed in this workspace and package-registry access was previously unavailable. Full authenticated browser upload-to-export and Android packaging remain outstanding. This is still a development build, not release-ready.

## 2026-11-27 engineering update: transcript-aware Smart Timeline input

- Smart Timeline now forwards timestamped transcript segments when the active transcription belongs to the only imported video, making the transcript source unambiguous.
- Segment inputs are filtered for finite timestamps, positive duration, and non-empty text before submission.
- When multiple videos are present or the transcript belongs to another asset, transcript segments are deliberately omitted rather than incorrectly applying source-relative timestamps to unrelated footage.
- The Smart Timeline panel explains whether transcript-aware ranking is enabled, unavailable, or withheld due to ambiguous source media.
- Validation: backend suite 507 passed; Python app compilation passed; frontend standalone timeline/API contract checks passed. Full React typecheck/build remains blocked pending dependency restoration.

## 2026-11-27 engineering update: Smart Timeline draft validation

- Added a dedicated frontend validation boundary for Smart Timeline responses before preview and again immediately before applying a draft to the editable timeline.
- Validation rejects unknown/non-video source references, malformed or non-finite timing, negative source/timeline positions, zero-length clips, source-media overruns, timeline overruns, overlapping/out-of-order video shots, invalid audio references, and audio volume outside the supported 0–2 range.
- This treats the API response as untrusted input and prevents malformed generated edits from silently entering the timeline. Invalid drafts are rejected with an actionable editor error; the existing timeline is left unchanged.
- Added standalone regression cases for valid drafts, unknown assets, invalid timing, overlapping shots, and overlong audio.
- Verification: **507 backend tests passed**; Python application compilation passed; frontend standalone timeline/API/draft-safety checks passed.
- Attempted dependency restoration with npm, but the registry request failed with `EAI_AGAIN` resolving `registry.npmjs.org`. React typecheck and production build therefore remain blocked by unavailable dependencies/network access. Authenticated browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This remains a development build, not release-ready.

## 2026-11-27 engineering update: inline storyboard frame thumbnails

- Scene storyboard cards now fetch and display the representative source frame directly beside each scene's timestamp and AI scene notes, removing the extra click required to inspect every candidate frame.
- Thumbnail retrieval is best-effort: if a frame request fails, semantic scene notes and shot actions remain available and the card shows a clear placeholder.
- Thumbnail object URLs are revoked when a storyboard is refreshed and when the inspector unmounts to avoid accumulating browser blob URLs.
- Added regression contract tests for inline thumbnails, graceful thumbnail failure, and object-URL cleanup.
- Verification: **510 backend tests passed**; Python application compilation passed; frontend standalone timeline/API/draft-safety checks passed. React typecheck and production build remain blocked by missing installed frontend dependencies and previously unavailable npm registry access. Full authenticated browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This is a development build, not release-ready.

## 2026-11-27 engineering update: adjustable visual shot ranking

- Added a user-adjustable pixel-evidence influence control (0–100%, 5-point steps) to the visual storyboard shot review.
- Ranking now reports separate semantic-detail and pixel-evidence scores plus a blended review score.
- Pixel evidence is explicitly limited to pixel-derived visual-interest statistics; it is not presented as artistic quality or semantic understanding.
- Missing pixel evidence preserves the semantic-only score and does not penalize a shot. Unavailable semantic analysis remains unranked with a zero score.
- AI Director's recommendation prompt now receives the current blend setting and the blended/semantic evidence for each ranked shot.
- Updated contract tests for the new ranking behavior.
- Verification: backend suite 511 passed; standalone TypeScript check for `visualShotRanking.ts` passed; frontend timeline checks passed; Python compilation passed. Full React production build remains blocked by unavailable frontend dependencies and registry connectivity.

## 2026-11-27 engineering update: configurable Smart Timeline shot length

- Added an optional `max_shot_duration` request setting, validated from 0.5 to 15 seconds.
- Smart Timeline now caps each selected video shot to the requested maximum; the existing editing-style duration preference remains the default when the setting is omitted.
- Added a visible Maximum shot length control to the Smart Timeline composer, defaulting to 5 seconds.
- The request value is passed through the authenticated API and included in the generated draft response for transparency.
- Added regression tests for shot-duration caps and invalid bounds.
- Verification: backend suite 513 passed; Python compilation passed; frontend standalone timeline checks passed.
- Frontend dependency doctor still reports all eight npm packages missing and npm registry DNS unavailable (`EAI_AGAIN`); production build remains blocked and unverified.

## 2026-11-27 engineering update: configurable minimum shot length

- Added an optional `min_shot_duration` setting to the Smart Timeline API and editor, configurable from 0.5 to 10 seconds.
- The minimum cannot exceed the configured maximum. Invalid bounds are rejected before a draft is requested and by the backend.
- Candidate scenes shorter than the minimum, and a final remainder too short to meet it, are skipped rather than silently producing an excessively short shot. The draft reports how many candidates were skipped, and any uncovered target duration remains visible in the existing coverage warning.
- The default minimum is 1.5 seconds in the editor. Omitting the API field preserves the previous behavior for existing clients.
- Added regression tests for minimum-length enforcement, short-scene handling, and invalid/inconsistent limits.
- Verification: **516 backend tests passed**; Python application compilation passed; frontend standalone timeline/API contract checks passed. React typecheck and production build remain unverified because dependencies are not installed and npm registry connectivity remains unavailable. Full authenticated browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This is a development build, not release-ready.

## 2026-11-27 engineering update: evidence-led pacing distribution

- Smart Timeline now varies preferred shot duration using supplied dialogue density and optional motion-suitability evidence instead of assigning every shot the same style duration.
- Calm edits give dialogue-dense scenes more room; Dynamic edits shorten shots with higher supplied motion-suitability scores; Balanced edits use a smaller adjustment.
- Pacing factors are clamped to 0.75–1.25 and remain subject to the configured minimum and maximum shot-length controls.
- Missing motion evidence is neutral. Each clip reports its pacing factor in draft evidence, and draft reasons explain that duration was adjusted from available evidence.
- Sub-half-second remainder fragments are skipped rather than emitted as distracting slivers.
- Added regression tests for dialogue-led pacing, motion-led dynamic pacing, pacing bounds, and maximum-shot constraints.
- Verification: **519 backend tests passed**; Python application compilation passed; frontend standalone timeline/API/draft-safety checks passed. React typecheck and production build remain blocked by missing dependencies and unavailable npm registry connectivity. Full authenticated browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This remains a development build, not release-ready.

## 2026-11-27 engineering update: supplied beat-grid alignment

- Smart Timeline now accepts optional `beat_times` markers (seconds) from an upstream audio beat analyzer or explicit source. It filters invalid/non-finite and non-increasing markers and estimates a beat interval from the median of plausible adjacent gaps.
- When at least three valid markers produce a stable interval, desired shot lengths are snapped to the nearest whole-beat multiple when that duration fits the source scene, remaining target, and configured minimum/maximum shot limits.
- Each clip reports whether it was beat-aligned, its whole-beat count, and the estimated beat interval. The draft reports the approximate BPM and asks the editor to verify synchronization.
- This implementation aligns to supplied beat markers; it does **not** detect beats from audio itself. The web API client can pass markers through, but automatic audio beat extraction and a visible beat-analysis control are not yet implemented.
- Verification: **521 backend tests passed**; Python application compilation passed; frontend timeline-core checks passed; ZIP integrity checked.
- React typecheck/production build, live browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding.

## 2026-11-27 engineering update: automatic audio beat candidate analysis

- Added FFmpeg-backed `energy-onset-v1` beat candidate extraction. Audio is decoded to mono 11,025 Hz PCM, measured in approximately 20 ms windows, and positive energy changes are peak-picked with a minimum spacing constraint.
- Returns candidate timestamps, an estimated BPM only when enough plausible and stable intervals are present, a conservative confidence estimate, analyzed duration, and a truncation indicator. Silence or unclear pulse returns no BPM rather than inventing one.
- Analysis is bounded to 30 minutes and has a 240-second timeout. It requires an audio stream and is scoped to the authenticated media owner/project.
- Added `GET /api/projects/{project_id}/media/{media_id}/beats` and a typed frontend `requestAudioBeatAnalysis` client method. This exposes analysis results; automatically applying them to Smart Timeline still requires a visible editor control and user review.
- This is deterministic signal-based onset analysis, not a trained music-understanding model. Candidate timestamps may include percussive onsets that are not musical beats and should be reviewed.
- Verification: **527 backend tests passed**; Python application compilation passed; frontend standalone timeline/API contract checks passed. Full React typecheck/production build, live browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This is a development build, not release-ready.

## 2026-11-27 engineering update: visible beat-analysis workflow

- Added a Music Intelligence panel to the timeline composer. It lists imported audio assets and video assets with audio streams and lets the editor request beat analysis for an individual source.
- Displays the estimated BPM (or an explicit uncertain-tempo state), confidence, detector notice, truncation warning, and a compact beat-marker strip with timestamp tooltips. The strip is a review visualization, not an editable waveform or draggable marker editor.
- The selected analysis result is passed as `beat_times` into the next Smart Timeline draft request. The editor can analyze another source to replace the active beat map; generated drafts remain preview-first and are not applied automatically.
- Added standalone frontend contract checks for the visible beat-analysis UI and its connection to the Smart Timeline request.
- Verification: **527 backend tests passed**; Python application compilation passed; frontend standalone timeline/API/draft-safety and beat-workflow contract checks passed. React typecheck/production build remains unverified because React/Vite dependencies are not installed and npm registry connectivity has previously failed. Authenticated browser upload-to-export, Android packaging/device validation, and production deployment review remain outstanding. This remains a development build, not release-ready.
