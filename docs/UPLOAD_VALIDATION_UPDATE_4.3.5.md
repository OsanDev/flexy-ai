# FLEXY AI 4.3.5 - Media import validation update

This is a source-level maintenance update within the existing 4.3.5 development line. It does not claim a new production release.

## Changes

- Extracted browser-side media validation into `frontend-reference/apps/web/src/lib/mediaValidation.ts` so it can be tested independently.
- Kept the 1 GiB per-file upload ceiling consistent with the backend.
- Validates video, audio, and image MIME prefixes, with a known-extension fallback for browsers that provide an empty MIME type.
- Invalid files are reported individually while valid files in the same selection can still upload. Oversized files and unsupported formats are skipped.
- Added deterministic tests for mixed selections, blank MIME types, unsupported files, invalid sizes, and over-limit files.

## Verification

- Backend suite: 462 passed.
- Timeline/core checks: passed, including media upload validation helper tests.
- Python compilation: passed.
- TypeScript/TSX syntax transpilation: 26 files passed.
- Full React typecheck and Vite production build: not run successfully because npm dependencies are not installed and registry DNS access remains unavailable.
- Browser upload workflow: not claimed as verified.
