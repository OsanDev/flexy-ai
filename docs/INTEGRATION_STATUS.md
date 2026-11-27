# FLEXY AI v4.2.24 Media Ownership Integration

## Included changes
- Added owner-scoped media insertion, listing, and lookup methods to `backend/app/storage.py`.
- Updated all project media endpoints and the ID-only media read endpoint to require `current_user`.
- Every media lookup is joined through its parent project and filtered by the authenticated owner ID.
- Uploads verify project ownership before writing and re-check ownership before inserting the media row; failed inserts remove the uploaded file.
- Media file and thumbnail responses use private cache headers.
- Expanded the fail-closed API allowlist only for the media endpoints that now have authentication and owner checks.
- Added isolated SQLite and source-contract tests.

## Verification
The copied backend test suite completed successfully in the build environment. See the test output in the release notes accompanying this package.

## Still disabled / incomplete
Project versions, organization, duplication, render preflight, render creation/status/cancel/delete/download, assistant routes, and subtitle export remain unavailable behind the fail-closed 503 gate until individually integrated. Media upload size/type checks remain as existing project behavior; rate limiting and quota enforcement are still needed.

This is not production approval. Run real HTTP two-user tests, configure trusted origins and HTTPS cookies, add login rate limiting and account recovery, and review file-system cleanup and proxy behavior before public deployment.


## v4.2.38

Project dashboard organization, favorites, folders, sort controls and first-media cover previews added. The organization endpoint is now authenticated and owner-scoped. Browser/device verification remains outstanding.


## v4.2.39

Added project title settings and local recovery snapshots for unsaved timeline edits. Recovery offers explicit restore/discard controls and clears after successful cloud autosave. Runtime browser/device recovery verification remains outstanding.


## v4.2.40

Timeline now supports toggleable magnetic snapping to clip edges/playhead and video transition selection (none/fade/crossfade). Visual pointer behavior remains unverified in a live browser/device.


## v4.2.41 update: clip properties inspector

Timeline clips can now be selected to edit clip-level properties. Video transitions can be changed after clip creation; audio volume and fade values can be adjusted; caption text and timing can be changed in place. Responsive inspector styling is included. This remains a frontend reference implementation pending browser/device validation.


## v4.2.42 update: prompt-based command engine prototype

Added a deterministic command interpreter and a timeline prompt panel. Commands create an inspectable edit plan; users must explicitly apply or discard it. Current supported intents are limited to video transition presets, basic music level/fades, trimming the first clip by a supplied duration, and output resolution. This is not yet an LLM integration or free-form natural-language editor.


## v4.2.61 update: authenticated AI Director

Connected the timeline prompt UI to the backend AI Director. The API endpoint is now allowlisted, session-authenticated, CSRF-checked, and owner-scoped to the requested project. Only bounded asset metadata is supplied to the planner. The existing OpenAI-compatible provider can be enabled with backend environment secrets; local fallback remains available. Returned suggestions are displayed separately from executable local command previews. No model-generated suggestion is auto-applied.


## v4.2.61: AI plan-to-timeline execution

The authenticated AI Director response can now be converted into a non-destructive timeline preview. The adapter validates every referenced asset against the current project's loaded media library, checks MIME compatibility and numeric source/timeline ranges, validates transitions and audio volume/fades/roles, and rejects invalid drafts before any edit is applied. The preview explains that existing video/audio clips will be replaced while captions remain unchanged. Apply and Discard are explicit actions; Apply uses the composer update path so the operation participates in undo/redo. This remains metadata-driven planning: it does not inspect media frames or listen to audio, and the user must review the resulting sequence.


## v4.2.61: natural-language timeline refinement

Expanded the deterministic command planner so users can target existing timeline clips by their chronological clip number, move a clip to a requested timeline position, set a clip duration, set music volume using a percentage or supported 0–2 multiplier, and remove transitions. Commands produce a preview rather than directly mutating the document. The resulting document is checked with the timeline validator before it can be approved, and applying it continues to use the existing undo/redo update path. The prompt examples now surface these refinement commands. Model-generated planning remains optional and is not required for these local commands.


## v4.2.61: multi-step editing agent

The local editing planner now accepts up to eight ordered editing steps in one request. It splits on “then”, semicolons/newlines, and “and” when followed by a recognized editing action. Each step is planned against the previous step's proposed document, so later steps see earlier changes. The planner is atomic: if any step is unsupported or invalid, it returns the original document and explains which step failed. The combined document is validated again before it is offered for approval. Applying the preview still uses the existing undoable update path. This is a deterministic local command agent, not an autonomous model that can inspect media frames or hear audio.


## v4.2.61: timeline intelligence and clip map

