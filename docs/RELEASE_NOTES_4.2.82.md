# FLEXY AI 4.2.82 · Account-scoped project history

## What changed
- Project revision history list and snapshot reads now require an authenticated account.
- Version queries are constrained through the owning project row; another account receives the same not-found response as an unknown project.
- Restore operations use the owner-scoped optimistic-save path. Restoring an older snapshot creates a new revision and never rewinds the revision counter.
- Stale restore requests return the existing `PROJECT_VERSION_CONFLICT` response with the current revision.
- Added integration tests for unauthenticated access, cross-account isolation, restore semantics, and stale revision conflicts.

## Verification
The complete backend suite passes: **389 passed**. The frontend production build remains unverified because npm dependency installation timed out in the build environment. This development package is not yet a production-ready release.
