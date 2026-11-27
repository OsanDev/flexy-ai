# FLEXY AI 4.5.2: Dialogue edit planning

## Added
- Dialogue transcript grouping into reviewable dialogue beats.
- Review-only cut candidates at long pauses, provider-labelled speaker changes, and maximum block duration boundaries.
- Each dialogue block preserves source segment IDs, timestamps, transcript text, and available provider speaker labels.
- Authenticated `POST /api/assistant/dialogue-edit-plan` endpoint with bounded pause and block-duration controls.

## Safety and correctness
- The planner does not infer speaker identities or visual scene changes.
- It never applies cuts automatically. Every boundary is explicitly marked for review.
- Speaker-change boundaries are created only when both adjacent transcript segments carry provider-supplied speaker labels.
- Empty or unlabelled transcripts remain valid and do not receive fabricated speaker metadata.

## Verification
- Dialogue planner tests cover speaker exchanges, long pauses, missing speaker labels, and input bounds.
- Backend test suite and Python compilation are run for this build.
