# FLEXY AI 4.5.3: Dialogue Timeline Integration

## Added
- Connected the dialogue edit-plan API to the caption workspace.
- Added a reviewable dialogue block list with source time ranges and provider speaker labels when available.
- Added non-destructive cut-candidate markers for long pauses, speaker changes, and block-length boundaries.
- Selecting a dialogue block or candidate moves the timeline playhead to its source timestamp.
- Added responsive styling for the dialogue review panel.

## Safety and behavior
- Suggestions do not modify, split, or delete clips automatically.
- The planner uses transcript timing and provider-supplied speaker labels only; it does not claim to detect visual scenes or identify real people.
- Speaker labels remain unavailable when the configured transcription provider does not return them.

## Verification
- Backend test suite: 545 passed.
- Timeline core checks: passed.
- Frontend TypeScript build: not verified because React and its type packages are not installed in this environment.