Added a live, metadata-only timeline intelligence panel. It summarizes track counts, timeline length and approximate visual coverage; identifies opening gaps, gaps between clips, same-track overlaps, audio extending beyond the visual sequence, captions extending past the last visual clip, and missing audio/captions/transitions. A clip map lists source asset names, timeline ranges, tracks and transition values. Inspect actions select the related clip, switch to its editing tab, and move the playhead to its start. The analyzer uses project timeline and asset metadata only: it does not inspect video pixels, generate scene descriptions, or listen to audio.


## v4.2.61: browser-side visual media inspection

Added a visual-media contact sheet for up to 12 imported image/video assets. It loads the existing authenticated media preview endpoints, displays thumbnails, and samples preview pixels locally in the browser to estimate average brightness, luminance contrast, colourfulness and broad warm/cool/balanced tone. Object URLs are revoked when the panel unmounts or assets change. No image pixels are sent to a model or uploaded for analysis. Video previews use the backend's existing thumbnail endpoint (currently its standard preview timestamp). This is pixel-statistics analysis, not semantic object recognition, scene understanding, or creative-quality judgement.


## v4.2.61: opt-in semantic scene understanding

Connected the existing authenticated, owner-scoped `/scene-vision` endpoint to the visual media inspector. Each video asset now has an explicit AI scene-analysis action that samples one representative frame near the clip midpoint and requests a description, visible-object labels, clearly visible actions, editing notes and model confidence. The backend uses the configured OpenAI-compatible vision provider and `FLEXY_AI_API_KEY`; when unconfigured, the UI displays the provider's clear unavailable notice. The request sends one frame to the configured provider only after the user clicks. Model outputs are fallible and are presented as suggestions, not automatic edit decisions. No multi-frame narrative understanding or automatic scene cutting is claimed.


## v4.2.61: multi-frame scene storyboard

Added an opt-in scene storyboard action for each video asset. The browser requests the existing authenticated scene-boundary detector, selects up to six representative timestamps across detected scenes, then sequentially requests semantic descriptions for those frames through the existing owner-scoped vision endpoint. Results appear as timestamped scene cards with descriptions, visible objects and actions. If the vision provider is not configured, the storyboard shows the unavailable notice and stops rather than fabricating scene labels. This is a representative-frame storyboard, not continuous video understanding; scene detection and up to six provider frame requests occur only after the user clicks.


## v4.2.61: AI shot review ranking

Added a transparent, deterministic ranking layer over the AI storyboard results. It scores only the richness of returned scene metadata (description detail, visible subjects, actions, editing notes and provider confidence), then orders the sampled shots for review with timestamp tie-breaking. The UI explains that this is not a guaranteed visual-quality score and does not modify or rearrange the timeline. Unavailable analyses are excluded from the ranked list.


## v4.2.61: AI editing recommendations from scene evidence

Connected the sampled scene storyboard to the existing AI Director planning and validated timeline-preview flow. Users can explicitly ask the AI Director to create an edit recommendation from the selected video's timestamped scene descriptions, objects, actions, editing notes and review scores. The request asks for an opening, coherent sequence, possible trims and justified transitions, while reminding the planner that ranking scores measure metadata richness rather than visual quality. Returned suggestions and a validated timeline draft remain subject to the existing review/discard/apply controls. No timeline changes occur automatically.


## v4.2.61: actionable source-shot controls

Storyboard cards now support loading a source-frame thumbnail at the exact sampled timestamp and adding a 3-second excerpt to the end of the current video timeline. Excerpts are clamped to the remaining source duration, selected after insertion, and added through the timeline's existing update/history path so they can be undone. This is a user-triggered action; no clips are inserted automatically. The user can further adjust the inserted clip in the existing timeline controls.


## v4.2.61: selected clip refinement proposals

Added quick refinement proposals to the selected video clip inspector: shorten by up to 0.5 seconds, extend by up to 0.5 seconds without exceeding known source duration, move to the end of the timeline, or cycle the transition. Each action creates a preview with Apply and Discard controls. Applying uses the existing timeline update/history mechanism and therefore supports undo. These are deterministic editing suggestions, not claims of a generative AI decision; the existing AI Director remains the model-powered planning path.


## v4.2.61: conversational selected-shot copilot

When a video clip is selected, natural-language commands can now propose changes to its duration, timeline position, source in-point, and transition. Supported requests include shortening or extending by a stated number of seconds, moving to a stated timeline time, setting the source start, and choosing fade/crossfade/no transition. The copilot creates a reviewable proposal in the selected clip inspector; Apply commits through the existing undoable update path, while Discard leaves the timeline unchanged. Unsupported or ambiguous requests continue to the existing command/AI Director workflow. These selected-shot commands are deterministic local parsing, not claims of model-generated reasoning.


## v4.2.61: context-aware editing copilot

The selected-shot copilot now derives local context from the active timeline and media library: selected clip position, track, source in-point, known remaining source duration, and nearest previous/next video clips. New context-aware requests can place the selected shot after the previous shot, before the next shot, or match the previous shot's duration. Each result remains a proposal requiring Apply or Discard, and duration changes respect known source limits. This context is derived locally from the timeline; it does not imply visual scene understanding beyond the existing media-analysis features.


