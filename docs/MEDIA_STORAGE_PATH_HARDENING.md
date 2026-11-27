# Media storage path hardening

## Change

Database-provided media and render filenames are now resolved through `safe_storage_path` before filesystem access in the API and rendering pipeline. The helper accepts only a single filename component, rejects POSIX and Windows path separators and traversal names, and verifies the resolved path remains directly inside its configured storage directory. This also rejects symlinks that resolve outside the storage root.

## Coverage

Regression tests cover a normal generated filename, parent traversal, absolute paths, empty/dot names, nested paths, Windows separators, and symlink escape.

## Verification

- Backend test suite: 494 passed.
- Backend Python compilation: passed.
- Frontend timeline core checks: passed.

This is a development-source hardening change, not a production security certification. Full frontend dependency installation, production build, live browser upload-to-export test, deployment review, and Android packaging remain outstanding.
