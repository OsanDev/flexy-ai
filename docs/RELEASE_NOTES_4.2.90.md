# FLEXY AI v4.2.90

## Recoverable session-service outages
- Session restoration still treats HTTP 401 as an expired or absent session and presents the sign-in flow.
- Network, CORS, and server failures are now distinguished from an expired session. The editor displays a workspace connection error instead of implying the user has been signed out.
- Added a Retry connection action that repeats the cookie-authenticated `/api/auth/me` check without reading the HttpOnly session cookie.
- The retry state is cancelled safely when the component unmounts, preserving the existing stale-response protection.

## Verification
- Added frontend source-contract tests for outage handling, retry behavior, and the 401 sign-in path.
- Frontend dependency installation and the complete Vite production build remain unverified in this offline build environment. GitHub Actions remains configured to run the production build on a network-enabled runner.
- Browser verification of deployed cookie, HTTPS, CORS, and API-origin settings remains required.
