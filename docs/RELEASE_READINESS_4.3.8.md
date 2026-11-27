# FLEXY AI v4.3.8 Release Readiness

## Current status: Internal demo candidate only

| Area | Status | Evidence / next action |
|---|---|---|
| Timeline core | Passed | `npm run test:timeline` |
| Backend syntax | Passed | `python -m compileall -q app` |
| Backend tests | Re-run required | Refresh stale version assertions, then run `python -m pytest -q -rs` |
| Frontend dependencies | Pending | Run `npm install --no-audit --no-fund` |
| TypeScript | Pending | Run `npm run typecheck` |
| Vite production build | Pending | Run `npm run build` |
| Browser E2E | Partial | Current suite mocks `/api/**`; add live-backend acceptance |
| Real upload-to-export | Pending | Upload media, edit, render, download and inspect MP4 with FFprobe |
| AI provider workflows | Configuration-dependent | Configure server-side provider credentials and verify enabled routes |
| Security review | Pending | Auth, CSRF, ownership, upload limits, worker isolation, rate limits |
| Performance | Pending | Test representative media and target export profiles on intended hardware |
| Accessibility | Pending | Keyboard, focus, contrast, screen-reader and responsive review |
| Deployment/Android | Pending | HTTPS, backups, monitoring, deployment and physical-device validation |

## Required commands

Backend:
```bash
cd backend
python -m compileall -q app
python -m pytest -q -rs
```

Frontend:
```bash
cd frontend-reference/apps/web
npm install --no-audit --no-fund
npm run doctor
npm run typecheck
npm run test:timeline
npm run build
npm run test:e2e
```

A passing mocked browser test is not evidence of a live backend workflow. Do not mark the release production-ready until all required checks are completed in the target environment.