## v4.2.61: scene-to-scene sequence refinement

Added a review-first sequence analyzer that checks neighboring video clips on each track. It proposes closing short gaps (over 0.15s and up to 3s) and adding a fade where shots are effectively adjacent and the incoming clip has no transition. Larger gaps and overlaps are surfaced as warnings and are not automatically altered. All proposed changes are previewed together, can be discarded, and apply as one undoable timeline update. This is a deterministic timeline-geometry check, not semantic visual scene matching.


## v4.2.61: visual transition intelligence

Added browser-local boundary-frame comparison for neighboring video clips on the same track. The analyzer samples the outgoing frame near the previous clip's source end and the incoming frame near the next clip's source start through the existing media preview API. It compares brightness, contrast, colorfulness and tone, reports a coarse visual-difference level, and proposes a fade or crossfade only when the incoming clip currently has no transition. Non-adjacent pairs are skipped with warnings. Results require review and explicit approval; proposed changes apply in one undoable update. This is low-level visual-statistics comparison, not semantic scene understanding or a guarantee that a transition is artistically appropriate.


## v4.2.61: editing quality assistant

Added a deterministic pre-export quality report using timeline metadata. It scores basic structure, opening alignment, source-range bounds when media duration is known, same-track continuity, audio ending and caption timing. Findings can jump the editor to the affected timeline item. The score is a checklist indicator, not a subjective quality or storytelling grade. It does not analyze sound content, verify speech accuracy, or detect actual lip-sync.


## v4.2.61: audio intelligence

Added an opt-in audio review panel using the existing authenticated FFmpeg waveform endpoint. It summarizes normalized peak buckets, displays a compact waveform, flags near-silent regions and quiet clip edges, warns about peak buckets approaching full scale, and notes timeline overlap between dialogue and music. Findings can jump to the related audio clip. This is coarse waveform analysis, not calibrated loudness, clipping certification, speech recognition, music identification or lip-sync verification; users must listen before changing levels or edits.


## v4.2.61: smart audio mixing assistant

Added conservative, review-first mix proposals derived from timeline roles, overlap timing and the existing waveform summaries. When music overlaps dialogue, the assistant can suggest enabling the existing ducking option and lowering overlapping music clips above 0.30 to 0.30. For sufficiently long clips whose sampled waveform edges are not already quiet, it can suggest short fade-in and fade-out values. All proposals require explicit approval, validate fade bounds, and apply as one undoable update. Recommendations are heuristic starting points; users should listen and adjust for the actual content.

## v4.2.83: export target validation and download reliability

The renderer now enforces the documented output envelope server-side: 120 FPS is accepted up to 4K, including portrait 2K/4K dimensions, while 8K output is capped at 60 FPS. The export panel disables the 120 FPS choice for 8K and resets an existing 120 FPS selection to 60 FPS when the user switches to 8K. The export downloader retains its generated object URL briefly after dispatching the browser download click so large files are less likely to encounter premature URL revocation. Regression coverage includes 8K/120 rejection, 4K/120 acceptance and portrait 2K/120 acceptance.

## v4.2.84: continuous integration and build verification

Added GitHub Actions jobs for backend compilation/full tests and frontend dependency installation/production build. This moves the frontend build check to a network-enabled CI runner because local npm installation timed out. The workflow has not yet run on GitHub in this archive, so frontend build status remains pending until a CI run completes.


## v4.2.85: media import lifecycle and CI reliability

- Added client-side media type and 1 GB size checks before upload; backend checks remain authoritative.
- Multi-file imports report progress and preserve already uploaded files when a later file fails.
- Preview object URLs are revoked on replacement/unmount, and stale project requests cannot overwrite the active library.
- Removed npm cache setup that required a lockfile not present in the repository.
- Backend suite: 394 passed. Frontend source transpilation: 22 files, no syntax errors. Full type-check/production build and real browser/media round-trip remain pending.

## v4.2.86: resilient media type detection
- Browser imports now recognize common video, audio and image extensions when the browser reports an empty or generic MIME type.
- Backend upload handling falls back to extension-based media type classification and still validates the uploaded bytes with ffprobe when available.
- Unknown/non-media extensions remain rejected; this fallback does not bypass media probing.
- Full frontend production build and real browser import/export round-trip remain release blockers.

## v4.2.88 autosave recovery
- Added a browser navigation warning while the loaded active project has unsaved timeline edits.
- Added a manual retry action after autosave failure and made save status announce through an accessible live region.
- Added source-contract tests for both controls.
- Backend suite: 403 passed.
- Frontend build remains unverified because dependency installation timed out and React packages are not available in the local environment. A Vite environment type declaration is now included to provide the expected `import.meta.env` typing once dependencies are installed.
