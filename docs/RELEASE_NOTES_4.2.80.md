# FLEXY AI v4.2.80 - Calibrated audio quality measurements

## Added
- Added a per-source **Measure LUFS** action to the Audio Intelligence review panel.
- The action reports EBU R128 integrated loudness (LUFS), loudness range (LU), and true peak (dBFS) from the backend FFmpeg analyzer.
- Reports distinguish unavailable measurements from numeric zero and can be refreshed independently for each source media asset.
- The existing waveform assistant remains explicitly identified as a coarse peak summary, not a calibrated loudness meter.

## Safety and behavior
- Measurement is read-only. It does not normalize, limit, compress, or otherwise modify source audio or timeline levels.
- Analysis requires FFmpeg and a decodable audio stream on the server.
- Very short or silent sources may not produce every EBU R128 metric; missing values remain unavailable rather than being guessed.

## Verification
- Backend audio-quality parser tests and release configuration tests are included in the targeted test run.
- Frontend production build still requires installing the exact npm dependencies; it must be verified in an environment with network/package-cache access before production deployment.
