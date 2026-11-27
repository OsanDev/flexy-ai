# FLEXY AI v4.3.8 — Team Demo Integration Candidate

Date: 2026-11-27

## Purpose

This package consolidates the existing editor capabilities into a version-aligned team-demo candidate. It does not claim production readiness or introduce a new AI capability that has not been verified in source.

## Included capabilities confirmed in the source tree

- React + TypeScript + Vite editing workspace and Python + FastAPI backend.
- Multi-track timeline editing, clip operations, timeline validation, undo/redo and recovery flows.
- AI Director prompt workflow with a local rules fallback and optional compatible model provider.
- Scene/dialogue-aware Smart Timeline draft generation using supplied scene and transcript evidence.
- Audio beat analysis and beat marker projection.
- Beat-aware transition suggestions.
- Caption-timing-based music ducking proposals.
- Audio automation curves, mixer buses and configurable ducking.
- Speech transcription/subtitle generation modules.
- Authenticated project/media and export-related backend foundations.

## Integration maintenance in 4.3.8

- Aligned backend API, frontend package, and visible editor version to `4.3.8`.
- Updated release-contract tests that still asserted the obsolete `4.3.5` version.
- Added a consolidated team demo guide and explicit release-readiness checklist.

## Verification performed for this package

- `npm run test:timeline`: passed.
- `python -m compileall -q app`: passed.
- Backend pytest suite: 506 passed, 23 failed before version-contract refresh. The failures were stale assertions hard-coded to `4.3.5`; the suite must be rerun after this refresh.
- Full frontend TypeScript/Vite build: not verified; frontend dependencies are not installed in the supplied workspace.
- Live authenticated browser upload → edit → export: not verified.

## Release status

Internal demo candidate only. Do not describe it as production-ready, and do not promise specific high-resolution/high-frame-rate performance until the exact export profile has been rendered and playback-checked on target hardware.
