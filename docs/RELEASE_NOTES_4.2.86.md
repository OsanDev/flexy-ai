# FLEXY AI 4.2.86 - Resilient media type detection

## Included
- Browser import validation accepts recognized video, audio and image extensions when the browser reports an empty or generic MIME type.
- The backend resolves an absent or generic upload MIME type from the filename extension and stores the normalized media type.
- The backend still runs media probing after upload and rejects content that cannot be read as a valid media stream.
- Uploads with unknown or non-media extensions remain rejected.
- Updated backend and frontend release metadata to 4.2.86.

## Verification
- Added tests for valid browser MIME types, empty/generic browser MIME fallback, and rejection of unknown/non-media extensions.
- Full frontend production build and real browser import remain unverified because npm dependency installation is unavailable in the current build environment.

## Release status
Development milestone only. Not approved for production use.
