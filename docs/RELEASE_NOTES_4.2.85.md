# FLEXY AI 4.2.85 - Media import lifecycle and CI reliability

## Included
- Asset import validates supported media MIME types and the 1 GB per-file development limit in the browser before sending uploads. The backend remains authoritative and enforces its own checks.
- Multi-file import reports completed-file progress and explains partial success if a later file fails; successfully uploaded assets are retained and the library is refreshed.
- Asset preview object URLs are revoked when replaced or when the component unmounts, preventing preview memory leaks.
- Stale media-library requests are ignored when the project changes or the component is disposed, preventing late responses from replacing the active project's assets.
- Fixed frontend CI setup: `actions/setup-node` no longer attempts npm caching against a lockfile that is not present in this repository. The job performs a normal dependency install and production build.
- Updated backend and frontend release metadata to 4.2.85.

## Verification
- Backend test suite and Python compilation are rerun for this release.
- Frontend production build remains unverified locally because npm dependency installation timed out in the build environment. GitHub Actions must complete successfully before this release can be considered build-verified.
- Browser upload, timeline edit, playback, and MP4 export round-trip still require end-to-end testing with a running deployment and real media.

## Release status
Development milestone only. Not approved for production use.
