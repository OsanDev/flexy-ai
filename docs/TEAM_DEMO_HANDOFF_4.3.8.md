# FLEXY AI v4.3.8 — Team Demo Handoff

**Audience:** Product and engineering team  
**Build:** 4.3.8 internal demo candidate  
**Duration:** 8–10 minutes  
**Status:** Demo candidate, not production release

## 1. Product story (45 seconds)

FLEXY AI is a browser-based multi-track video editor with an AI-assisted editing workflow. The AI proposes editable changes; the editor remains in control and can review or reject drafts before applying them.

## 2. Editor foundation (2 minutes)

Demonstrate:
- Project dashboard and asset library.
- Import video/audio/image assets.
- Multi-track timeline and clip selection.
- Trim, move, split/delete, undo/redo and autosave/recovery UI.
- Preview and export settings.

Use short, non-sensitive sample media prepared before the meeting.

## 3. AI Director and Smart Timeline (2 minutes)

- Enter a natural-language editing instruction.
- Show the returned plan and warnings.
- Explain that local planning mode is available without provider credentials.
- Generate a Smart Timeline draft using available scene/transcript evidence.
- Review the proposed sequence before accepting it.

Do not claim semantic scene recognition or model-generated output unless the provider is configured and the capability is demonstrated live.

## 4. Music and dialogue intelligence (2 minutes)

- Analyze an audio asset and show candidate beat markers/BPM confidence.
- Show beat markers projected onto the timeline.
- Show music-aware transition suggestions.
- Show caption-timing-based music ducking proposals and editable automation curves.

Explain that beat markers are analysis candidates and should be reviewed against the music. Caption ducking uses existing caption timing; it does not infer dialogue where captions are absent.

## 5. Speech and captions (1 minute)

Show transcription/subtitle workflow and caption timing tools using prepared media. Provider-backed transcription requires valid server-side credentials and an enabled route.

## 6. Close with engineering status (1 minute)

State clearly:
- Timeline-core checks pass in the supplied environment.
- Backend Python compilation passes.
- Backend test suite must be rerun after version-contract refresh.
- Full frontend typecheck/Vite build is pending dependency installation.
- Current browser E2E suite uses mocked API responses; live authenticated upload-to-export acceptance is still required.
- Security, performance, accessibility, deployment and Android validation remain release gates.

## Demo setup checklist

- [ ] Install backend dependencies and FFmpeg/FFprobe.
- [ ] Install frontend dependencies from the trusted npm registry.
- [ ] Configure exact CORS origins.
- [ ] Configure HTTPS and secure cookies for any shared environment.
- [ ] Configure server-side AI credentials only if demonstrating provider-backed features.
- [ ] Prepare sample media and a clean demo account.
- [ ] Verify sign-in, project creation, import, editing, preview and export in the actual target environment.
- [ ] Keep a backup copy of the source archive and demo media.

## Suggested opening

“FLEXY AI combines a conventional editable timeline with AI-assisted planning. Today we’ll show the editor foundation, how the AI proposes a first cut, and how music, beats and captions can inform the edit. We’ll also separate what is demonstrated from what remains in release validation.”

## Suggested closing

“This is an internal demo candidate. The core editing and intelligence workflows are represented in source, but production approval depends on a successful frontend build, live browser acceptance, security review and deployment validation.”
