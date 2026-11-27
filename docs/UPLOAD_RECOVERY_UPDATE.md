# Upload cancellation and retry update

This development update improves the Asset Library upload lifecycle without changing the application version.

## Changes
- Upload requests accept an `AbortSignal` and can be cancelled from the Asset Library.
- A cancelled batch preserves files already uploaded successfully.
- Files that fail, plus files not yet attempted when cancellation occurs, are retained in a retry queue.
- Users can retry the remaining files without selecting them again.
- Batch progress counts successful uploads and the interface reports partial completion.
- Existing shared media validation and the 1 GB per-file limit remain in place.

## Verification
- Backend test suite: 462 passed.
- TypeScript/TSX syntax transpilation: 26 files, zero syntax diagnostics.
- Python application compilation: passed.
- Full React typecheck and Vite production build remain unverified because npm dependencies are not installed and registry DNS is unavailable.

## Limitations
Browser-level cancellation, retry and real upload interaction still require the frontend dependencies and a working browser test environment. This update must not be described as a production build or production-ready release.
