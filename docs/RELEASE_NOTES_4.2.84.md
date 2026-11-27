# FLEXY AI 4.2.84 - Continuous integration and build verification

## Included
- Added GitHub Actions CI for backend compilation and the complete pytest suite.
- Added a separate frontend job that installs the declared npm dependencies and runs the production TypeScript/Vite build.
- CI runs on pushes and pull requests with read-only repository permissions.
- Updated backend and frontend package version metadata to 4.2.84.

## Local verification
- Backend test suite: 391 passed before the CI-only changes; rerun against this release before merging.
- Frontend production build: not verified locally because npm dependency installation timed out in this environment. The new CI job is intended to run the install and build in GitHub Actions where package registry access is available.

## Release status
This is a development milestone, not production approval. A green CI run is still required. Browser/device editing, real media upload, render-worker execution, and complete export/download round trips must also be verified before production use.
