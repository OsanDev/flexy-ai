# FLEXY AI v4.3.7 development update

## Caption-synchronized music automation

- Added a review-first planner that proposes clip-relative volume keyframes for music clips overlapping existing caption timing.
- Music gain is eased down before a caption window, held lower during the window, and restored after it.
- Nearby/overlapping caption windows are merged to avoid duplicate or conflicting automation points.
- Existing keyframes outside the generated ducking windows are preserved; baseline gain is sampled from existing automation.
- The plan is applied through the existing undoable Smart Mix workflow and remains editable in the audio automation curve.
- When caption timing is unavailable, the existing dialogue-track ducking recommendation remains available.
- No speech is inferred from waveform peaks; caption timing is used only when already present in the project.

## Verification

- `npm run test:timeline`: passed, including new caption-synchronized automation cases.
- React/TypeScript production build and live-browser workflow: not verified in this workspace because frontend dependencies have not been installed.
- This is a development update, not a production release.
