# FLEXY AI 4.5.4: Approved Dialogue Cut Operations

## Added
- Dialogue cut candidates can now be applied as explicit split operations on matching video timeline clips.
- Source timestamps are mapped through each clip source in-point to the corresponding timeline position.
- The split preserves both resulting clip segments and their media references.
- Split operations use the existing document update/history path, so Undo and Redo remain available.
- A preview-position action remains available even when the transcribed media is not currently on the video timeline.

## Safety and limitations
- No suggested cut is applied automatically. The user must select **Split clip**.
- Split controls are disabled unless the timestamp falls inside a matching video clip.
- This operation creates an edit boundary; it does not remove the pause or delete media.
- Audio-only clips are not split by this dialogue action in this release.
- Full frontend typecheck/build requires installing the project dependencies.
