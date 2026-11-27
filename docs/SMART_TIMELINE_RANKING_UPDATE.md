# Smart Timeline Ranking Update

## Change

The deterministic Smart Timeline draft now ranks candidate scenes before selecting footage. Ranking uses only supplied evidence:

- dialogue density within each detected scene;
- duration suitability for the selected editing style (dynamic, balanced, calm).

The ranker selects the strongest candidates until the requested duration is filled, then restores source chronology before emitting clips. Dialogue-bearing shots are anchored to the supplied transcript start when the scene is longer than the selected shot. Each emitted clip includes an explainable `shot_score`, `dialogue_density`, and `duration_fit` in its evidence payload.

## Limitations

This is evidence-based deterministic ranking, not learned semantic video understanding. It does not infer emotion, subject identity, visual quality, or story meaning. Ranking quality depends on the accuracy of scene boundaries and transcript timestamps. Editors should review the generated first cut.

## Verification

- Backend suite: 500 passed.
- Python compilation: passed.
- Frontend timeline core checks: passed.
- React/TypeScript production build: still blocked pending frontend dependency installation.
