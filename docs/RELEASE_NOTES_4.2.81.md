# FLEXY AI 4.2.81 · Audio measurement accuracy

- Corrected EBU R128 parsing to read the final FFmpeg summary rather than periodic live measurements that may appear earlier in the log.
- When FFmpeg emits more than one summary block, the parser uses the last complete block.
- Added regression tests for periodic live readings and repeated summaries.
- This is a read-only measurement correction. It does not normalize, compress, limit, or otherwise alter source audio.

## Verification

- Audio-quality unit tests and speech tests are run as targeted checks.
- The full backend suite still contains legacy unauthenticated integration tests and routes deliberately fail-closed while ownership integration is incomplete. Those failures must not be bypassed by weakening account protection.
- Frontend production build and real-media/device end-to-end checks remain outstanding.
