# FLEXY AI 4.2.83 - Export target validation and download reliability

## Changes

- Enforced the supported high-frame-rate delivery envelope on the backend: 120 FPS is accepted through 4K, while 8K output is limited to 60 FPS.
- Updated the export panel to disable the 120 FPS choice for 8K and automatically fall back to 60 FPS when switching an existing 120 FPS selection to 8K.
- Kept generated blob URLs alive for a short cleanup window after a download click, avoiding premature revocation during large file downloads.
- Added regression tests proving 8K/120 FPS is rejected and 4K/120 FPS remains accepted.

## Verification

Run from `backend/`:

```bash
python -m pytest -q -p no:cacheprovider tests/test_rendering.py tests/test_render_preflight.py tests/test_release_config.py
```

The full frontend production build remains unverified until npm dependencies can be installed in the build environment.
