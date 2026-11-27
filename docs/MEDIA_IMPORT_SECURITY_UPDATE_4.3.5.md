# FLEXY AI 4.3.5 - Media import security update

This is a source-level hardening change in the existing 4.3.5 development line. It is not a production release.

## Change

- Reject playlist and manifest extensions (`.m3u`, `.m3u8`, `.pls`, `.xspf`, `.asx`, `.ism`, `.mpd`) before media probing.
- Reject SVG/SVGZ uploads before media probing because they can carry external resource references.
- Apply the exclusions even when a client supplies a misleading video MIME type.
- Preserve normal video, audio, and raster-image MIME detection and the existing byte-level `ffprobe` validation for accepted uploads.

## Verification

- Backend tests: 482 passed.
- Backend Python compilation: passed.
- Frontend timeline/core checks: passed.
- Full React typecheck and Vite production build remain blocked because frontend dependencies are unavailable in the environment.
- Real browser upload-to-export workflow remains unverified.
