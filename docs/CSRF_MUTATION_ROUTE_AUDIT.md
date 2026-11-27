# CSRF mutation guard update

## Change

The API's fail-closed middleware now applies the existing double-submit CSRF validator centrally to state-changing `/api/` requests when an authenticated browser session cookie and an `Origin` header are present. `GET`, `HEAD`, and `OPTIONS` are exempt. Login and registration retain their own origin validation; logout retains its explicit CSRF validation. Existing handler-level checks remain in place.

The middleware returns a JSON 403 on failed validation before route dispatch. This is defense in depth for browser-originated mutation requests and protects newly added routes from accidentally omitting a handler-level check.

## Verification

- `python -m pytest -q -rs`: 485 passed
- `python -m compileall -q app`: passed
- `npm run test:timeline`: passed
- `npm run doctor`: reports all 8 frontend dependencies missing and npm registry DNS unavailable (`EAI_AGAIN`)

## Scope and limitations

This guard is not a substitute for authenticated route dependencies or project/media ownership checks. Non-browser/internal requests without an `Origin` header are not subject to this browser CSRF guard; sensitive routes must continue to require authentication and explicit origin/token checks where applicable. Production frontend build and live browser verification remain blocked until dependencies can be installed.
