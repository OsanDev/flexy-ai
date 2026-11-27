import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";

const root = resolve(new URL("..", import.meta.url).pathname);
const temp = mkdtempSync(join(tmpdir(), "flexy-timeline-"));
const tsc = process.env.TSC_BIN || "tsc";
const result = spawnSync(tsc, [
  "src/lib/timelineGraph.ts", "src/lib/timelineCommands.ts", "src/lib/audioAutomation.ts", "src/lib/audioMeter.ts", "src/lib/mediaValidation.ts", "src/lib/smartTimelineValidation.ts", "src/lib/beatMarkers.ts", "src/lib/musicTransitionIntelligence.ts", "src/lib/audioMixAssistant.ts", "src/lib/speechCaptionLayout.ts", "src/lib/dialoguePauseTrim.ts", "src/lib/dialogueTrimSync.ts",
  "--target", "ES2022", "--module", "commonjs", "--strict",
  "--skipLibCheck", "--outDir", temp,
], { cwd: root, encoding: "utf8" });
if (result.status !== 0) {
  process.stderr.write(result.stdout || "");
  process.stderr.write(result.stderr || "");
  process.exit(result.status ?? 1);
}
try {
  const require = createRequire(import.meta.url);
  const { planTimelineCommand } = require(join(temp, "timelineCommands.js"));
  const { buildRenderGraph, getTimelineDuration, validateTimelineDocument } = require(join(temp, "timelineGraph.js"));
  const { normalizeVolumeKeyframes, volumeAtTime } = require(join(temp, "audioAutomation.js"));
  const { peakToDbfs, dbfsToMeterPercent } = require(join(temp, "audioMeter.js"));
  const { validateMediaFiles, MAX_UPLOAD_BYTES } = require(join(temp, "mediaValidation.js"));
  const { validateSmartTimelineDraft } = require(join(temp, "smartTimelineValidation.js"));
  const { projectBeatMarkers } = require(join(temp, "beatMarkers.js"));
  const { proposeMusicTransitions } = require(join(temp, "musicTransitionIntelligence.js"));
  const { buildDialogueDuckKeyframes, recommendAudioMix } = require(join(temp, "audioMixAssistant.js"));
  const { buildSpeechCaptionCues } = require(join(temp, "speechCaptionLayout.js"));
  const { trimDialoguePauses } = require(join(temp, "dialoguePauseTrim.js"));
  const { synchronizeDialogueAfterTrim } = require(join(temp, "dialogueTrimSync.js"));
  const speechCues = buildSpeechCaptionCues([{ id: "s1", start: 0, end: 3, text: "Hello there, welcome to FLEXY AI today.", words: [
    { word: "Hello", start: 0, end: 0.35 }, { word: "there,", start: 0.36, end: 0.7 },
    { word: "welcome", start: 0.8, end: 1.2 }, { word: "to", start: 1.21, end: 1.35 },
    { word: "FLEXY", start: 1.36, end: 1.8 }, { word: "AI", start: 1.81, end: 2.0 },
    { word: "today.", start: 2.01, end: 2.4 },
  ] }], { maxWords: 2 });
  if (speechCues.length !== 4 || speechCues[0].text !== "Hello there," || speechCues[1].start !== 0.8 || !speechCues.every((cue) => cue.wordTimed)) throw new Error(`Speech caption layout failed: ${JSON.stringify(speechCues)}`);
  const fallbackCue = buildSpeechCaptionCues([{ id: "s2", start: 4, end: 5, text: "No word timing available" }]);
  if (fallbackCue.length !== 1 || fallbackCue[0].wordTimed || fallbackCue[0].start !== 4) throw new Error("Speech caption fallback must preserve provider segment timing");
  const duckClip = { id: "music-duck", mediaId: "music", sourceStart: 0, duration: 12, timelineStart: 5, trackIndex: 0, volume: 1, fadeIn: 0, fadeOut: 0, role: "music", volumeKeyframes: [] };
  const duckPoints = buildDialogueDuckKeyframes(duckClip, [
    { id: "cap-1", text: "Hello there", start: 7, duration: 1.5 },
    { id: "cap-2", text: "How are you", start: 8.4, duration: 1 },
  ]);
  if (duckPoints.length !== 4 || duckPoints[0].time !== 1.88 || duckPoints[1].time !== 2 || duckPoints[1].volume !== 0.35 || duckPoints[2].time !== 4.4) {
    throw new Error(`Dialogue-timed ducking keyframes were not generated correctly: ${JSON.stringify(duckPoints)}`);
  }
  const duckDocument = {
    videoClips: [], audioClips: [duckClip], captions: [{ id: "cap", text: "spoken words", start: 7, duration: 2 }],
    width: 1920, height: 1080, frameRate: 30, exportPreset: "1080p", videoBitrate: "12M", ducking: false,
  };
  const duckPlan = recommendAudioMix(duckDocument, []);
  if (!duckPlan.changes.some((change) => change.clipId === "music-duck" && change.patch?.volumeKeyframes?.length >= 4)) {
    throw new Error("Audio mix assistant did not propose caption-synchronized music automation");
  }
  const syncOriginal = { id: "sync-v", mediaId: "sync-media", sourceStart: 0, duration: 10, timelineStart: 0, trackIndex: 0, transition: "none" };
  const syncTrimmed = [
    { ...syncOriginal, duration: 3.5 },
    { ...syncOriginal, id: "sync-v-2", sourceStart: 5.5, duration: 4.5, timelineStart: 3.5, transition: "none" },
  ];
  const syncAudio = [
    { id: "dialogue-a", mediaId: "sync-media", sourceStart: 0, duration: 10, timelineStart: 0, trackIndex: 1, volume: 1, fadeIn: 0, fadeOut: 0, role: "dialogue", volumeKeyframes: [{ time: 1, volume: 0.8 }, { time: 7, volume: 0.6 }] },
    { id: "music-a", mediaId: "music", sourceStart: 0, duration: 10, timelineStart: 0, trackIndex: 2, volume: 1, fadeIn: 0, fadeOut: 0, role: "music" },
  ];
  const syncCaptions = [
    { id: "cap-before", text: "First line", start: 1, duration: 1 },
    { id: "cap-after", text: "Second line", start: 6, duration: 1 },
    { id: "cap-spanning", text: "Review this line", start: 3, duration: 3 },
  ];
  const syncResult = synchronizeDialogueAfterTrim(syncOriginal, syncTrimmed, syncAudio, syncCaptions);
  const syncedDialogueTail = syncResult.audioClips.find((clip) => clip.id.startsWith("dialogue-a-sync-"));
  if (syncResult.audioClips.length !== 3 || syncedDialogueTail?.timelineStart !== 3.5 || syncedDialogueTail?.sourceStart !== 5.5) throw new Error(`Dialogue audio did not follow retained video sections: ${JSON.stringify(syncResult.audioClips)}`);
  if (syncResult.audioClips.find((clip) => clip.id === "music-a") !== syncAudio[1]) throw new Error("Music clip should remain untouched by dialogue synchronization");
  if (syncResult.captions.find((item) => item.id === "cap-after")?.start !== 4) throw new Error("Post-cut caption did not move with the retained dialogue");
  if (!syncResult.warnings.some((warning) => warning.includes("spans a removed pause"))) throw new Error("Caption crossing a removed pause should be flagged for review");
  const document = {
    videoClips: [
      { id: "v1", mediaId: "asset-v1", sourceStart: 0, duration: 8, timelineStart: 0, trackIndex: 0, transition: "none" },
      { id: "v2", mediaId: "asset-v2", sourceStart: 1, duration: 5, timelineStart: 8, trackIndex: 0, transition: "none" },
    ],
    audioClips: [{ id: "a1", mediaId: "asset-a1", sourceStart: 0, duration: 13, timelineStart: 0, trackIndex: 0, volume: 1, fadeIn: 0, fadeOut: 0, role: "music", volumeKeyframes: [{ time: 0, volume: 0.2 }, { time: 5, volume: 0.9 }] }],
    captions: [], width: 1920, height: 1080, frameRate: 30, exportPreset: "1080p", videoBitrate: "12M", ducking: false,
    duckingSettings: { thresholdDb: -30, ratio: 5, attackMs: 35, releaseMs: 700 },
    audioMixer: { dialogue: { gain: 1, muted: false }, music: { gain: 0.75, muted: false }, effects: { gain: 1, muted: true }, master: { gain: 0.9, muted: false } },
  };
  const plan = planTimelineCommand(document, "move clip 2 to 10 seconds and set clip 1 duration to 6 seconds and set music volume to 40%");
  if (plan.error) throw new Error(plan.error);
  if (plan.nextDocument.videoClips.find((clip) => clip.id === "v2").timelineStart !== 10) throw new Error("Clip positioning failed");
  if (plan.nextDocument.videoClips.find((clip) => clip.id === "v1").duration !== 6) throw new Error("Clip duration edit failed");
  if (plan.nextDocument.audioClips[0].volume !== 0.4) throw new Error("Audio volume edit failed");
  if (validateTimelineDocument(plan.nextDocument).length) throw new Error("Edited timeline failed validation");
  const graph = buildRenderGraph(plan.nextDocument);
  if (graph.clips.length !== 2 || graph.audio_clips.length !== 1) throw new Error("Render graph serialization lost clips");
  if (graph.ducking_settings.threshold_db !== -30 || graph.ducking_settings.ratio !== 5 || graph.ducking_settings.attack_ms !== 35 || graph.ducking_settings.release_ms !== 700) throw new Error("Ducking settings were not serialized");
  if (graph.audio_clips[0].volume_keyframes.length !== 2 || graph.audio_clips[0].volume_keyframes[1].volume !== 0.9) throw new Error("Audio volume keyframes were not serialized");
  if (graph.audio_clips[0].bus !== "music" || graph.audio_mixer.music.gain !== 0.75 || graph.audio_mixer.effects.muted !== true || graph.audio_mixer.master.gain !== 0.9) throw new Error("Audio bus routing or mixer settings were not serialized");
  const invalidKeyframes = { ...plan.nextDocument, audioClips: [{ ...plan.nextDocument.audioClips[0], volumeKeyframes: [{ time: 3, volume: 1 }, { time: 2, volume: 0.5 }] }] };
  if (!validateTimelineDocument(invalidKeyframes).some((error) => error.includes("volume automation"))) throw new Error("Invalid audio volume keyframes were not rejected");
  const invalidBus = { ...plan.nextDocument, audioClips: [{ ...plan.nextDocument.audioClips[0], bus: "master" }] };
  if (!validateTimelineDocument(invalidBus).some((error) => error.includes("output bus"))) throw new Error("Invalid audio bus routing was not rejected");
  const invalidMixer = { ...plan.nextDocument, audioMixer: { ...plan.nextDocument.audioMixer, music: { gain: 3, muted: false } } };
  if (!validateTimelineDocument(invalidMixer).some((error) => error.includes("Audio mixer music"))) throw new Error("Invalid audio mixer gain was not rejected");
  const invalidDucking = { ...plan.nextDocument, duckingSettings: { ...plan.nextDocument.duckingSettings, ratio: 25 } };
  if (!validateTimelineDocument(invalidDucking).some((error) => error.includes("Ducking ratio"))) throw new Error("Invalid ducking settings were not rejected");
  if (getTimelineDuration(plan.nextDocument) !== 15) throw new Error("Timeline duration is incorrect");
  const rejected = planTimelineCommand(document, "move clip 99 to 2 seconds");
  if (!rejected.error || rejected.nextDocument.videoClips[0].duration !== 8) throw new Error("Invalid command was not safely rejected");
  const normalized = normalizeVolumeKeyframes([
    { time: 8, volume: 3 }, { time: -1, volume: -0.5 }, { time: 4, volume: 0.5 },
    { time: 4, volume: 1.25 }, { time: Number.NaN, volume: 1 },
  ], 6);
  if (normalized.length !== 3 || normalized[0].time !== 0 || normalized[0].volume !== 0 || normalized[1].volume !== 1.25 || normalized[2].time !== 6 || normalized[2].volume !== 2) throw new Error("Volume automation normalization failed");
  if (volumeAtTime([{ time: 0, volume: 0 }, { time: 4, volume: 2 }], 1) !== 0.5) throw new Error("Volume automation interpolation failed");
  if (volumeAtTime([], 1, 0.7) !== 0.7) throw new Error("Constant volume fallback failed");
  if (peakToDbfs(0) !== -90 || Math.abs(peakToDbfs(0.5) - (-6.020599913279624)) > 1e-9 || peakToDbfs(2) !== 0) throw new Error("Audio peak dBFS conversion failed");
  if (dbfsToMeterPercent(-60) !== 0 || dbfsToMeterPercent(-30) !== 50 || dbfsToMeterPercent(0) !== 100 || dbfsToMeterPercent(-100) !== 0) throw new Error("Audio meter scaling failed");
  const mediaCheck = validateMediaFiles([
    { name: "clip.MP4", type: "", size: 1024 },
    { name: "voice", type: "audio/wav", size: 2048 },
    { name: "notes.txt", type: "text/plain", size: 10 },
    { name: "huge.mov", type: "video/quicktime", size: MAX_UPLOAD_BYTES + 1 },
    { name: "negative.mp4", type: "video/mp4", size: -1 },
  ]);
  if (mediaCheck.accepted.length !== 2 || mediaCheck.rejected.length !== 3) throw new Error("Media upload validation did not separate accepted and rejected files");
  if (mediaCheck.rejected[0].reason !== "unsupported" || mediaCheck.rejected[1].reason !== "too_large" || mediaCheck.rejected[2].reason !== "too_large") throw new Error("Media upload validation returned an incorrect rejection reason");
  const smartApiSource = await import("node:fs/promises").then(({ readFile }) => readFile(join(root, "src/lib/smartTimelineApi.ts"), "utf8"));
  for (const contract of ["/api/assistant/smart-timeline", "transcript_segments", "target_duration", "X-CSRF-Token", "visual_score", "visual_signals"]) {
    if (!smartApiSource.includes(contract)) throw new Error(`Smart Timeline API contract is missing ${contract}`);
  }
  const composerSource = await import("node:fs/promises").then(({ readFile }) => readFile(join(root, "src/components/TimelineComposer.tsx"), "utf8"));
  for (const contract of ["requestAudioBeatAnalysis", "aria-label=\"Music beat analysis\"", "beatAnalysis.beats", "beatTimes: beatAnalysis?.beats ?? []", "beat-marker-strip", "projectBeatMarkers", "timeline-beat-marker"]) {
    if (!composerSource.includes(contract)) throw new Error(`Visible beat-analysis workflow is missing ${contract}`);
  }
  const projectedBeats = projectBeatMarkers(
    [0, 0.5, 1, 1.5, 2, 3, Number.NaN],
    [
      { mediaId: "music", sourceStart: 1, duration: 2, timelineStart: 5 },
      { mediaId: "music", sourceStart: 0, duration: 1, timelineStart: 10 },
      { mediaId: "other", sourceStart: 0, duration: 10, timelineStart: 0 },
    ],
    "music",
  );
  if (JSON.stringify(projectedBeats) !== JSON.stringify([5, 5.5, 6, 7, 10, 10.5, 11])) throw new Error("Source-relative beat markers were not projected correctly onto timeline clips");
  const invalidBeatProjection = projectBeatMarkers([1, 2], [{ mediaId: "music", sourceStart: 0, duration: -1, timelineStart: 0 }], "music");
  if (invalidBeatProjection.length) throw new Error("Invalid audio clip timing produced beat markers");
  const transitionClips = [
    { id: "a", timelineStart: 0, duration: 4.1, trackIndex: 0, transition: "none" },
    { id: "b", timelineStart: 4, duration: 3, trackIndex: 0, transition: "none" },
    { id: "c", timelineStart: 7.5, duration: 2, trackIndex: 0, transition: "none" },
    { id: "other-track", timelineStart: 4, duration: 2, trackIndex: 1, transition: "none" },
  ];
  const transitionSuggestions = proposeMusicTransitions(transitionClips, [3.95, 4.02, 7.5, Number.NaN]);
  if (transitionSuggestions.length !== 2) throw new Error("Beat transition suggestions should target only close same-track cuts");
  if (transitionSuggestions[0].clipId !== "b" || transitionSuggestions[0].transition !== "crossfade") throw new Error("Overlapping beat-aligned cut should suggest crossfade");
  if (transitionSuggestions[1].clipId !== "c" || transitionSuggestions[1].transition !== "fade") throw new Error("Non-overlapping beat-aligned cut should suggest fade");
  if (proposeMusicTransitions(transitionClips, [4], -1).length) throw new Error("Invalid transition tolerance should return no suggestions");
  if (proposeMusicTransitions(transitionClips, [Number.NaN]).length) throw new Error("Invalid beat timestamps should be ignored");
  const smartAssets = [
    { id: "video-1", type: "video", duration: 12 },
    { id: "music-1", type: "audio", duration: 20 },
  ];
  const validSmartDraft = {
    duration: 8, clips: [{ assetId: "video-1", start: 0, sourceStart: 1, duration: 4 }, { assetId: "video-1", start: 4, sourceStart: 5, duration: 4 }],
    audio_clips: [{ assetId: "music-1", start: 0, sourceStart: 0, duration: 8, volume: 0.7 }],
  };
  if (!validateSmartTimelineDraft(validSmartDraft, smartAssets, 8).valid) throw new Error("Valid Smart Timeline draft was rejected");
  const unsafeSmartDraft = { ...validSmartDraft, clips: [{ assetId: "missing", start: -1, sourceStart: 10, duration: 5 }] };
  const unsafeResult = validateSmartTimelineDraft(unsafeSmartDraft, smartAssets, 8);
  if (unsafeResult.valid || unsafeResult.errors.length < 3) throw new Error("Unsafe Smart Timeline draft was not rejected");
  const overlappingDraft = { ...validSmartDraft, clips: [{ assetId: "video-1", start: 0, sourceStart: 0, duration: 5 }, { assetId: "video-1", start: 4, sourceStart: 5, duration: 4 }] };
  if (validateSmartTimelineDraft(overlappingDraft, smartAssets, 8).valid) throw new Error("Overlapping Smart Timeline shots were not rejected");
  const overlongAudio = { ...validSmartDraft, audio_clips: [{ assetId: "music-1", start: 0, sourceStart: 0, duration: 9, volume: 0.7 }] };
  if (validateSmartTimelineDraft(overlongAudio, smartAssets, 8).valid) throw new Error("Overlong Smart Timeline audio was not rejected");
  process.stdout.write("Smart Timeline API contract and draft-safety checks passed.\n");
  process.stdout.write("Timeline core checks passed: move, trim/duration, audio level, validation, graph serialization, configurable ducking, volume automation normalization/interpolation, audio bus routing and mixer serialization, peak dBFS conversion, meter scaling, mixed-file upload validation, beat projection, beat-synced transition suggestions, dialogue-caption-synchronized music ducking automation, word-timed speech caption layout, duration, and invalid-command rollback.\n");
} finally {
  rmSync(temp, { recursive: true, force: true });
}
