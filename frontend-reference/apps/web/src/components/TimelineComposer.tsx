import { useEffect, useMemo, useState } from "react";
import type { MediaAsset, WaveformData, TranscriptionResult, AudioQualityResult, DialogueEditPlan } from "../lib/mediaApi";
import { PlaybackPreview } from "./PlaybackPreview";
import { AudioAutomationCurve } from "./AudioAutomationCurve";
import { planTimelineCommand, type TimelineCommandPlan } from "../lib/timelineCommands";
import { aiDirectorApi, type DirectorPlan } from "../lib/aiDirectorApi";
import { adaptDirectorDraftToTimeline, type DirectorTimelinePreview } from "../lib/aiPlanAdapter";
import { analyzeTimeline } from "../lib/timelineIntelligence";
import { analyzeTimelineQuality } from "../lib/timelineQuality";
import { analyzeAudioWaveforms } from "../lib/audioIntelligence";
import { recommendAudioMix, type AudioMixPlan } from "../lib/audioMixAssistant";
import { analyzeCaptionTiming, type CaptionIntelligenceReport } from "../lib/captionIntelligence";
import { analyzePreviewPixels } from "../lib/visualMediaAnalysis";
import { mediaApi } from "../lib/mediaApi";
import { trimDialoguePauses } from "../lib/dialoguePauseTrim";
import { synchronizeDialogueAfterTrim } from "../lib/dialogueTrimSync";
import { requestSmartTimeline, requestAudioBeatAnalysis, type AudioBeatAnalysis, type SmartTimelineDraft } from "../lib/smartTimelineApi";
import { validateSmartTimelineDraft } from "../lib/smartTimelineValidation";
import { projectBeatMarkers } from "../lib/beatMarkers";
import { proposeMusicTransitions } from "../lib/musicTransitionIntelligence";
import { buildSpeechCaptionCues } from "../lib/speechCaptionLayout";
import { VisualMediaInspector } from "./VisualMediaInspector";
import {
  buildRenderGraph, getTimelineDuration, validateTimelineDocument,
  type TimelineDocument, type CaptionStyle, type SavedCaptionPreset,
} from "../lib/timelineGraph";

type Props = {
  assets: MediaAsset[];
  projectId: string;
  projectContext?: Record<string, unknown>;
  onGraphChange: (graph: Record<string, unknown>, errors: string[]) => void;
  initialDocument?: TimelineDocument;
  onDocumentChange?: (document: TimelineDocument) => void;
};



const captionPresetLibrary: Array<{ id: string; name: string; style: CaptionStyle }> = [
  { id: "cinematic-fade", name: "Cinematic Fade", style: { preset: "classic", position: "bottom", fontSize: 30, color: "#ffffff", backgroundColor: "#00000000", bold: false, animation: "fade", animationDuration: 0.8 } },
  { id: "social-pop", name: "Social Pop", style: { preset: "bold", position: "bottom", fontSize: 38, color: "#ffffff", backgroundColor: "#101010d9", bold: true, animation: "pop", animationDuration: 0.35 } },
  { id: "karaoke-glow", name: "Karaoke Glow", style: { preset: "neon", position: "bottom", fontSize: 34, color: "#f8fbff", backgroundColor: "#071321c9", bold: true, animation: "karaoke", animationDuration: 0.45 } },
  { id: "minimal-slide", name: "Minimal Slide", style: { preset: "minimal", position: "bottom", fontSize: 26, color: "#ffffff", backgroundColor: "#00000000", bold: false, animation: "slide", animationDuration: 0.55 } },
  { id: "neon-reveal", name: "Neon Reveal", style: { preset: "neon", position: "top", fontSize: 32, color: "#8ef7ff", backgroundColor: "#071321c9", bold: true, animation: "word", animationDuration: 0.7 } },
];

const initial: TimelineDocument = {
  videoClips: [], audioClips: [], captions: [],
  width: 1920, height: 1080, frameRate: 30,
  audioMixer: { dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false }, effects: { gain: 1, muted: false }, master: { gain: 1, muted: false } },
  exportPreset: "1080p", videoBitrate: "12M", ducking: false,
  duckingSettings: { thresholdDb: -24, ratio: 8, attackMs: 20, releaseMs: 450 },
};

export function TimelineComposer({ assets, projectId, projectContext = {}, onGraphChange, initialDocument, onDocumentChange }: Props) {
  const [doc, setDoc] = useState<TimelineDocument>(initialDocument ?? initial);
  const [video, setVideo] = useState({ mediaId: "", sourceStart: "0", duration: "5", timelineStart: "0", trackIndex: "0", transition: "none" as "none" | "fade" | "crossfade" });
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [lockedTracks, setLockedTracks] = useState<Record<string, boolean>>({});
  const [mutedAudioTracks, setMutedAudioTracks] = useState<Record<number, Record<string, number>>>({});
  const [snapGuide, setSnapGuide] = useState<number | null>(null);
  const [audio, setAudio] = useState({ mediaId: "", sourceStart: "0", duration: "5", timelineStart: "0", volume: "1", trackIndex: "0", fadeIn: "0", fadeOut: "0", role: "music" as "dialogue" | "music" | "other" });
  const [caption, setCaption] = useState({ text: "", start: "0", duration: "3" });
  const [captionPresetName, setCaptionPresetName] = useState("");
  const [tab, setTab] = useState<"video" | "audio" | "captions">("video");
  const [playhead, setPlayhead] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [history, setHistory] = useState<TimelineDocument[]>([]);
  const [future, setFuture] = useState<TimelineDocument[]>([]);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [selectedClip, setSelectedClip] = useState<{ id: string; type: "video" | "audio" | "caption" } | null>(null);
  const [clipClipboard, setClipClipboard] = useState<{ type: "video" | "audio" | "caption"; clip: any } | null>(null);
  const [commandText, setCommandText] = useState("");
  const [commandPlan, setCommandPlan] = useState<TimelineCommandPlan | null>(null);
  const [directorPlan, setDirectorPlan] = useState<DirectorPlan | null>(null);
  const [directorTimelinePreview, setDirectorTimelinePreview] = useState<DirectorTimelinePreview | null>(null);
  const [directorTimelineError, setDirectorTimelineError] = useState("");
  const [directorError, setDirectorError] = useState("");
  const [directorLoading, setDirectorLoading] = useState(false);
  const [clipRefinement, setClipRefinement] = useState<{ clipId: string; patch: Record<string, unknown>; summary: string } | null>(null);
  const [sceneSequencePlan, setSceneSequencePlan] = useState<{ nextDocument: TimelineDocument; changes: string[]; warnings: string[] } | null>(null);
  const [visualTransitionPlan, setVisualTransitionPlan] = useState<{ nextDocument: TimelineDocument; findings: string[]; changes: string[]; warnings: string[] } | null>(null);
  const [visualTransitionBusy, setVisualTransitionBusy] = useState(false);
  const [visualTransitionError, setVisualTransitionError] = useState("");
  const [audioIntelligenceBusy, setAudioIntelligenceBusy] = useState(false);
  const [audioIntelligenceError, setAudioIntelligenceError] = useState("");
  const [audioWaveforms, setAudioWaveforms] = useState<Record<string, WaveformData>>({});
  const [audioIntelligenceRan, setAudioIntelligenceRan] = useState(false);
  const [audioMixPlan, setAudioMixPlan] = useState<AudioMixPlan | null>(null);
  const [audioQualityReports, setAudioQualityReports] = useState<Record<string, AudioQualityResult>>({});
  const [audioQualityBusy, setAudioQualityBusy] = useState<Record<string, boolean>>({});
  const [audioQualityErrors, setAudioQualityErrors] = useState<Record<string, string>>({});
  const [captionReport, setCaptionReport] = useState<CaptionIntelligenceReport | null>(null);
  const [transcriptionMediaId, setTranscriptionMediaId] = useState("");
  const [transcriptionLanguage, setTranscriptionLanguage] = useState("auto");
  const [transcription, setTranscription] = useState<TranscriptionResult | null>(null);
  const [transcriptionBusy, setTranscriptionBusy] = useState(false);
  const [transcriptionError, setTranscriptionError] = useState("");
  const [dialoguePlan, setDialoguePlan] = useState<DialogueEditPlan | null>(null);
  const [dialoguePlanBusy, setDialoguePlanBusy] = useState(false);
  const [dialoguePlanError, setDialoguePlanError] = useState("");
  const [smartTimelineStyle, setSmartTimelineStyle] = useState<"balanced" | "dynamic" | "calm">("balanced");
  const [smartTimelineDuration, setSmartTimelineDuration] = useState("30");
  const [smartTimelineShotCap, setSmartTimelineShotCap] = useState("5");
  const [smartTimelineShotFloor, setSmartTimelineShotFloor] = useState("1.5");
  const [smartTimelineBusy, setSmartTimelineBusy] = useState(false);
  const [smartTimelineError, setSmartTimelineError] = useState("");
  const [smartTimelineDraft, setSmartTimelineDraft] = useState<SmartTimelineDraft | null>(null);
  const [beatAnalysis, setBeatAnalysis] = useState<AudioBeatAnalysis | null>(null);
  const [beatAnalysisBusy, setBeatAnalysisBusy] = useState(false);
  const [beatAnalysisTarget, setBeatAnalysisTarget] = useState("");
  const [beatAnalysisError, setBeatAnalysisError] = useState("");
  const [showMusicTransitionSuggestions, setShowMusicTransitionSuggestions] = useState(false);

  const selectedVideo = selectedClip?.type === "video" ? doc.videoClips.find((x) => x.id === selectedClip.id) : undefined;
  const selectedAudio = selectedClip?.type === "audio" ? doc.audioClips.find((x) => x.id === selectedClip.id) : undefined;
  const selectedCaption = selectedClip?.type === "caption" ? doc.captions.find((x) => x.id === selectedClip.id) : undefined;
  const patchSelected = (patch: Record<string, unknown>) => {
    if (!selectedClip) return;
    if (selectedClip.type === "video") update({ ...doc, videoClips: doc.videoClips.map((x) => x.id === selectedClip.id ? { ...x, ...patch } : x) });
    if (selectedClip.type === "audio") update({ ...doc, audioClips: doc.audioClips.map((x) => x.id === selectedClip.id ? { ...x, ...patch } : x) });
    if (selectedClip.type === "caption") update({ ...doc, captions: doc.captions.map((x) => x.id === selectedClip.id ? { ...x, ...patch } : x) });
  };
  const numberValue = (value: string, fallback: number, minimum = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.max(minimum, parsed) : fallback;
  };

  const updateSelectedAudioKeyframes = (keyframes: Array<{ time: number; volume: number }>) => {
    if (!selectedAudio) return;
    patchSelected({ volumeKeyframes: keyframes });
  };
  const addAudioVolumeKeyframe = () => {
    if (!selectedAudio) return;
    const time = Math.min(selectedAudio.duration, Math.max(0, playhead - selectedAudio.timelineStart));
    const keyframes = [...(selectedAudio.volumeKeyframes ?? [])];
    const existing = keyframes.findIndex((point) => Math.abs(point.time - time) < 0.001);
    if (existing >= 0) keyframes[existing] = { time, volume: selectedAudio.volume };
    else keyframes.push({ time, volume: selectedAudio.volume });
    keyframes.sort((a, b) => a.time - b.time);
    updateSelectedAudioKeyframes(keyframes);
  };

  const proposeClipRefinement = (patch: Record<string, unknown>, summary: string) => {
    if (!selectedVideo) return;
    setClipRefinement({ clipId: selectedVideo.id, patch, summary });
  };
  const applyClipRefinement = () => {
    if (!clipRefinement || selectedClip?.type !== "video" || selectedClip.id !== clipRefinement.clipId) return;
    patchSelected(clipRefinement.patch);
    setClipRefinement(null);
  };

  const errors = useMemo(() => validateTimelineDocument(doc), [doc]);
  const graph = useMemo(() => buildRenderGraph(doc), [doc]);
  const duration = getTimelineDuration(doc);
  const timelineIntelligence = useMemo(() => analyzeTimeline(doc, assets), [doc, assets]);
  const timelineQuality = useMemo(() => analyzeTimelineQuality(doc, assets), [doc, assets]);
  const audioIntelligence = useMemo(() => analyzeAudioWaveforms(doc.audioClips, audioWaveforms), [doc.audioClips, audioWaveforms]);
  const captionIntelligence = useMemo(() => analyzeCaptionTiming(doc), [doc]);

  const analyzeSceneSequence = () => {
    const nextDocument: TimelineDocument = {
      ...doc,
      videoClips: doc.videoClips.map((clip) => ({ ...clip })),
    };
    const changes: string[] = [];
    const warnings: string[] = [];
    const tracks = [...new Set(doc.videoClips.map((clip) => clip.trackIndex))].sort((a, b) => a - b);
    for (const trackIndex of tracks) {
      const ordered = nextDocument.videoClips
        .filter((clip) => clip.trackIndex === trackIndex)
        .sort((a, b) => a.timelineStart - b.timelineStart);
      for (let index = 1; index < ordered.length; index += 1) {
        const previous = ordered[index - 1];
        const current = ordered[index];
        const previousEnd = previous.timelineStart + previous.duration;
        const gap = current.timelineStart - previousEnd;
        if (gap > 0.15 && gap <= 3) {
          current.timelineStart = previousEnd;
          changes.push(`Close ${gap.toFixed(1)}s gap before ${assets.find((asset) => asset.id === current.mediaId)?.filename ?? "the next shot"} on track ${trackIndex + 1}`);
        } else if (gap > 3) {
          warnings.push(`Large ${gap.toFixed(1)}s gap before ${assets.find((asset) => asset.id === current.mediaId)?.filename ?? "the next shot"} on track ${trackIndex + 1} was left unchanged`);
        } else if (gap < -0.15) {
          warnings.push(`Overlap of ${Math.abs(gap).toFixed(1)}s between neighboring shots on track ${trackIndex + 1} needs manual review`);
        } else if (Math.abs(gap) <= 0.15 && current.transition === "none") {
          current.transition = "fade";
          changes.push(`Add a fade transition before ${assets.find((asset) => asset.id === current.mediaId)?.filename ?? "the next shot"} on track ${trackIndex + 1}`);
        }
      }
    }
    if (changes.length === 0 && warnings.length === 0) warnings.push("No obvious gaps, overlaps, or missing transitions were found");
    setSceneSequencePlan({ nextDocument, changes, warnings });
  };
  const applySceneSequencePlan = () => {
    if (!sceneSequencePlan || sceneSequencePlan.changes.length === 0) return;
    update(sceneSequencePlan.nextDocument);
    setSceneSequencePlan(null);
  };

  const applyAudioMixPlan = () => {
    if (!audioMixPlan || audioMixPlan.changes.length === 0) return;
    let nextDocument: TimelineDocument = {
      ...doc,
      audioClips: doc.audioClips.map((clip) => ({ ...clip })),
    };
    for (const change of audioMixPlan.changes) {
      if (change.enableDucking) nextDocument.ducking = true;
      if (change.clipId && change.patch) {
        nextDocument.audioClips = nextDocument.audioClips.map((clip) =>
          clip.id === change.clipId ? { ...clip, ...change.patch } : clip);
      }
    }
    const invalidFades = nextDocument.audioClips.some((clip) =>
      clip.fadeIn < 0 || clip.fadeOut < 0 || clip.fadeIn + clip.fadeOut > clip.duration);
    if (invalidFades) {
      setAudioIntelligenceError("The proposed fades exceed an audio clip's duration. No changes were applied.");
      return;
    }
    update(nextDocument);
    setAudioMixPlan(null);
  };

  const runBeatAnalysis = async (mediaId: string) => {
    if (beatAnalysisBusy) return;
    setBeatAnalysisBusy(true);
    setBeatAnalysisTarget(mediaId);
    setBeatAnalysisError("");
    try {
      const result = await requestAudioBeatAnalysis(projectId, mediaId);
      setBeatAnalysis(result);
      setSmartTimelineDraft(null);
    } catch (cause) {
      setBeatAnalysisError(cause instanceof Error ? cause.message : "Beat analysis failed.");
    } finally {
      setBeatAnalysisBusy(false);
      setBeatAnalysisTarget("");
    }
  };

  const runSmartTimeline = async () => {
    if (smartTimelineBusy) return;
    const targetDuration = Number(smartTimelineDuration);
    if (!Number.isFinite(targetDuration) || targetDuration < 1 || targetDuration > 600) {
      setSmartTimelineError("Choose a target duration from 1 to 600 seconds.");
      return;
    }
    const shotCap = Number(smartTimelineShotCap);
    if (!Number.isFinite(shotCap) || shotCap < 0.5 || shotCap > 15) {
      setSmartTimelineError("Choose a maximum shot length from 0.5 to 15 seconds.");
      return;
    }
    const shotFloor = Number(smartTimelineShotFloor);
    if (!Number.isFinite(shotFloor) || shotFloor < 0.5 || shotFloor > 10 || shotFloor > shotCap) {
      setSmartTimelineError("Choose a minimum shot length from 0.5 to 10 seconds, no greater than the maximum.");
      return;
    }
    const videos = assets.filter((asset) => asset.mime_type.startsWith("video/"));
    if (!videos.length) {
      setSmartTimelineError("Import at least one video before generating a Smart Timeline.");
      return;
    }
    setSmartTimelineBusy(true);
    setSmartTimelineError("");
    setSmartTimelineDraft(null);
    try {
      const sceneResults = await Promise.all(videos.map(async (asset) => {
        const result = await mediaApi.detectScenes(projectId, asset.id, 50, true);
        return { assetId: asset.id, scenes: result.scenes.map((scene) => ({
          start: scene.start,
          ...(typeof scene.visual_interest === "number" ? { visual_interest: scene.visual_interest } : {}),
          ...(scene.visual_evidence ? { visual_evidence: scene.visual_evidence } : {}),
        })) };
      }));
      const scenesByAsset = new Map(sceneResults.map((item) => [item.assetId, item.scenes]));
      // Transcript timestamps are source-media-relative. Only attach them when
      // their source is unambiguous (a single video matching the transcript).
      const transcriptSegments = videos.length === 1 && transcription?.media_id === videos[0].id
        ? transcription.segments
            .filter((segment) => Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end > segment.start && segment.text.trim())
            .map(({ start, end, text }) => ({ start, end, text }))
        : [];
      const draft = await requestSmartTimeline({
        assets: assets.map((asset) => ({
          id: asset.id,
          name: asset.filename,
          type: asset.mime_type.startsWith("video/") ? "video" : asset.mime_type.startsWith("audio/") ? "audio" : "image",
          duration: asset.duration,
          scenes: scenesByAsset.get(asset.id) ?? [],
        })),
        transcriptSegments,
        targetDuration,
        style: smartTimelineStyle,
        maxShotDuration: Number(smartTimelineShotCap),
        minShotDuration: Number(smartTimelineShotFloor),
        beatTimes: beatAnalysis?.beats ?? [],
      });
      const validation = validateSmartTimelineDraft(draft, assets.map((asset) => ({
        id: asset.id,
        type: asset.mime_type.startsWith("video/") ? "video" : asset.mime_type.startsWith("audio/") ? "audio" : "image",
        duration: asset.duration,
      })), targetDuration);
      if (!validation.valid) throw new Error(`Smart Timeline returned an unsafe draft: ${validation.errors.join(" ")}`);
      setSmartTimelineDraft(draft);
      if (!draft.clips.length) setSmartTimelineError(draft.warnings.join(" ") || "No usable video shots were found.");
    } catch (cause) {
      setSmartTimelineError(cause instanceof Error ? cause.message : "Smart Timeline could not generate a draft.");
    } finally {
      setSmartTimelineBusy(false);
    }
  };

  const applySmartTimelineDraft = () => {
    if (!smartTimelineDraft?.clips.length) return;
    const validation = validateSmartTimelineDraft(smartTimelineDraft, assets.map((asset) => ({
      id: asset.id,
      type: asset.mime_type.startsWith("video/") ? "video" : asset.mime_type.startsWith("audio/") ? "audio" : "image",
      duration: asset.duration,
    })), Number(smartTimelineDuration));
    if (!validation.valid) {
      setSmartTimelineError(`Draft cannot be applied: ${validation.errors.join(" ")}`);
      setSmartTimelineDraft(null);
      return;
    }
    const videoClips = smartTimelineDraft.clips.map((clip, index) => ({
      id: `smart-${Date.now()}-${index}`,
      mediaId: clip.assetId,
      sourceStart: clip.sourceStart,
      duration: clip.duration,
      timelineStart: clip.start,
      trackIndex: 0,
      transition: (clip.transition === "fade" || clip.transition === "crossfade" ? clip.transition : "none") as "none" | "fade" | "crossfade",
    }));
    const audioClips = smartTimelineDraft.audio_clips.map((clip, index) => ({
      id: `smart-audio-${Date.now()}-${index}`,
      mediaId: clip.assetId,
      sourceStart: clip.sourceStart,
      duration: clip.duration,
      timelineStart: clip.start,
      trackIndex: 0,
      volume: Math.max(0, Math.min(2, clip.volume)),
      fadeIn: 0,
      fadeOut: 0,
      role: "music" as const,
    }));
    update({ ...doc, videoClips, audioClips: audioClips.length ? audioClips : doc.audioClips });
    setSmartTimelineDraft(null);
    setSelectedClip(null);
    setPlayhead(0);
  };

  const runCalibratedAudioAnalysis = async (mediaId: string) => {
    if (audioQualityBusy[mediaId]) return;
    setAudioQualityBusy((current) => ({ ...current, [mediaId]: true }));
    setAudioQualityErrors((current) => ({ ...current, [mediaId]: "" }));
    try {
      const report = await mediaApi.audioQuality(projectId, mediaId);
      setAudioQualityReports((current) => ({ ...current, [mediaId]: report }));
    } catch (cause) {
      setAudioQualityErrors((current) => ({ ...current, [mediaId]: cause instanceof Error ? cause.message : "Loudness analysis failed." }));
    } finally {
      setAudioQualityBusy((current) => ({ ...current, [mediaId]: false }));
    }
  };

  const runAudioIntelligence = async () => {
    if (audioIntelligenceBusy) return;
    setAudioIntelligenceBusy(true);
    setAudioIntelligenceError("");
    try {
      const mediaIds = [...new Set(doc.audioClips.map((clip) => clip.mediaId))];
      const results = await Promise.all(mediaIds.map(async (mediaId) => {
        try { return [mediaId, await mediaApi.waveform(projectId, mediaId)] as const; }
        catch { return [mediaId, null] as const; }
      }));
      const available = Object.fromEntries(results.filter((item): item is readonly [string, WaveformData] => item[1] !== null));
      setAudioWaveforms(available);
      setAudioIntelligenceRan(true);
      setAudioMixPlan(recommendAudioMix(doc, analyzeAudioWaveforms(doc.audioClips, available).profiles));
      if (!Object.keys(available).length) setAudioIntelligenceError("No audio waveforms could be generated. Check that the media contains decodable audio.");
    } catch (cause) {
      setAudioIntelligenceError(cause instanceof Error ? cause.message : "Audio analysis could not be completed.");
    } finally {
      setAudioIntelligenceBusy(false);
    }
  };

  const runTranscription = async () => {
    if (!transcriptionMediaId || transcriptionBusy) return;
    setTranscriptionBusy(true);
    setTranscriptionError("");
    setTranscription(null);
    try {
      const result = await mediaApi.transcribeWithLanguage(projectId, transcriptionMediaId, transcriptionLanguage);
      if (!result.segments?.length) throw new Error("The speech provider returned no timestamped segments.");
      setTranscription(result);
    } catch (cause) {
      setTranscriptionError(cause instanceof Error ? cause.message : "Transcription could not be completed.");
    } finally {
      setTranscriptionBusy(false);
    }
  };

  const runDialoguePlanning = async () => {
    if (!transcription?.segments?.length || dialoguePlanBusy) return;
    setDialoguePlanBusy(true); setDialoguePlanError(""); setDialoguePlan(null);
    try { setDialoguePlan(await mediaApi.dialogueEditPlan(transcription.segments)); }
    catch (cause) { setDialoguePlanError(cause instanceof Error ? cause.message : "Dialogue planning could not be completed."); }
    finally { setDialoguePlanBusy(false); }
  };

  const applyDialogueCut = (sourceTime: number) => {
    if (!transcriptionMediaId || !Number.isFinite(sourceTime)) return;
    const matching = doc.videoClips.filter((clip) => {
      if (clip.mediaId !== transcriptionMediaId) return false;
      const offset = sourceTime - clip.sourceStart;
      return offset > 0.1 && offset < clip.duration - 0.1;
    });
    if (!matching.length) {
      setDialoguePlanError("No matching video clip contains this source timestamp. Add the transcribed media to the timeline or review the marker manually.");
      return;
    }
    const splitIds = new Set(matching.map((clip) => clip.id));
    const nextClips = doc.videoClips.flatMap((clip) => {
      if (!splitIds.has(clip.id)) return [clip];
      const offset = sourceTime - clip.sourceStart;
      const first = { ...clip, duration: offset };
      const second = { ...clip, id: `v-dialogue-${Date.now()}-${clip.id}`, sourceStart: sourceTime,
        timelineStart: clip.timelineStart + offset, duration: clip.duration - offset };
      return [first, second];
    });
    update({ ...doc, videoClips: nextClips });
    setPlayhead(matching[0].timelineStart + (sourceTime - matching[0].sourceStart));
    setDialoguePlanError("");
  };

  const applyDialoguePauseTrims = () => {
    if (!dialoguePlan || !transcriptionMediaId) return;
    const boundaries = dialoguePlan.cut_candidates.filter((item) => item.reason === "long_pause");
    if (!boundaries.length) {
      setDialoguePlanError("No long-pause boundaries are available to trim. Analyze dialogue first or lower the pause threshold.");
      return;
    }
    let changedClips = 0;
    let removedSeconds = 0;
    let nextAudioClips = [...doc.audioClips];
    let nextCaptions = [...doc.captions];
    const nextVideoClips = doc.videoClips.flatMap((clip) => {
      if (clip.mediaId !== transcriptionMediaId) return [clip];
      const result = trimDialoguePauses(clip, boundaries, 0.12);
      if (!result.changed) return [clip];
      changedClips += 1;
      removedSeconds += result.removedSeconds;
      const synced = synchronizeDialogueAfterTrim(clip, result.clips, nextAudioClips, nextCaptions);
      nextAudioClips = synced.audioClips;
      nextCaptions = synced.captions;
      if (synced.warnings.length) setDialoguePlanError(synced.warnings.join(" "));
      return result.clips;
    });
    if (!changedClips) {
      setDialoguePlanError("No matching long pauses fall inside the selected media's current timeline clips.");
      return;
    }
    update({ ...doc, videoClips: nextVideoClips, audioClips: nextAudioClips, captions: nextCaptions });
    setPlayhead(0);
    setSelectedClip(null);
    setDialoguePlanError((current) => `${current ? `${current} ` : ""}Trimmed ${changedClips} clip(s), removing ${removedSeconds.toFixed(2)} seconds of reviewed pauses. Dialogue audio and caption timing were synchronized where possible. Use Undo to restore the previous timeline.`);
  };

  const downloadTranscription = async (format: "srt" | "vtt") => {
    if (!transcription?.segments?.length) return;
    try {
      const blob = await mediaApi.exportSubtitles(transcription.segments, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `flexy-captions.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setTranscriptionError(cause instanceof Error ? cause.message : "Subtitle export could not be completed.");
    }
  };

  const importTranscription = () => {
    if (!transcription?.segments?.length) return;
    const existing = new Set(doc.captions.map((item) => item.id));
    const videoUse = doc.videoClips.filter((clip) => clip.mediaId === transcription.media_id)
      .sort((a, b) => a.timelineStart - b.timelineStart)[0];
    const audioUse = doc.audioClips.filter((clip) => clip.mediaId === transcription.media_id)
      .sort((a, b) => a.timelineStart - b.timelineStart)[0];
    const sourceUse = videoUse ?? audioUse;
    const timelineOffset = sourceUse ? sourceUse.timelineStart - sourceUse.sourceStart : 0;
    const sourceStart = sourceUse?.sourceStart ?? 0;
    const sourceEnd = sourceUse ? sourceStart + sourceUse.duration : Infinity;
    const captionCues = buildSpeechCaptionCues(transcription.segments);
    const importId = Date.now();
    const imported = captionCues.map((cue, index) => {
      const start = Math.max(cue.start, sourceStart);
      const end = Math.min(cue.end, sourceEnd);
      return {
        id: `speech-${importId}-${index}`,
        text: cue.text,
        start: Math.max(0, start + timelineOffset),
        duration: Math.max(0, end - start),
      };
    }).filter((item) => item.duration > 0.1 && !existing.has(item.id));
    if (!imported.length) return;
    update({ ...doc, captions: [...doc.captions, ...imported] });
    setTranscription(null);
    setTab("captions");
  };

  const applyCaptionTimingPlan = () => {
    if (!captionReport || captionReport.changes.length === 0) return;
    const nextDocument: TimelineDocument = {
      ...doc,
      captions: doc.captions.map((caption) => {
        const change = captionReport.changes.find((item) => item.captionId === caption.id);
        return change ? { ...caption, ...change.patch } : { ...caption };
      }),
    };
    if (nextDocument.captions.some((item) => item.start < 0 || item.duration <= 0)) return;
    update(nextDocument);
    setCaptionReport(null);
  };

  const analyzeVisualTransitions = async () => {
    if (visualTransitionBusy) return;
    setVisualTransitionBusy(true);
    setVisualTransitionError("");
    setVisualTransitionPlan(null);
    const nextDocument: TimelineDocument = { ...doc, videoClips: doc.videoClips.map((clip) => ({ ...clip })) };
    const findings: string[] = [];
    const changes: string[] = [];
    const warnings: string[] = [];
    const tracks = [...new Set(doc.videoClips.map((clip) => clip.trackIndex))];
    const loadProfile = async (mediaId: string, timestamp: number) => {
      const asset = assets.find((item) => item.id === mediaId);
      if (!asset) return null;
      const url = await mediaApi.preview(projectId, asset, timestamp);
      if (!url) return null;
      try {
        const image = new Image();
        image.src = url;
        const loaded = await new Promise<boolean>((resolve) => {
          image.onload = () => resolve(true);
          image.onerror = () => resolve(false);
        });
        return loaded ? analyzePreviewPixels(image) : null;
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    try {
      for (const trackIndex of tracks) {
        const ordered = nextDocument.videoClips
          .filter((clip) => clip.trackIndex === trackIndex)
          .sort((a, b) => a.timelineStart - b.timelineStart);
        for (let index = 1; index < ordered.length; index += 1) {
          const previous = ordered[index - 1];
          const current = ordered[index];
          const gap = current.timelineStart - (previous.timelineStart + previous.duration);
          if (Math.abs(gap) > 0.15) {
            warnings.push(`Skipped non-adjacent shots on track ${trackIndex + 1}; close gaps or review overlaps first`);
            continue;
          }
          const previousAsset = assets.find((asset) => asset.id === previous.mediaId);
          const currentAsset = assets.find((asset) => asset.id === current.mediaId);
          if (!previousAsset || !currentAsset) {
            warnings.push(`Could not find media for a neighboring shot on track ${trackIndex + 1}`);
            continue;
          }
          const previousEnd = Math.max(0, previous.sourceStart + previous.duration - 0.1);
          const currentStart = current.sourceStart + 0.1;
          const [left, right] = await Promise.all([
            loadProfile(previous.mediaId, previousEnd),
            loadProfile(current.mediaId, currentStart),
          ]);
          if (!left || !right) {
            warnings.push(`Could not sample both boundary frames for ${previousAsset.filename} and ${currentAsset.filename}`);
            continue;
          }
          const brightnessDelta = Math.abs(left.brightness - right.brightness);
          const contrastDelta = Math.abs(left.contrast - right.contrast);
          const colorDelta = Math.abs(left.colorfulness - right.colorfulness);
          const toneDelta = left.tone === right.tone ? 0 : 12;
          const difference = Math.round(brightnessDelta * 0.45 + contrastDelta * 0.2 + colorDelta * 0.2 + toneDelta * 0.15);
          const level = difference >= 22 ? "high" : difference >= 10 ? "moderate" : "low";
          findings.push(`${previousAsset.filename} → ${currentAsset.filename}: ${level} visual difference (${difference}/100)`);
          if (current.transition === "none" && difference >= 22) {
            current.transition = "crossfade";
            changes.push(`Suggest crossfade between ${previousAsset.filename} and ${currentAsset.filename}`);
          } else if (current.transition === "none" && difference >= 10) {
            current.transition = "fade";
            changes.push(`Suggest fade between ${previousAsset.filename} and ${currentAsset.filename}`);
          }
        }
      }
      if (!findings.length) warnings.push("No adjacent shot pairs could be visually compared");
      setVisualTransitionPlan({ nextDocument, findings, changes, warnings });
    } catch (cause) {
      setVisualTransitionError(cause instanceof Error ? cause.message : "Could not analyze neighboring frame previews");
    } finally {
      setVisualTransitionBusy(false);
    }
  };
  const applyVisualTransitionPlan = () => {
    if (!visualTransitionPlan || visualTransitionPlan.changes.length === 0) return;
    update(visualTransitionPlan.nextDocument);
    setVisualTransitionPlan(null);
  };

  const trackNames = doc.trackNames ?? {};
  const trackColors = doc.trackColors ?? {};
  const updateTrackMeta = (key: string, patch: { name?: string; color?: string }) => {
    update({ ...doc,
      trackNames: patch.name !== undefined ? { ...trackNames, [key]: patch.name.slice(0, 32) } : trackNames,
      trackColors: patch.color !== undefined ? { ...trackColors, [key]: patch.color } : trackColors,
    });
  };
  const hiddenVideoTracks = doc.hiddenVideoTracks ?? [];
  const hiddenAudioTracks = doc.hiddenAudioTracks ?? [];
  const captionsHidden = !!doc.captionsHidden;
  const toggleTrackVisibility = (kind: "video" | "audio" | "captions", trackIndex?: number) => {
    if (kind === "video" && trackIndex !== undefined) {
      const next = hiddenVideoTracks.includes(trackIndex) ? hiddenVideoTracks.filter((x) => x !== trackIndex) : [...hiddenVideoTracks, trackIndex];
      update({ ...doc, hiddenVideoTracks: next });
    } else if (kind === "audio" && trackIndex !== undefined) {
      const next = hiddenAudioTracks.includes(trackIndex) ? hiddenAudioTracks.filter((x) => x !== trackIndex) : [...hiddenAudioTracks, trackIndex];
      update({ ...doc, hiddenAudioTracks: next });
    } else {
      update({ ...doc, captionsHidden: !captionsHidden });
    }
  };
  const toggleAudioTrackSolo = (trackIndex: number) => {
    update({ ...doc, soloAudioTrack: doc.soloAudioTrack === trackIndex ? null : trackIndex });
  };

  const toggleTrackLock = (key: string) => setLockedTracks((current) => ({ ...current, [key]: !current[key] }));
  const toggleAudioTrackMute = (trackIndex: number) => {
    const saved = mutedAudioTracks[trackIndex];
    if (saved) {
      const restored = doc.audioClips.map((clip) => clip.trackIndex === trackIndex && saved[clip.id] !== undefined
        ? { ...clip, volume: saved[clip.id] } : clip);
      update({ ...doc, audioClips: restored });
      setMutedAudioTracks((current) => { const next = { ...current }; delete next[trackIndex]; return next; });
      return;
    }
    const volumes = Object.fromEntries(doc.audioClips.filter((clip) => clip.trackIndex === trackIndex).map((clip) => [clip.id, clip.volume]));
    if (!Object.keys(volumes).length) return;
    update({ ...doc, audioClips: doc.audioClips.map((clip) => clip.trackIndex === trackIndex ? { ...clip, volume: 0 } : clip) });
    setMutedAudioTracks((current) => ({ ...current, [trackIndex]: volumes }));
  };

  const updateAudioBus = (bus: "dialogue" | "music" | "effects" | "master", patch: { gain?: number; muted?: boolean }) => {
    const current = doc.audioMixer ?? { dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false }, effects: { gain: 1, muted: false }, master: { gain: 1, muted: false } };
    update({ ...doc, audioMixer: { ...current, [bus]: { ...current[bus], ...patch } } });
  };

  const update = (next: TimelineDocument) => {
    setHistory((items) => [...items.slice(-49), doc]);
    setFuture([]);
    setDoc(next);
    onDocumentChange?.(next);
    const nextErrors = validateTimelineDocument(next);
    onGraphChange(buildRenderGraph(next), nextErrors);
  };

  const applyCaptionStylePreset = (style: CaptionStyle) => {
    if (!selectedCaption) return;
    patchSelected({ style: { ...(selectedCaption.style ?? {}), ...style } });
  };
  const saveCaptionStylePreset = () => {
    if (!selectedCaption) return;
    const name = captionPresetName.trim();
    if (!name) return;
    const preset: SavedCaptionPreset = {
      id: `custom-${Date.now()}`,
      name: name.slice(0, 32),
      style: { preset: "classic", position: "bottom", fontSize: 28, color: "#ffffff", backgroundColor: "#000000b8", bold: true, ...(selectedCaption.style ?? {}) },
    };
    update({ ...doc, captionPresets: [...(doc.captionPresets ?? []).filter((item) => item.name.toLowerCase() !== preset.name.toLowerCase()), preset] });
    setCaptionPresetName("");
  };

  const addVideo = () => {
    const clip = {
      id: `v-${Date.now()}`, mediaId: video.mediaId.trim(),
      sourceStart: Number(video.sourceStart), duration: Number(video.duration),
      timelineStart: Number(video.timelineStart), trackIndex: Number(video.trackIndex),
      transition: video.transition,
    };
    update({ ...doc, videoClips: [...doc.videoClips, clip] });
  };
  const addAudio = () => {
    const clip = {
      id: `a-${Date.now()}`, mediaId: audio.mediaId.trim(),
      sourceStart: Number(audio.sourceStart), duration: Number(audio.duration),
      timelineStart: Number(audio.timelineStart), trackIndex: Number(audio.trackIndex), volume: Number(audio.volume),
      fadeIn: Number(audio.fadeIn), fadeOut: Number(audio.fadeOut), role: audio.role,
      bus: audio.role === "other" ? "effects" : audio.role,
    };
    update({ ...doc, audioClips: [...doc.audioClips, clip] });
  };
  const addCaption = () => {
    const item = { id: `c-${Date.now()}`, text: caption.text, start: Number(caption.start), duration: Number(caption.duration) };
    update({ ...doc, captions: [...doc.captions, item] });
    setCaption({ text: "", start: String(Number(caption.start) + Number(caption.duration)), duration: "3" });
  };

  const remove = (id: string, type: "video" | "audio" | "caption") => {
    if (type === "video") update({ ...doc, videoClips: doc.videoClips.filter((x) => x.id !== id) });
    if (type === "audio") update({ ...doc, audioClips: doc.audioClips.filter((x) => x.id !== id) });
    if (type === "caption") update({ ...doc, captions: doc.captions.filter((x) => x.id !== id) });
  };

  const copySelectedClip = () => {
    if (!selectedClip) return;
    const clip = selectedClip.type === "video" ? doc.videoClips.find((item) => item.id === selectedClip.id)
      : selectedClip.type === "audio" ? doc.audioClips.find((item) => item.id === selectedClip.id)
      : doc.captions.find((item) => item.id === selectedClip.id);
    if (clip) setClipClipboard({ type: selectedClip.type, clip: { ...clip } });
  };
  const pasteClip = () => {
    if (!clipClipboard) return;
    const id = `${clipClipboard.type === "video" ? "v" : clipClipboard.type === "audio" ? "a" : "c"}-${Date.now()}`;
    if (clipClipboard.type === "video") {
      const clip = { ...clipClipboard.clip, id, timelineStart: playhead };
      update({ ...doc, videoClips: [...doc.videoClips, clip] });
    } else if (clipClipboard.type === "audio") {
      const clip = { ...clipClipboard.clip, id, timelineStart: playhead };
      update({ ...doc, audioClips: [...doc.audioClips, clip] });
    } else {
      const clip = { ...clipClipboard.clip, id, start: playhead };
      update({ ...doc, captions: [...doc.captions, clip] });
    }
    setSelectedClip({ id, type: clipClipboard.type });
  };
  const duplicateSelectedClip = () => {
    if (!selectedClip) return;
    const source = selectedClip.type === "video" ? doc.videoClips.find((item) => item.id === selectedClip.id)
      : selectedClip.type === "audio" ? doc.audioClips.find((item) => item.id === selectedClip.id)
      : doc.captions.find((item) => item.id === selectedClip.id);
    if (!source) return;
    setClipClipboard({ type: selectedClip.type, clip: { ...source } });
    const id = `${selectedClip.type === "video" ? "v" : selectedClip.type === "audio" ? "a" : "c"}-${Date.now()}`;
    if (selectedClip.type === "video") {
      const clip = source as typeof doc.videoClips[number];
      update({ ...doc, videoClips: [...doc.videoClips, { ...clip, id, timelineStart: clip.timelineStart + clip.duration }] });
    } else if (selectedClip.type === "audio") {
      const clip = source as typeof doc.audioClips[number];
      update({ ...doc, audioClips: [...doc.audioClips, { ...clip, id, timelineStart: clip.timelineStart + clip.duration }] });
    } else {
      const clip = source as typeof doc.captions[number];
      update({ ...doc, captions: [...doc.captions, { ...clip, id, start: clip.start + clip.duration }] });
    }
    setSelectedClip({ id, type: selectedClip.type });
  };

  const editVideo = (id: string, start: number, sourceStart: number, clipDuration: number) => {
    update({ ...doc, videoClips: doc.videoClips.map((x) => x.id === id
      ? { ...x, timelineStart: Math.max(0, start), sourceStart: Math.max(0, sourceStart), duration: Math.max(0.1, clipDuration) } : x) });
  };
  const editAudio = (id: string, start: number, sourceStart: number, clipDuration: number) => {
    update({ ...doc, audioClips: doc.audioClips.map((x) => x.id === id
      ? { ...x, timelineStart: Math.max(0, start), sourceStart: Math.max(0, sourceStart), duration: Math.max(0.1, clipDuration) } : x) });
  };
  const editCaption = (id: string, start: number, clipDuration: number) => {
    update({ ...doc, captions: doc.captions.map((x) => x.id === id
      ? { ...x, start: Math.max(0, start), duration: Math.max(0.1, clipDuration) } : x) });
  };
  const splitVideo = (id: string, at: number) => {
    const clip = doc.videoClips.find((x) => x.id === id);
    if (!clip || at <= clip.timelineStart + 0.1 || at >= clip.timelineStart + clip.duration - 0.1) return;
    const firstDuration = at - clip.timelineStart;
    const second = { ...clip, id: `v-${Date.now()}`, sourceStart: clip.sourceStart + firstDuration,
      timelineStart: at, duration: clip.duration - firstDuration };
    update({ ...doc, videoClips: [...doc.videoClips.map((x) => x.id === id ? { ...x, duration: firstDuration } : x), second] });
  };
  const splitAudio = (id: string, at: number) => {
    const clip = doc.audioClips.find((x) => x.id === id);
    if (!clip || at <= clip.timelineStart + 0.1 || at >= clip.timelineStart + clip.duration - 0.1) return;
    const firstDuration = at - clip.timelineStart;
    const second = { ...clip, id: `a-${Date.now()}`, sourceStart: clip.sourceStart + firstDuration,
      timelineStart: at, duration: clip.duration - firstDuration };
    update({ ...doc, audioClips: [...doc.audioClips.map((x) => x.id === id ? { ...x, duration: firstDuration } : x), second] });
  };
  const splitCaption = (id: string, at: number) => {
    const clip = doc.captions.find((x) => x.id === id);
    if (!clip || at <= clip.start + 0.1 || at >= clip.start + clip.duration - 0.1) return;
    const firstDuration = at - clip.start;
    const second = { ...clip, id: `c-${Date.now()}`, start: at, duration: clip.duration - firstDuration };
    update({ ...doc, captions: [...doc.captions.map((x) => x.id === id ? { ...x, duration: firstDuration } : x), second] });
  };

  const undo = () => {
    if (!history.length) return;
    const previous = history[history.length - 1];
    setHistory((items) => items.slice(0, -1));
    setFuture((items) => [doc, ...items].slice(0, 50));
    setDoc(previous);
    onDocumentChange?.(previous);
    onGraphChange(buildRenderGraph(previous), validateTimelineDocument(previous));
  };
  const redo = () => {
    if (!future.length) return;
    const next = future[0];
    setFuture((items) => items.slice(1));
    setHistory((items) => [...items.slice(-49), doc]);
    setDoc(next);
    onDocumentChange?.(next);
    onGraphChange(buildRenderGraph(next), validateTimelineDocument(next));
  };
  const frameStep = (direction: number) => setPlayhead((value) =>
    Math.max(0, Math.min(duration, value + direction / doc.frameRate)));
  // Beat timestamps are relative to the analyzed source asset. Project them onto
  // every matching timeline audio instance, accounting for its source in-point.
  const beatTimelineMarkers = useMemo(() => beatAnalysis
    ? projectBeatMarkers(beatAnalysis.beats, doc.audioClips, beatAnalysis.media_id)
    : [], [beatAnalysis, doc.audioClips]);

  const musicTransitionSuggestions = useMemo(
    () => proposeMusicTransitions(doc.videoClips, beatTimelineMarkers),
    [doc.videoClips, beatTimelineMarkers],
  );
  const applyMusicTransitionSuggestions = () => {
    if (!musicTransitionSuggestions.length) return;
    const byClip = new Map(musicTransitionSuggestions.map((item) => [item.clipId, item.transition]));
    update({
      ...doc,
      videoClips: doc.videoClips.map((clip) => byClip.has(clip.id)
        ? { ...clip, transition: byClip.get(clip.id)! }
        : clip),
    });
    setShowMusicTransitionSuggestions(false);
  };

  const snapPoints = useMemo(() => {
    const points = [0, playhead, ...beatTimelineMarkers];
    doc.videoClips.forEach((clip) => points.push(clip.timelineStart, clip.timelineStart + clip.duration));
    doc.audioClips.forEach((clip) => points.push(clip.timelineStart, clip.timelineStart + clip.duration));
    doc.captions.forEach((clip) => points.push(clip.start, clip.start + clip.duration));
    return [...new Set(points.filter(Number.isFinite))];
  }, [doc, playhead, beatTimelineMarkers]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || target?.isContentEditable) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "c") {
        event.preventDefault(); copySelectedClip();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "v") {
        event.preventDefault(); pasteClip();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
        event.preventDefault(); duplicateSelectedClip();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault(); if (event.shiftKey) redo(); else undo();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault(); redo();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault(); frameStep(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault(); frameStep(1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const runCommand = async (rawCommand: string) => {
    const trimmed = rawCommand.trim();
    if (!trimmed || directorLoading) return;

    // Selected-shot commands are local, deterministic proposals requiring approval.
    if (selectedVideo) {
      const normalized = trimmed.toLowerCase();
      const seconds = normalized.match(/(\\d+(?:\\.\\d+)?)\\s*(?:s|sec|secs|second|seconds)\\b/);
      const amount = seconds ? Number(seconds[1]) : 0.5;
      const orderedVideo = [...doc.videoClips].sort((a, b) => a.timelineStart - b.timelineStart);
      const selectedIndex = orderedVideo.findIndex((clip) => clip.id === selectedVideo.id);
      const previousShot = selectedIndex > 0 ? orderedVideo[selectedIndex - 1] : undefined;
      const nextShot = selectedIndex >= 0 && selectedIndex < orderedVideo.length - 1 ? orderedVideo[selectedIndex + 1] : undefined;
      const selectedAsset = assets.find((item) => item.id === selectedVideo.mediaId);
      const remainingSource = selectedAsset?.duration == null ? null : Math.max(0, selectedAsset.duration - selectedVideo.sourceStart);
      let patch: Record<string, unknown> | null = null;
      let summary = "";
      if (/\\b(shorten|trim shorter|reduce duration)\\b/.test(normalized)) {
        const duration = Math.max(0.1, selectedVideo.duration - Math.max(0.1, amount));
        if (duration < selectedVideo.duration) { patch = { duration }; summary = `Shorten selected shot to ${duration.toFixed(1)} seconds`; }
      } else if (/\\b(extend|lengthen)\\b/.test(normalized)) {
        const asset = selectedAsset;
        const limit = asset?.duration == null ? selectedVideo.duration + Math.max(0.1, amount) : Math.max(0, asset.duration - selectedVideo.sourceStart);
        const duration = Math.min(selectedVideo.duration + Math.max(0.1, amount), limit);
        if (duration > selectedVideo.duration) { patch = { duration }; summary = `Extend selected shot to ${duration.toFixed(1)} seconds`; }
      } else if (/\\b(move|place|position)\\b/.test(normalized) && /\\b(to|at)\\s+\\d/.test(normalized)) {
        const position = Number(normalized.match(/\\b(?:to|at)\\s+(\\d+(?:\\.\\d+)?)/)?.[1]);
        if (Number.isFinite(position) && position >= 0) { patch = { timelineStart: position }; summary = `Move selected shot to ${position.toFixed(1)} seconds`; }
      } else if (/\\b(source start|source in|start from)\\b/.test(normalized) && seconds) {
        const asset = assets.find((item) => item.id === selectedVideo.mediaId);
        const sourceStart = Math.max(0, amount);
        if (asset?.duration == null || sourceStart < asset.duration) {
          const duration = asset?.duration == null ? selectedVideo.duration : Math.min(selectedVideo.duration, asset.duration - sourceStart);
          if (duration >= 0.1) { patch = { sourceStart, duration }; summary = `Set source start to ${sourceStart.toFixed(1)} seconds`; }
        }
      } else if (/\\b(after previous|after the previous|after prior)\\b/.test(normalized) && previousShot) {
        const position = previousShot.timelineStart + previousShot.duration;
        patch = { timelineStart: position };
        summary = `Place selected shot after the previous shot at ${position.toFixed(1)} seconds`;
      } else if (/\\b(before next|before the next)\\b/.test(normalized) && nextShot) {
        const position = Math.max(0, nextShot.timelineStart - selectedVideo.duration);
        patch = { timelineStart: position };
        summary = `Place selected shot before the next shot at ${position.toFixed(1)} seconds`;
      } else if (/\\b(match|same)\\b/.test(normalized) && /\\b(previous|prior)\\b/.test(normalized) && previousShot) {
        const maxDuration = remainingSource ?? Number.POSITIVE_INFINITY;
        const duration = Math.min(previousShot.duration, maxDuration);
        if (duration >= 0.1) {
          patch = { duration };
          summary = `Match the previous shot's ${duration.toFixed(1)} second duration`;
        }
      } else if (/\\b(fade|crossfade|no transition|remove transition)\\b/.test(normalized)) {
        const transition = /\\bcrossfade\\b/.test(normalized) ? "crossfade" : /\\bfade\\b/.test(normalized) ? "fade" : "none";
        patch = { transition }; summary = `Set selected shot transition to ${transition}`;
      }
      if (patch) {
        setCommandText(trimmed);
        setClipRefinement({ clipId: selectedVideo.id, patch, summary });
        setCommandPlan(null);
        setDirectorPlan(null);
        setDirectorTimelinePreview(null);
        setDirectorTimelineError("");
        setDirectorError("");
        return;
      }
    }
    setCommandText(trimmed);
    setCommandPlan(planTimelineCommand(doc, trimmed));
    setDirectorPlan(null);
    setDirectorTimelinePreview(null);
    setDirectorTimelineError("");
    setDirectorError("");
    setDirectorLoading(true);
    try {
      const plan = await aiDirectorApi.plan({
        projectId,
        instruction: trimmed,
        project: { ...projectContext, timeline_document: doc },
        assets: assets.map(({ id, filename, mime_type, duration }) => ({ id, filename, mime_type, duration })),
      });
      setDirectorPlan(plan);
      try {
        setDirectorTimelinePreview(adaptDirectorDraftToTimeline(plan.timeline_draft, doc, assets));
      } catch (cause) {
        setDirectorTimelineError(cause instanceof Error ? cause.message : "The AI timeline draft could not be validated.");
      }
    } catch (cause) {
      setDirectorError(cause instanceof Error ? cause.message : "Could not reach the AI Director.");
    } finally {
      setDirectorLoading(false);
    }
  };

  return (
    <section className="panel timeline-composer">
      <div className="panel-heading"><div><p className="eyebrow">EDITING WORKSPACE</p><h2>Timeline composer</h2></div><span className="timeline-duration">{duration.toFixed(1)}s</span></div>
      <section className="ai-command-panel" aria-label="AI editing commands">
        <div className="ai-command-title"><div><p className="eyebrow">PROMPT-BASED EDITING</p><h3>Tell FLEXY what to change</h3></div><span className="command-spark">✦</span></div>
        <form className="ai-command-form" onSubmit={(event) => { event.preventDefault(); void runCommand(commandText); }}>
          <input aria-label="Editing command" value={commandText} onChange={(event) => { setCommandText(event.target.value); setCommandPlan(null); setDirectorTimelinePreview(null); setDirectorTimelineError(""); }} placeholder="e.g. Make it cinematic, then set music volume to 40%" />
          <button className="primary" type="submit" disabled={!commandText.trim() || directorLoading}>{directorLoading ? "Thinking…" : "Create edit plan"}</button>
        </form>
        <section className="scene-sequence-panel" aria-label="Music beat analysis">
          <div className="scene-sequence-heading">
            <div><p className="eyebrow">MUSIC INTELLIGENCE</p><strong>Beat analysis</strong></div>
            <span>{beatAnalysis ? `${beatAnalysis.beats.length} markers` : "No analysis yet"}</span>
          </div>
          <div className="smart-timeline-controls">
            {assets.filter((asset) => asset.mime_type.startsWith("audio/") || (asset.mime_type.startsWith("video/") && Array.isArray(asset.metadata?.streams) && (asset.metadata?.streams as Array<{codec_type?: string}>).some((stream) => stream.codec_type === "audio"))).map((asset) => (
              <button key={asset.id} type="button" onClick={() => void runBeatAnalysis(asset.id)} disabled={beatAnalysisBusy}>
                {beatAnalysisBusy && beatAnalysisTarget === asset.id ? "Analyzing…" : `Analyze ${asset.filename}`}
              </button>
            ))}
          </div>
          {beatAnalysisError && <p className="command-error" role="alert">{beatAnalysisError}</p>}
          {beatAnalysis && <>
            <div className="scene-sequence-preview" aria-live="polite">
              <strong>{beatAnalysis.estimated_bpm === null ? "Tempo uncertain" : `${beatAnalysis.estimated_bpm.toFixed(1)} BPM`} · {(beatAnalysis.confidence * 100).toFixed(0)}% confidence</strong>
              <div className="beat-marker-strip" role="img" aria-label={`${beatAnalysis.beats.length} detected beat markers across ${beatAnalysis.duration_analyzed.toFixed(1)} seconds`}>
                {beatAnalysis.beats.slice(0, 160).map((time, index) => <span key={`${time}-${index}`} title={`${time.toFixed(2)} seconds`} style={{ left: `${beatAnalysis.duration_analyzed > 0 ? (time / beatAnalysis.duration_analyzed) * 100 : 0}%` }} />)}
              </div>
              <small>{beatAnalysis.notice}</small>
              {beatAnalysis.truncated && <small>Analysis was capped at the supported duration.</small>}
            </div>
            <div className="command-plan-actions">
              <button type="button" onClick={() => setShowMusicTransitionSuggestions((value) => !value)} disabled={!beatTimelineMarkers.length || !doc.videoClips.length}>
                {showMusicTransitionSuggestions ? "Hide transition suggestions" : "Suggest beat-synced transitions"}
              </button>
              <button type="button" className="primary" onClick={applyMusicTransitionSuggestions} disabled={!showMusicTransitionSuggestions || !musicTransitionSuggestions.length}>
                Apply {musicTransitionSuggestions.length} suggestion{musicTransitionSuggestions.length === 1 ? "" : "s"}
              </button>
            </div>
            {showMusicTransitionSuggestions && <div className="scene-sequence-preview" aria-live="polite">
              <strong>Beat-synced transition review</strong>
              {musicTransitionSuggestions.length ? <ul>{musicTransitionSuggestions.map((item) => (
                <li key={item.clipId}>Clip {item.clipId}: {item.transition} at {item.cutTime.toFixed(2)}s, nearest beat {item.beatTime.toFixed(2)}s ({item.offsetSeconds.toFixed(3)}s away)</li>
              ))}</ul> : <small>No untransitioned same-track cuts are within 0.12 seconds of a detected beat. No changes are recommended.</small>}
              <small>Suggestions only set the existing transition type. They do not move or trim clips. Review the result before exporting.</small>
            </div>}
            <small>These beat markers can guide Smart Timeline drafts and review-first transition suggestions. Analyze another audio asset to replace this source.</small>
          </>}
          {!beatAnalysis && !beatAnalysisError && <small>Analyze an imported audio file or video with an audio stream. Detected markers can guide Smart Timeline shot lengths.</small>}
        </section>
        <section className="scene-sequence-panel smart-timeline-panel" aria-label="Smart Timeline first-cut generator">
          <div className="scene-sequence-heading">
            <div><p className="eyebrow">AI FIRST CUT</p><strong>Smart Timeline</strong></div>
            <button type="button" className="primary" onClick={() => void runSmartTimeline()} disabled={smartTimelineBusy || !assets.some((asset) => asset.mime_type.startsWith("video/"))}>
              {smartTimelineBusy ? "Analyzing shots…" : "Generate draft"}
            </button>
          </div>
          <div className="smart-timeline-controls">
            <label>Editing style<select value={smartTimelineStyle} onChange={(event) => setSmartTimelineStyle(event.target.value as "balanced" | "dynamic" | "calm")}><option value="balanced">Balanced</option><option value="dynamic">Dynamic</option><option value="calm">Calm</option></select></label>
            <label>Target duration (seconds)<input type="number" min="1" max="600" step="1" value={smartTimelineDuration} onChange={(event) => setSmartTimelineDuration(event.target.value)} /></label>
            <label>Minimum shot length (seconds)<input type="number" min="0.5" max="10" step="0.5" value={smartTimelineShotFloor} onChange={(event) => setSmartTimelineShotFloor(event.target.value)} /></label>
            <label>Maximum shot length (seconds)<input type="number" min="0.5" max="15" step="0.5" value={smartTimelineShotCap} onChange={(event) => setSmartTimelineShotCap(event.target.value)} /></label>
          </div>
          <small>Analyzes imported video scenes and available visual-interest evidence, then prepares a non-destructive first cut. Nothing changes until you apply it.</small>
          {transcription?.segments.length ? <small>{assets.filter((asset) => asset.mime_type.startsWith("video/")).length === 1 && assets.some((asset) => asset.id === transcription.media_id) ? `Transcript-aware ranking enabled · ${transcription.segments.length} timestamped segments` : "Transcript available, but not attached because its source video is ambiguous."}</small> : <small>Run speech transcription on the source video to enable dialogue-aware shot selection.</small>}
          {smartTimelineError && <p className="command-error" role="alert">{smartTimelineError}</p>}
          {smartTimelineDraft && <div className="scene-sequence-preview" aria-live="polite">
            <strong>Draft preview · {smartTimelineDraft.clips.length} shots · {smartTimelineDraft.duration.toFixed(1)}s</strong>
            <ol>{smartTimelineDraft.clips.map((clip, index) => <li key={`smart-shot-${index}`}>
              <strong>{assets.find((asset) => asset.id === clip.assetId)?.filename ?? "Video asset"}</strong>
              <span> Source {clip.sourceStart.toFixed(1)}s · {clip.duration.toFixed(1)}s · score {clip.evidence.shot_score.toFixed(1)}</span>
              <small>{clip.reason}{clip.evidence.visual_score === null ? " · No visual score supplied" : ` · Visual interest ${(clip.evidence.visual_score * 100).toFixed(0)}%`}</small>
            </li>)}</ol>
            {smartTimelineDraft.warnings.map((warning, index) => <small key={`smart-warning-${index}`}>{warning}</small>)}
            <div className="command-plan-actions">
              <button type="button" onClick={() => setSmartTimelineDraft(null)}>Discard draft</button>
              <button type="button" className="primary" disabled={!smartTimelineDraft.clips.length} onClick={applySmartTimelineDraft}>Apply to timeline</button>
            </div>
            <small>Applying replaces current video clips with the proposed sequence. Existing audio is kept unless the draft supplies an audio track. This is one undoable timeline edit.</small>
          </div>}
        </section>
        <section className="visual-transition-panel" aria-label="Visual transition analysis">
          <div className="scene-sequence-heading">
            <div><p className="eyebrow">FRAME COMPARISON</p><strong>Visual transition intelligence</strong></div>
            <button type="button" onClick={() => void analyzeVisualTransitions()} disabled={visualTransitionBusy || doc.videoClips.length < 2}>{visualTransitionBusy ? "Sampling frames…" : "Analyze frames"}</button>
          </div>
          <small>Samples the outgoing and incoming boundary frames, then compares brightness, contrast, colorfulness and tone locally in your browser.</small>
          {visualTransitionError && <p className="command-error" role="alert">{visualTransitionError}</p>}
          {visualTransitionPlan && <div className="scene-sequence-preview" aria-live="polite">
            <strong>Visual comparison results</strong>
            {visualTransitionPlan.findings.length ? <ul>{visualTransitionPlan.findings.map((finding, index) => <li key={`visual-finding-${index}`}>{finding}</li>)}</ul> : <p>No frame pairs were compared.</p>}
            {visualTransitionPlan.changes.length ? <><strong>Transition proposals</strong><ul>{visualTransitionPlan.changes.map((change, index) => <li key={`visual-change-${index}`}>{change}</li>)}</ul></> : <p>No transition changes proposed.</p>}
            {visualTransitionPlan.warnings.map((warning, index) => <small key={`visual-warning-${index}`}>{warning}</small>)}
            <div className="command-plan-actions">
              <button type="button" onClick={() => setVisualTransitionPlan(null)}>Discard</button>
              <button type="button" className="primary" disabled={visualTransitionPlan.changes.length === 0} onClick={applyVisualTransitionPlan}>Apply transitions</button>
            </div>
            <small>Frame comparisons are simple visual-difference estimates, not semantic scene understanding. Review every suggestion before applying.</small>
          </div>}
        </section>
        <section className="scene-sequence-panel" aria-label="Scene-to-scene sequence analysis">
          <div className="scene-sequence-heading">
            <div><p className="eyebrow">SEQUENCE CHECK</p><strong>Scene-to-scene refinement</strong></div>
            <button type="button" onClick={analyzeSceneSequence} disabled={doc.videoClips.length < 2}>Analyze sequence</button>
          </div>
          <small>Checks neighboring shots on each track for short gaps, overlaps and missing transitions.</small>
          {sceneSequencePlan && <div className="scene-sequence-preview" aria-live="polite">
            {sceneSequencePlan.changes.length > 0 ? <ul>{sceneSequencePlan.changes.map((change, index) => <li key={`sequence-change-${index}`}>{change}</li>)}</ul> : <p>No automatic changes proposed.</p>}
            {sceneSequencePlan.warnings.map((warning, index) => <small key={`sequence-warning-${index}`}>{warning}</small>)}
            <div className="command-plan-actions">
              <button type="button" onClick={() => setSceneSequencePlan(null)}>Discard</button>
              <button type="button" className="primary" disabled={sceneSequencePlan.changes.length === 0} onClick={applySceneSequencePlan}>Apply sequence edits</button>
            </div>
            <small>Only listed changes are applied. Overlaps and large gaps are not changed automatically. Applying creates one undo step.</small>
          </div>}
        </section>
        {selectedVideo && <div className="copilot-context" aria-label="Selected shot context">
          <strong>FLEXY understands this shot</strong>
          <span>Timeline: {selectedVideo.timelineStart.toFixed(1)}s to {(selectedVideo.timelineStart + selectedVideo.duration).toFixed(1)}s · Track {selectedVideo.trackIndex + 1}</span>
          <span>Source: {selectedVideo.sourceStart.toFixed(1)}s in · {remainingSource === null ? "source duration unknown" : `${remainingSource.toFixed(1)}s available`}</span>
          <span>Previous: {previousShot ? `${assets.find((item) => item.id === previousShot.mediaId)?.filename ?? "Video clip"} ends at ${(previousShot.timelineStart + previousShot.duration).toFixed(1)}s` : "none"}</span>
          <span>Next: {nextShot ? `${assets.find((item) => item.id === nextShot.mediaId)?.filename ?? "Video clip"} starts at ${nextShot.timelineStart.toFixed(1)}s` : "none"}</span>
        </div>}
        {selectedVideo && <div className="command-examples selected-shot-examples" aria-label="Selected shot command examples">
          {["Shorten this clip by 1 second", "Extend this clip by 2 seconds", "Move this clip after previous", "Move this clip before next", "Match previous shot duration", "Set source start to 2 seconds", "Add a crossfade"].map((example) =>
            <button type="button" key={example} onClick={() => { setCommandText(example); void runCommand(example); }}>{example}</button>
          )}
        </div>}
        <div className="command-examples">
          {["Make it cinematic, then set music volume to 40%", "Move clip 2 to 5 seconds", "Set clip 1 duration to 3 seconds", "Set music volume to 40%", "Remove transitions"].map((example) =>
            <button type="button" key={example} onClick={() => { void runCommand(example); }}>{example}</button>
          )}
        </div>
        {directorError && <p className="command-error" role="alert">{directorError}</p>}
        {directorPlan && <div className="director-result" aria-live="polite">
          <div className="director-result-heading"><strong>AI Director analysis</strong><span>{directorPlan.provider === "openai_compatible" ? `Model: ${directorPlan.model ?? "configured provider"}` : "Local planning mode"}</span></div>
          <p>{directorPlan.summary}</p>
          <ul>{directorPlan.suggestions.map((item, index) => <li key={`${item.kind}-${index}`}><strong>{item.title}</strong><span>{item.detail}</span></li>)}</ul>
          {directorPlan.warnings.map((warning, index) => <small key={index}>{warning}</small>)}
          <small>Suggested canvas: {directorPlan.aspect_ratio.label} · {directorPlan.aspect_ratio.width} × {directorPlan.aspect_ratio.height}</small>
        </div>}
        {directorTimelineError && <p className="command-error" role="alert">{directorTimelineError}</p>}
        {directorTimelinePreview && <div className="command-plan director-timeline-preview" aria-live="polite">
          <strong>AI timeline preview</strong>
          <p>{directorTimelinePreview.summary}</p>
          <ul>{directorTimelinePreview.changes.map((change, index) => <li key={index}>{change}</li>)}</ul>
          {directorTimelinePreview.warnings.map((warning, index) => <small key={`draft-warning-${index}`}>{warning}</small>)}
          <div className="command-plan-actions">
            <button type="button" onClick={() => setDirectorTimelinePreview(null)}>Discard timeline</button>
            <button type="button" className="primary" onClick={() => {
              update(directorTimelinePreview.nextDocument);
              setDirectorTimelinePreview(null);
              setSelectedClip(null);
              setPlayhead(0);
            }}>Apply timeline</button>
          </div>
          <small>Applying replaces the current video and audio clips, keeps captions, and adds one undo step. Nothing changes until you apply.</small>
        </div>}
        {commandPlan && <div className={`command-plan${commandPlan.error ? " has-error" : ""}`} aria-live="polite">
          <strong>{commandPlan.error ? "Needs attention" : commandPlan.summary}</strong>
          {commandPlan.error ? <p>{commandPlan.error}</p> : <>
            <ul>{commandPlan.changes.map((change, index) => <li key={index}>{change}</li>)}</ul>
            <div className="command-plan-actions">
              <button type="button" onClick={() => setCommandPlan(null)}>Discard</button>
              <button type="button" className="primary" onClick={() => { update(commandPlan.nextDocument); setCommandPlan(null); setSelectedClip(null); }}>Apply edits</button>
            </div>
          </>}
        </div>}
        <p className="command-disclaimer">The local command preview is rule-based and supports up to 8 ordered steps in one request. Separate steps with “then”, semicolons, or “and” before another editing action. Every step is previewed together and the full request is rejected if any step fails. The AI Director can also prepare a separate starter sequence. Configure FLEXY_AI_API_KEY on the backend for model-generated suggestions. No edit is applied until you approve it.</p>
      </section>
      <VisualMediaInspector assets={assets} projectId={projectId}
        onCreateEditPlan={(instruction) => { setCommandText(instruction); void runCommand(instruction); }}
        onAddShotToTimeline={(asset, sourceStart) => {
          const available = asset.duration === null ? 3 : Math.max(0, asset.duration - sourceStart);
          const shotDuration = Math.min(3, available);
          if (shotDuration < 0.1) return;
          const clip = { id: `ai-shot-${Date.now()}`, mediaId: asset.id,
            sourceStart: Math.max(0, sourceStart), duration: shotDuration,
            timelineStart: getTimelineDuration(doc), trackIndex: 0, transition: "none" as const };
          update({ ...doc, videoClips: [...doc.videoClips, clip] });
          setSelectedClip({ id: clip.id, type: "video" });
          setTab("video");
          setPlayhead(clip.timelineStart);
        }} />
      <section className="caption-intelligence-panel" aria-label="Caption intelligence">
        <div className="timeline-quality-heading">
          <div><p className="eyebrow">CAPTION INTELLIGENCE</p><h3>Smart caption timing</h3></div>
          <button type="button" onClick={() => setCaptionReport(analyzeCaptionTiming(doc))} disabled={doc.captions.length === 0}>Analyze captions</button>
        </div>
        <small>Checks caption overlaps, video-end boundaries and estimated reading speed. All timing edits are suggestions for review.</small>
        {captionReport && <div className="caption-intelligence-results" aria-live="polite">
          <div className="audio-intelligence-stats">
            <div><strong>{captionReport.findings.length}</strong><small>Review notes</small></div>
            <div><strong>{captionReport.changes.length}</strong><small>Proposed fixes</small></div>
          </div>
          {captionReport.findings.map((finding, index) => <article className="audio-finding" key={`caption-finding-${index}`}>
            <span>{finding.severity === "warning" ? "!" : "i"}</span><div><strong>{finding.title}</strong><small>{finding.detail}</small></div>
            {finding.captionId && <button type="button" onClick={() => {
              const item = doc.captions.find((captionItem) => captionItem.id === finding.captionId);
              if (item) { setSelectedClip({ id: item.id, type: "caption" }); setTab("captions"); setPlayhead(item.start); }
            }}>Review</button>}
          </article>)}
          {captionReport.changes.length > 0 && <ul>{captionReport.changes.map((change) => <li key={change.captionId}>{change.description}</li>)}</ul>}
          {captionReport.notes.map((note, index) => <small key={`caption-note-${index}`}>{note}</small>)}
          <div className="command-plan-actions">
            <button type="button" onClick={() => setCaptionReport(null)}>Discard</button>
            <button type="button" className="primary" disabled={captionReport.changes.length === 0} onClick={applyCaptionTimingPlan}>Apply timing</button>
          </div>
          <small>Applying approved changes creates one undoable timeline edit. Timing heuristics do not establish actual speech synchronization.</small>
        </div>}
      </section>
      <section className="audio-intelligence-panel" aria-label="Audio intelligence">
        <div className="timeline-quality-heading">
          <div><p className="eyebrow">AUDIO INTELLIGENCE</p><h3>Audio review assistant</h3></div>
          <button type="button" onClick={() => void runAudioIntelligence()} disabled={audioIntelligenceBusy || doc.audioClips.length === 0}>
            {audioIntelligenceBusy ? "Analyzing…" : audioIntelligenceRan ? "Refresh analysis" : "Analyze audio"}
          </button>
        </div>
        <small>Uses the project's FFmpeg waveform summaries to flag quiet regions, near-silent openings/endings, high peak buckets and dialogue/music overlap.</small>
        {audioIntelligenceError && <p className="command-error" role="alert">{audioIntelligenceError}</p>}
        {audioIntelligenceRan && <div className="audio-intelligence-results" aria-live="polite">
          <div className="audio-intelligence-stats">
            <div><strong>{audioIntelligence.analyzedClips}</strong><small>Clips analyzed</small></div>
            <div><strong>{audioIntelligence.findings.length}</strong><small>Review notes</small></div>
            <div><strong>{audioIntelligence.unavailable.length}</strong><small>Unavailable</small></div>
          </div>
          {audioIntelligence.profiles.map((profile) => {
            const asset = assets.find((item) => item.id === profile.mediaId);
            return <div className="audio-profile" key={profile.clipId}>
              <strong>{asset?.filename ?? "Audio clip"}</strong>
              <div className="audio-profile-wave" aria-label={`${profile.bucketCount} waveform peak samples`}>
                {(audioWaveforms[profile.mediaId]?.points ?? audioWaveforms[profile.mediaId]?.samples ?? audioWaveforms[profile.mediaId]?.waveform ?? []).slice(0, 96).map((value, index) =>
                  <span key={`${profile.clipId}-${index}`} style={{ height: `${Math.max(3, Math.min(100, Number(value) * 100))}%` }} />)}
              </div>
              <small>Average peak {Math.round(profile.averagePeak * 100)}% · {Math.round(profile.silentBuckets / Math.max(1, profile.bucketCount) * 100)}% near-silent buckets</small>
              <div className="audio-quality-actions">
                <button type="button" onClick={() => void runCalibratedAudioAnalysis(profile.mediaId)} disabled={Boolean(audioQualityBusy[profile.mediaId])}>
                  {audioQualityBusy[profile.mediaId] ? "Measuring…" : audioQualityReports[profile.mediaId] ? "Refresh LUFS" : "Measure LUFS"}
                </button>
                {audioQualityErrors[profile.mediaId] && <small role="alert">{audioQualityErrors[profile.mediaId]}</small>}
                {audioQualityReports[profile.mediaId] && <small>
                  EBU R128 · Integrated {audioQualityReports[profile.mediaId].integrated_lufs === null ? "Unavailable" : `${audioQualityReports[profile.mediaId].integrated_lufs.toFixed(1)} LUFS`} ·
                  LRA {audioQualityReports[profile.mediaId].loudness_range_lu === null ? "Unavailable" : `${audioQualityReports[profile.mediaId].loudness_range_lu.toFixed(1)} LU`} ·
                  True peak {audioQualityReports[profile.mediaId].true_peak_dbfs === null ? "Unavailable" : `${audioQualityReports[profile.mediaId].true_peak_dbfs.toFixed(1)} dBFS`}
                </small>}
              </div>
            </div>;
          })}
          {audioMixPlan && <div className="audio-mix-proposals">
            <strong>Smart mix proposals</strong>
            {audioMixPlan.changes.length ? <ul>{audioMixPlan.changes.map((change, index) => <li key={`mix-proposal-${index}`}>{change.description}</li>)}</ul> : <p>No automatic mix changes suggested.</p>}
            {audioMixPlan.notes.map((note, index) => <small key={`mix-note-${index}`}>{note}</small>)}
            <div className="command-plan-actions">
              <button type="button" onClick={() => setAudioMixPlan(null)}>Discard</button>
              <button type="button" className="primary" disabled={audioMixPlan.changes.length === 0} onClick={applyAudioMixPlan}>Apply mix</button>
            </div>
            <small>Review by listening first. Caption-timed music dips use existing caption positions and are applied as editable volume keyframes in one undoable edit.</small>
          </div>}
          {audioIntelligence.findings.length ? audioIntelligence.findings.map((finding, index) => <article className="audio-finding" key={`${finding.title}-${index}`}>
            <span>{finding.severity === "warning" ? "!" : "i"}</span><div><strong>{finding.title}</strong><small>{finding.detail}</small></div>
            {finding.clipId && <button type="button" onClick={() => {
              const clip = doc.audioClips.find((item) => item.id === finding.clipId);
              if (clip) { setSelectedClip({ id: clip.id, type: "audio" }); setTab("audio"); setPlayhead(clip.timelineStart); }
            }}>Review</button>}
          </article>) : <p>No waveform review notes were generated.</p>}
          {audioIntelligence.unavailable.length > 0 && <small>Waveform unavailable for {audioIntelligence.unavailable.length} clip(s). Confirm the source media contains audio.</small>}
        </div>}
        <small className="timeline-quality-note">Waveform peaks are coarse summaries, not calibrated loudness, speech detection, music recognition or automatic lip-sync verification. Listen before making changes.</small>
      </section>
      <section className="timeline-quality-panel" aria-label="Editing quality report">
        <div className="timeline-quality-heading">
          <div><p className="eyebrow">PRE-EXPORT REVIEW</p><h3>Editing quality assistant</h3></div>
          <div className="timeline-quality-score"><strong>{timelineQuality.score}</strong><small>/100 · {timelineQuality.grade}</small></div>
        </div>
        <div className="timeline-quality-checks">
          {timelineQuality.checks.map((check) => <div key={check.label} className={check.passed ? "passed" : "review"}>
            <span>{check.passed ? "✓" : "!"}</span><div><strong>{check.label}</strong><small>{check.detail}</small></div>
          </div>)}
        </div>
        <div className="timeline-quality-findings">
          {timelineQuality.findings.length ? timelineQuality.findings.map((finding, index) => <article key={`${finding.category}-${finding.title}-${index}`}>
            <span>{finding.severity === "warning" ? "!" : "i"}</span><div><strong>{finding.title}</strong><small>{finding.detail}</small></div>
            {finding.clipId && <button type="button" onClick={() => {
              const clip = doc.videoClips.find((item) => item.id === finding.clipId);
              const audioClip = doc.audioClips.find((item) => item.id === finding.clipId);
              const captionItem = doc.captions.find((item) => item.id === finding.clipId);
              if (clip) { setSelectedClip({ id: clip.id, type: "video" }); setTab("video"); setPlayhead(clip.timelineStart); }
              else if (audioClip) { setSelectedClip({ id: audioClip.id, type: "audio" }); setTab("audio"); setPlayhead(audioClip.timelineStart); }
              else if (captionItem) { setSelectedClip({ id: captionItem.id, type: "caption" }); setTab("captions"); setPlayhead(captionItem.start); }
            }}>Review</button>}
          </article>) : <p>No structural issues detected by these checks. Preview the complete edit before exporting.</p>}
        </div>
        <small className="timeline-quality-note">Score reflects timeline structure and metadata only. It does not judge storytelling, audio quality, music fit, speech accuracy or actual lip-sync.</small>
      </section>
      <section className="timeline-intelligence" aria-label="Timeline intelligence">
        <div className="timeline-intelligence-heading">
          <div><p className="eyebrow">TIMELINE INTELLIGENCE</p><h3>Editing insights</h3></div>
          <span>{timelineIntelligence.videoCount} video · {timelineIntelligence.audioCount} audio · {timelineIntelligence.captionCount} captions</span>
        </div>
        <div className="timeline-intelligence-stats">
          <div><strong>{timelineIntelligence.duration.toFixed(1)}s</strong><small>Timeline length</small></div>
          <div><strong>{timelineIntelligence.visualCoverage.toFixed(0)}%</strong><small>Visual clip coverage</small></div>
          <div><strong>{timelineIntelligence.insights.filter((item) => item.kind === "warning").length}</strong><small>Items to review</small></div>
        </div>
        {timelineIntelligence.clipNotes.length > 0 && <div className="timeline-clip-map">
          <strong>Clip map</strong>
          {timelineIntelligence.clipNotes.map((clip, index) => <button type="button" key={clip.id}
            onClick={() => { setSelectedClip({ id: clip.id, type: "video" }); setTab("video"); setPlayhead(clip.start); }}
            title={`Select ${clip.name}`}>
            <span>#{index + 1} {clip.name}</span><small>{clip.start.toFixed(1)}s–{clip.end.toFixed(1)}s · Track {clip.track + 1} · {clip.transition}</small>
          </button>)}
        </div>}
        <div className="timeline-insight-list">
          {timelineIntelligence.insights.length ? timelineIntelligence.insights.map((insight, index) => <div className={`timeline-insight ${insight.kind}`} key={`${insight.title}-${index}`}>
            <span>{insight.kind === "warning" ? "!" : "i"}</span><div><strong>{insight.title}</strong><small>{insight.detail}</small></div>
            {insight.clipId && insight.clipType && <button type="button" onClick={() => {
              setSelectedClip({ id: insight.clipId!, type: insight.clipType! });
              setTab(insight.clipType === "audio" ? "audio" : insight.clipType === "caption" ? "captions" : "video");
              const target = insight.clipType === "caption" ? doc.captions.find((item) => item.id === insight.clipId)?.start
                : insight.clipType === "audio" ? doc.audioClips.find((item) => item.id === insight.clipId)?.timelineStart
                : doc.videoClips.find((item) => item.id === insight.clipId)?.timelineStart;
              if (target !== undefined) setPlayhead(target);
            }}>Inspect</button>}
          </div>) : <p>No structural issues detected in the current timeline.</p>}
        </div>
        <small className="timeline-intelligence-note">Analysis uses clip timing, track, transition and asset metadata. It does not visually inspect footage or listen to audio.</small>
      </section>
      <div className="timeline-settings">
        <label>Export preset<select value={doc.exportPreset} onChange={(e) => update({ ...doc, exportPreset: e.target.value as TimelineDocument["exportPreset"] })}>
          <option value="720p">720p</option><option value="1080p">1080p</option><option value="4k">4K</option>
        </select></label>
        <label>Frame rate<select value={doc.frameRate} onChange={(e) => update({ ...doc, frameRate: Number(e.target.value) })}>
          {[24,25,30,50,60].map((fps) => <option key={fps} value={fps}>{fps} FPS</option>)}
        </select></label>
      </div>
      <div className="timeline-tabs">
        <button className={tab === "video" ? "active" : ""} onClick={() => setTab("video")}>Video / image</button>
        <button className={tab === "audio" ? "active" : ""} onClick={() => setTab("audio")}>Audio</button>
        <button className={tab === "captions" ? "active" : ""} onClick={() => setTab("captions")}>Captions</button>
      </div>

      {tab === "video" && <div className="timeline-form">
        <label>Video / image asset<select value={video.mediaId} onChange={(e) => setVideo({ ...video, mediaId: e.target.value })}><option value="">Choose imported media</option>{assets.filter((a) => a.mime_type.startsWith("video/") || a.mime_type.startsWith("image/")).map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}</select></label>
        <div className="form-grid">
          <label>Source in (s)<input type="number" min="0" step=".1" value={video.sourceStart} onChange={(e) => setVideo({ ...video, sourceStart: e.target.value })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={video.duration} onChange={(e) => setVideo({ ...video, duration: e.target.value })}/></label>
          <label>Timeline start (s)<input type="number" min="0" step=".1" value={video.timelineStart} onChange={(e) => setVideo({ ...video, timelineStart: e.target.value })}/></label>
          <label>Track (0-7)<input type="number" min="0" max="7" step="1" value={video.trackIndex} onChange={(e) => setVideo({ ...video, trackIndex: e.target.value })}/></label>
          <label>Transition<select value={video.transition} onChange={(e) => setVideo({ ...video, transition: e.target.value as typeof video.transition })}><option value="none">None</option><option value="fade">Fade</option><option value="crossfade">Crossfade</option></select></label>
        </div>
        <button className="primary" disabled={!video.mediaId.trim() || Number(video.duration) <= 0} onClick={addVideo}>Add video clip +</button>
      </div>}

      {tab === "audio" && <div className="timeline-form">
        <section className="audio-bus-mixer" aria-label="Audio bus mixer">
          <div><p className="eyebrow">PRO MIXER</p><h3>Audio bus mixer</h3><small>Bus gain and mute are applied in the final FFmpeg export.</small></div>
          {(["dialogue", "music", "effects", "master"] as const).map((bus) => {
            const settings = (doc.audioMixer ?? { dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false }, effects: { gain: 1, muted: false }, master: { gain: 1, muted: false } })[bus];
            return <div className="audio-bus-row" key={bus}>
              <strong>{bus[0].toUpperCase() + bus.slice(1)}</strong>
              <input aria-label={`${bus} bus gain`} type="range" min="0" max="2" step="0.01" value={settings.gain} onChange={(e) => updateAudioBus(bus, { gain: Number(e.target.value) })}/>
              <output>{Math.round(settings.gain * 100)}%</output>
              <label className="inline-check"><input type="checkbox" checked={settings.muted} onChange={(e) => updateAudioBus(bus, { muted: e.target.checked })}/> Mute</label>
            </div>;
          })}
        </section>
        <section className="audio-ducking-controls" aria-label="Dialogue-aware music ducking">
          <label className="inline-check"><input type="checkbox" checked={doc.ducking} onChange={(e) => update({ ...doc, ducking: e.target.checked })}/> Enable dialogue-aware music ducking</label>
          <small>When enabled, dialogue controls how strongly overlapping music is reduced during export.</small>
          <div className="form-grid">
            <label>Trigger threshold (dB)<input type="number" min="-40" max="-6" step="1" value={doc.duckingSettings?.thresholdDb ?? -24} onChange={(e) => update({ ...doc, duckingSettings: { ...(doc.duckingSettings ?? { thresholdDb: -24, ratio: 8, attackMs: 20, releaseMs: 450 }), thresholdDb: Math.max(-40, Math.min(-6, Number(e.target.value))) } })}/></label>
            <label>Compression ratio<input type="number" min="1" max="20" step="0.5" value={doc.duckingSettings?.ratio ?? 8} onChange={(e) => update({ ...doc, duckingSettings: { ...(doc.duckingSettings ?? { thresholdDb: -24, ratio: 8, attackMs: 20, releaseMs: 450 }), ratio: Math.max(1, Math.min(20, Number(e.target.value))) } })}/></label>
            <label>Attack (ms)<input type="number" min="1" max="200" step="1" value={doc.duckingSettings?.attackMs ?? 20} onChange={(e) => update({ ...doc, duckingSettings: { ...(doc.duckingSettings ?? { thresholdDb: -24, ratio: 8, attackMs: 20, releaseMs: 450 }), attackMs: Math.max(1, Math.min(200, Number(e.target.value))) } })}/></label>
            <label>Release (ms)<input type="number" min="50" max="2000" step="10" value={doc.duckingSettings?.releaseMs ?? 450} onChange={(e) => update({ ...doc, duckingSettings: { ...(doc.duckingSettings ?? { thresholdDb: -24, ratio: 8, attackMs: 20, releaseMs: 450 }), releaseMs: Math.max(50, Math.min(2000, Number(e.target.value))) } })}/></label>
          </div>
        </section>
        <label>Audio asset<select value={audio.mediaId} onChange={(e) => setAudio({ ...audio, mediaId: e.target.value })}><option value="">Choose imported audio</option>{assets.filter((a) => a.mime_type.startsWith("audio/") || a.mime_type.startsWith("video/")).map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}</select></label>
        <div className="form-grid">
          <label>Source in (s)<input type="number" min="0" step=".1" value={audio.sourceStart} onChange={(e) => setAudio({ ...audio, sourceStart: e.target.value })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={audio.duration} onChange={(e) => setAudio({ ...audio, duration: e.target.value })}/></label>
          <label>Timeline start (s)<input type="number" min="0" step=".1" value={audio.timelineStart} onChange={(e) => setAudio({ ...audio, timelineStart: e.target.value })}/></label>
          <label>Volume (0-2)<input type="number" min="0" max="2" step=".1" value={audio.volume} onChange={(e) => setAudio({ ...audio, volume: e.target.value })}/></label>
          <label>Audio track (0-7)<input type="number" min="0" max="7" step="1" value={audio.trackIndex} onChange={(e) => setAudio({ ...audio, trackIndex: e.target.value })}/></label>
          <label>Fade in (s)<input type="number" min="0" step=".1" value={audio.fadeIn} onChange={(e) => setAudio({ ...audio, fadeIn: e.target.value })}/></label>
          <label>Fade out (s)<input type="number" min="0" step=".1" value={audio.fadeOut} onChange={(e) => setAudio({ ...audio, fadeOut: e.target.value })}/></label>
        </div>
        <label>Audio role<select value={audio.role} onChange={(e) => setAudio({ ...audio, role: e.target.value as typeof audio.role })}><option value="dialogue">Dialogue</option><option value="music">Music</option><option value="other">Other</option></select></label>
        <button className="primary" disabled={!audio.mediaId.trim() || Number(audio.duration) <= 0} onClick={addAudio}>Add audio clip +</button>
      </div>}

      {tab === "captions" && <div className="timeline-form">
        <section className="speech-caption-panel" aria-label="AI subtitle generation">
          <div><p className="eyebrow">AI SUBTITLE GENERATION</p><h3>Transcribe a media clip</h3></div>
          <small>Creates timestamped draft captions from spoken audio using the configured speech provider. Requires backend speech credentials and FFmpeg/FFprobe. Long files are converted to audio-only chunks automatically, with timestamps restored to the original clip. No synthetic transcript is created when unavailable.</small>
          <label>Source media<select value={transcriptionMediaId} onChange={(e) => setTranscriptionMediaId(e.target.value)}>
            <option value="">Choose video or audio</option>
            {assets.filter((asset) => asset.mime_type.startsWith("video/") || asset.mime_type.startsWith("audio/")).map((asset) =>
              <option key={asset.id} value={asset.id}>{asset.filename}</option>)}
          </select></label>
          <label>Spoken language<select value={transcriptionLanguage} onChange={(e) => setTranscriptionLanguage(e.target.value)}>
            <option value="auto">Auto-detect</option>
            <option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option>
            <option value="fr">French</option><option value="de">German</option><option value="ja">Japanese</option>
            <option value="ko">Korean</option><option value="pt">Portuguese</option><option value="ar">Arabic</option>
          </select></label>
          <button type="button" onClick={() => void runTranscription()} disabled={!transcriptionMediaId || transcriptionBusy}>
            {transcriptionBusy ? "Transcribing…" : "Generate subtitles"}
          </button>
          {transcriptionError && <p className="command-error" role="alert">{transcriptionError}</p>}
          {transcription && <div className="speech-caption-preview" aria-live="polite">
            <strong>{transcription.segments.length} timestamped segments{transcription.language ? ` · ${transcription.language}` : ""}</strong>
            {transcription.chunking?.enabled && <small>Long-media mode · {transcription.chunking.chunk_count} audio chunks merged onto the original timeline</small>}
            <small>{transcription.segments.reduce((count, segment) => count + (segment.words?.length ?? 0), 0)} word timestamps available</small>
            {transcription.analysis && <div className="speech-analysis-summary" aria-label="Speech intelligence report">
              <strong>Speech intelligence</strong>
              <small>{transcription.analysis.word_count} words · {transcription.analysis.speaking_rate_wpm === null ? "Speaking rate unavailable" : `${transcription.analysis.speaking_rate_wpm} words/min`} · {transcription.analysis.long_pauses.length} pause(s) ≥ 0.6s</small>
              {Object.keys(transcription.analysis.filler_word_counts).length > 0 && <small>Possible filler phrases: {Object.entries(transcription.analysis.filler_word_counts).map(([term, count]) => `${term} ×${count}`).join(", ")}</small>}
              {transcription.analysis.long_pauses.slice(0, 3).map((pause, index) => <small key={`${pause.start}-${index}`}>Pause: {pause.start.toFixed(2)}s–{pause.end.toFixed(2)}s ({pause.duration.toFixed(2)}s)</small>)}
              <small>{transcription.analysis.notice}</small>
            </div>}
            <div className="dialogue-edit-planner">
              <div className="clip-inspector-heading"><div><strong>Dialogue timeline planner</strong><small>Review dialogue blocks and jump directly to timeline positions.</small></div>
                <button type="button" onClick={() => void runDialoguePlanning()} disabled={dialoguePlanBusy}>{dialoguePlanBusy ? "Planning…" : "Analyze dialogue"}</button>
              </div>
              {dialoguePlanError && <p className="command-error" role="alert">{dialoguePlanError}</p>}
              {dialoguePlan && <>
                <small>{dialoguePlan.block_count} dialogue blocks · {dialoguePlan.boundary_count} review markers · {dialoguePlan.speaker_labels_available ? "provider speaker labels available" : "no provider speaker labels"}</small>
                <div className="dialogue-block-list">{dialoguePlan.blocks.slice(0, 30).map((block) => <button key={block.block_id} type="button" className="dialogue-block" onClick={() => setPlayhead(block.start)}>
                  <span><strong>{block.block_id.replace("dialogue_", "Block ")}</strong><small>{block.start.toFixed(2)}s–{block.end.toFixed(2)}s · {block.duration.toFixed(1)}s · {block.kind.replaceAll("_", " ")}</small></span>
                  <span>{block.speaker_ids.length ? block.speaker_ids.join(", ") : "Dialogue"}<small>{block.text}</small></span>
                </button>)}</div>
                {dialoguePlan.cut_candidates.some((item) => item.reason === "long_pause") && <div className="dialogue-pause-trim-actions">
                  <p>Pause trims keep 0.12 seconds of breathing room beside each speech boundary. The edit is applied as one undoable timeline change.</p>
                  <button type="button" className="dialogue-apply-cut" onClick={applyDialoguePauseTrims}>Trim reviewed long pauses</button>
                </div>}
                {dialoguePlan.cut_candidates.length > 0 && <div className="dialogue-cut-list"><strong>Suggested review markers</strong>
                  {dialoguePlan.cut_candidates.slice(0, 20).map((marker, index) => {
                    const hasMatchingClip = doc.videoClips.some((clip) => clip.mediaId === transcriptionMediaId && marker.at > clip.sourceStart + 0.1 && marker.at < clip.sourceStart + clip.duration - 0.1);
                    return <div className="dialogue-cut-row" key={`${marker.at}-${index}`}>
                      <button type="button" onClick={() => {
                        const clip = doc.videoClips.find((item) => item.mediaId === transcriptionMediaId && marker.at > item.sourceStart + 0.1 && marker.at < item.sourceStart + item.duration - 0.1);
                        if (clip) setPlayhead(clip.timelineStart + marker.at - clip.sourceStart); else setPlayhead(marker.at);
                      }}>
                        <span>{marker.at.toFixed(2)}s</span><span>{marker.reason.replaceAll("_", " ")}{marker.gap_seconds > 0 ? ` · ${marker.gap_seconds.toFixed(2)}s pause` : ""}</span><small>Preview position</small>
                      </button>
                      <button type="button" className="dialogue-apply-cut" disabled={!hasMatchingClip} onClick={() => applyDialogueCut(marker.at)}>Split clip</button>
                    </div>;
                  })}</div>}
                <small>{dialoguePlan.notice}</small>
              </>}
            </div>
            <small>{transcription.notice}</small>
            {transcription.segments.slice(0, 8).map((segment) => <div key={segment.id}><time>{segment.start.toFixed(2)}s–{segment.end.toFixed(2)}s</time><span>{segment.text}</span></div>)}
            {transcription.segments.length > 8 && <small>Plus {transcription.segments.length - 8} more segments.</small>}
            <div className="command-plan-actions">
              <button type="button" onClick={() => void downloadTranscription("srt")}>Export SRT</button>
              <button type="button" onClick={() => void downloadTranscription("vtt")}>Export VTT</button>
              <button type="button" onClick={() => setTranscription(null)}>Discard</button>
              <button type="button" className="primary" onClick={importTranscription}>Import {buildSpeechCaptionCues(transcription.segments).length} smart captions</button>
            </div>
          </div>}
        </section>
        <label>Caption text<input value={caption.text} onChange={(e) => setCaption({ ...caption, text: e.target.value })} maxLength={1000} placeholder="Type your caption" /></label>
        <div className="form-grid">
          <label>Start (s)<input type="number" min="0" step=".1" value={caption.start} onChange={(e) => setCaption({ ...caption, start: e.target.value })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={caption.duration} onChange={(e) => setCaption({ ...caption, duration: e.target.value })}/></label>
        </div>
        <button className="primary" disabled={!caption.text.trim() || Number(caption.duration) <= 0} onClick={addCaption}>Add caption +</button>
      </div>}

      {selectedClip && (selectedVideo || selectedAudio || selectedCaption) && <section className="clip-inspector" aria-label="Selected clip properties">
        <div className="clip-inspector-heading"><div><p className="eyebrow">CLIP PROPERTIES</p><h3>{selectedVideo ? "Video clip" : selectedAudio ? "Audio clip" : "Caption"} inspector</h3></div>
          <div className="clip-management-actions">
            <button type="button" onClick={copySelectedClip}>Copy</button>
            <button type="button" onClick={pasteClip} disabled={!clipClipboard}>Paste at playhead</button>
            <button type="button" onClick={duplicateSelectedClip}>Duplicate</button>
            <button type="button" onClick={() => setSelectedClip(null)}>Clear selection</button>
          </div>
        </div>
        {selectedVideo && <div className="form-grid">
          <label>Timeline position (s)<input type="number" min="0" step=".1" value={selectedVideo.timelineStart} onChange={(e) => patchSelected({ timelineStart: numberValue(e.target.value, selectedVideo.timelineStart) })}/></label>
          <label>Source in (s)<input type="number" min="0" step=".1" value={selectedVideo.sourceStart} onChange={(e) => patchSelected({ sourceStart: numberValue(e.target.value, selectedVideo.sourceStart) })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={selectedVideo.duration} onChange={(e) => patchSelected({ duration: numberValue(e.target.value, selectedVideo.duration, .1) })}/></label>
          <label>Track (0-7)<input type="number" min="0" max="7" step="1" value={selectedVideo.trackIndex} onChange={(e) => patchSelected({ trackIndex: Math.min(7, numberValue(e.target.value, selectedVideo.trackIndex)) })}/></label>
          <label>Transition<select value={selectedVideo.transition} onChange={(e) => patchSelected({ transition: e.target.value as "none" | "fade" | "crossfade" })}><option value="none">None</option><option value="fade">Fade</option><option value="crossfade">Crossfade</option></select></label>
        </div>}
        {selectedVideo && <div className="clip-refinement">
          <strong>Quick AI editing suggestions</strong>
          <small>Choose a refinement to preview it. Your timeline changes only after Apply.</small>
          <div className="clip-refinement-actions">
            <button type="button" onClick={() => proposeClipRefinement(
              { duration: Math.max(0.1, selectedVideo.duration - 0.5) },
              `Shorten this shot by ${Math.min(0.5, selectedVideo.duration - 0.1).toFixed(1)} seconds`
            )} disabled={selectedVideo.duration <= 0.1}>Shorten 0.5s</button>
            <button type="button" onClick={() => {
              const asset = assets.find((item) => item.id === selectedVideo.mediaId);
              const maxDuration = asset?.duration == null ? selectedVideo.duration + 0.5 : Math.max(0, asset.duration - selectedVideo.sourceStart);
              const nextDuration = Math.min(selectedVideo.duration + 0.5, maxDuration);
              if (nextDuration > selectedVideo.duration) proposeClipRefinement({ duration: nextDuration }, `Extend this shot to ${nextDuration.toFixed(1)} seconds`);
            }} disabled={assets.some((item) => item.id === selectedVideo.mediaId && item.duration != null && selectedVideo.sourceStart + selectedVideo.duration >= item.duration - 0.001)}>Extend 0.5s</button>
            <button type="button" onClick={() => proposeClipRefinement(
              { timelineStart: Math.max(0, getTimelineDuration(doc)) },
              `Move this shot to the end of the timeline at ${getTimelineDuration(doc).toFixed(1)} seconds`
            )}>Move to end</button>
            <button type="button" onClick={() => {
              const transitions = ["none", "fade", "crossfade"] as const;
              const next = transitions[(transitions.indexOf(selectedVideo.transition) + 1) % transitions.length];
              proposeClipRefinement({ transition: next }, `Change transition to ${next}`);
            }}>Change transition</button>
          </div>
          {clipRefinement?.clipId === selectedVideo.id && <div className="clip-refinement-preview">
            <span>Preview: {clipRefinement.summary}</span>
            <div>
              <button type="button" onClick={() => setClipRefinement(null)}>Discard</button>
              <button type="button" className="primary" onClick={applyClipRefinement}>Apply refinement</button>
            </div>
          </div>}
        </div>}
        {selectedAudio && <div className="form-grid">
          <label>Timeline position (s)<input type="number" min="0" step=".1" value={selectedAudio.timelineStart} onChange={(e) => patchSelected({ timelineStart: numberValue(e.target.value, selectedAudio.timelineStart) })}/></label>
          <label>Source in (s)<input type="number" min="0" step=".1" value={selectedAudio.sourceStart} onChange={(e) => patchSelected({ sourceStart: numberValue(e.target.value, selectedAudio.sourceStart) })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={selectedAudio.duration} onChange={(e) => patchSelected({ duration: numberValue(e.target.value, selectedAudio.duration, .1) })}/></label>
          <label>Track (0-7)<input type="number" min="0" max="7" step="1" value={selectedAudio.trackIndex} onChange={(e) => patchSelected({ trackIndex: Math.min(7, numberValue(e.target.value, selectedAudio.trackIndex)) })}/></label>
          <label>Volume (0-2)<input type="number" min="0" max="2" step=".1" value={selectedAudio.volume} onChange={(e) => patchSelected({ volume: Math.min(2, numberValue(e.target.value, selectedAudio.volume)) })}/></label>
          <label>Output bus<select value={selectedAudio.bus ?? (selectedAudio.role === "other" ? "effects" : selectedAudio.role)} onChange={(e) => patchSelected({ bus: e.target.value })}><option value="dialogue">Dialogue</option><option value="music">Music</option><option value="effects">Effects</option></select></label>
          <label>Fade in (s)<input type="number" min="0" step=".1" value={selectedAudio.fadeIn} onChange={(e) => patchSelected({ fadeIn: numberValue(e.target.value, selectedAudio.fadeIn) })}/></label>
          <label>Fade out (s)<input type="number" min="0" step=".1" value={selectedAudio.fadeOut} onChange={(e) => patchSelected({ fadeOut: numberValue(e.target.value, selectedAudio.fadeOut) })}/></label>
          <div className="audio-keyframe-editor">
            <strong>Volume automation</strong>
            <small>Add a gain keyframe at the current playhead. FLEXY interpolates smoothly between points during export.</small>
            <button type="button" onClick={addAudioVolumeKeyframe}>Add keyframe at playhead</button>
            <AudioAutomationCurve
              keyframes={selectedAudio.volumeKeyframes ?? []}
              duration={selectedAudio.duration}
              playhead={playhead - selectedAudio.timelineStart}
              fallbackVolume={selectedAudio.volume}
              onChange={updateSelectedAudioKeyframes}
            />
          </div>
        </div>}
        {selectedCaption && <div className="form-grid">
          <label className="caption-inspector-text">Caption text<textarea rows={3} maxLength={1000} value={selectedCaption.text} placeholder="Write your caption. Use Enter for a new line." onChange={(e) => patchSelected({ text: e.target.value })}/></label>
          <div className="caption-preset-library">
            <strong>Quick caption presets</strong>
            <div className="caption-preset-buttons">
              {captionPresetLibrary.map((preset) => <button type="button" key={preset.id} onClick={() => applyCaptionStylePreset(preset.style)}>{preset.name}</button>)}
              {(doc.captionPresets ?? []).map((preset) => <button type="button" key={preset.id} onClick={() => applyCaptionStylePreset(preset.style)}>{preset.name}</button>)}
            </div>
            <div className="caption-save-preset">
              <input aria-label="Custom caption preset name" maxLength={32} placeholder="Name this style…" value={captionPresetName} onChange={(e) => setCaptionPresetName(e.target.value)}/>
              <button type="button" disabled={!captionPresetName.trim()} onClick={saveCaptionStylePreset}>Save current style</button>
            </div>
            <small>Saved custom presets stay with this project and can be reused on its captions.</small>
          </div>
          <label>Timeline position (s)<input type="number" min="0" step=".1" value={selectedCaption.start} onChange={(e) => patchSelected({ start: numberValue(e.target.value, selectedCaption.start) })}/></label>
          <label>Duration (s)<input type="number" min=".1" step=".1" value={selectedCaption.duration} onChange={(e) => patchSelected({ duration: numberValue(e.target.value, selectedCaption.duration, .1) })}/></label>
          <label>Style preset<select value={selectedCaption.style?.preset ?? "classic"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), preset: e.target.value } })}>
            <option value="classic">Classic</option><option value="bold">Bold impact</option><option value="minimal">Minimal</option><option value="neon">Neon glow</option>
          </select></label>
          <label>Position<select value={selectedCaption.style?.position ?? "bottom"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), position: e.target.value } })}>
            <option value="bottom">Bottom</option><option value="top">Top</option>
          </select></label>
          <label>Font size<input type="number" min="12" max="72" value={selectedCaption.style?.fontSize ?? 28} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), fontSize: numberValue(e.target.value, 28, 12) } })}/></label>
          <label>Text color<input type="color" value={selectedCaption.style?.color ?? "#ffffff"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), color: e.target.value } })}/></label>
          <label>Background color<input type="color" value={(selectedCaption.style?.backgroundColor ?? "#000000b8").slice(0,7)} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), backgroundColor: `${e.target.value}b8` } })}/></label>
          <label className="caption-bold-toggle"><input type="checkbox" checked={selectedCaption.style?.bold ?? true} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), bold: e.target.checked } })}/> Bold text</label>
          <label>Animation<select value={selectedCaption.style?.animation ?? "none"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), animation: e.target.value } })}>
            <option value="none">None</option><option value="word">Word reveal</option><option value="karaoke">Karaoke highlight</option>
            <option value="pop">Pop</option><option value="fade">Fade</option><option value="slide">Slide up</option>
          </select></label>
          <label>Animation time (s)<input type="number" min="0.1" max="2" step="0.05" value={selectedCaption.style?.animationDuration ?? 0.45}
            onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), animationDuration: Math.max(0.1, Math.min(2, numberValue(e.target.value, 0.45, 0.1))) } })}/></label>
          <label>Text alignment<select value={selectedCaption.style?.alignment ?? "center"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), alignment: e.target.value } })}>
            <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
          </select></label>
          <label>Vertical position (%)<input type="number" min="0" max="100" value={selectedCaption.style?.verticalOffset ?? 7}
            onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), verticalOffset: Math.min(100, numberValue(e.target.value, 7)) } })}/></label>
          <label>Outline color<input type="color" value={selectedCaption.style?.outlineColor ?? "#000000"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), outlineColor: e.target.value } })}/></label>
          <label>Outline width (px)<input type="number" min="0" max="8" step=".5" value={selectedCaption.style?.outlineWidth ?? 0}
            onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), outlineWidth: Math.min(8, numberValue(e.target.value, 0)) } })}/></label>
          <label>Shadow color<input type="color" value={selectedCaption.style?.shadowColor ?? "#000000"} onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), shadowColor: e.target.value } })}/></label>
          <label>Shadow blur (px)<input type="number" min="0" max="32" value={selectedCaption.style?.shadowBlur ?? 0}
            onChange={(e) => patchSelected({ style: { ...(selectedCaption.style ?? {}), shadowBlur: Math.min(32, numberValue(e.target.value, 0)) } })}/></label>
        </div>}
      </section>}

      <PlaybackPreview document={doc} assets={assets} projectId={projectId} playhead={playhead} onPlayheadChange={setPlayhead}
        playbackRate={playbackRate} onPlaybackRateChange={setPlaybackRate} />
      <div className="timeline-lanes">
        <div className="timeline-toolbar">
          <h3>Timeline tracks</h3>
          <label className="snap-toggle"><input type="checkbox" checked={snapEnabled} onChange={(e) => setSnapEnabled(e.target.checked)} /> Magnetic snap</label>
          <div className="history-controls">
            <button disabled={!history.length} onClick={undo} title="Undo (Ctrl/Cmd+Z)">↶ Undo</button>
            <button disabled={!future.length} onClick={redo} title="Redo (Ctrl/Cmd+Y)">↷ Redo</button>
            <button onClick={() => frameStep(-1)} title="Previous frame">◀|</button>
            <button onClick={() => frameStep(1)} title="Next frame">|▶</button>
          </div>
          <label>Zoom <input aria-label="Timeline zoom" type="range" min="0.5" max="4" step="0.25" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
          <span>{playhead.toFixed(1)}s</span>
        </div>
        <div className="playhead-ruler" onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          setPlayhead(Math.max(0, Math.min(duration, ((e.clientX - rect.left) / rect.width) * Math.max(10, duration) / zoom)));
        }}>
          <span>Click ruler to move playhead</span><i style={{ left: `${Math.min(100, playhead / Math.max(10, duration) * zoom * 100)}%` }} />
        </div>
        {Array.from({ length: Math.max(1, ...doc.videoClips.map((x) => x.trackIndex + 1)) }, (_, index) => (
          <Track key={`video-${index}`} label={trackNames[`video-${index}`] || `VIDEO ${index + 1}`} trackKey={`video-${index}`} accent={trackColors[`video-${index}`] || "violet"} onRename={(name) => updateTrackMeta(`video-${index}`, { name })} onAccentChange={(color) => updateTrackMeta(`video-${index}`, { color })} color="video" locked={!!lockedTracks[`video-${index}`]} hidden={hiddenVideoTracks.includes(index)} onToggleVisibility={() => toggleTrackVisibility("video", index)} onToggleLock={() => toggleTrackLock(`video-${index}`)}
            viewDuration={Math.max(10, duration) / zoom} beatMarkers={beatTimelineMarkers}
            items={doc.videoClips.filter((x) => x.trackIndex === index).map((x) => ({
              id:x.id,title:assets.find((a) => a.id === x.mediaId)?.filename ?? x.mediaId,selected:selectedClip?.id === x.id && selectedClip.type === "video",onSelect:() => setSelectedClip({id:x.id,type:"video"}),
              start:x.timelineStart,duration:x.duration,
              change:(start:number, source:number, len:number) => editVideo(x.id,start,source,len),
              split:() => splitVideo(x.id,playhead),remove:() => remove(x.id,"video"),
            }))} snapEnabled={snapEnabled} snapPoints={snapPoints} onSnapGuide={setSnapGuide} />
        ))}
        {Array.from({ length: Math.max(1, ...doc.audioClips.map((x) => x.trackIndex + 1)) }, (_, index) => (
          <Track key={`audio-${index}`} label={trackNames[`audio-${index}`] || `AUDIO ${index + 1}`} trackKey={`audio-${index}`} accent={trackColors[`audio-${index}`] || "mint"} onRename={(name) => updateTrackMeta(`audio-${index}`, { name })} onAccentChange={(color) => updateTrackMeta(`audio-${index}`, { color })} color="audio" locked={!!lockedTracks[`audio-${index}`]} hidden={hiddenAudioTracks.includes(index)} solo={doc.soloAudioTrack === index} onToggleVisibility={() => toggleTrackVisibility("audio", index)} onToggleSolo={() => toggleAudioTrackSolo(index)} onToggleLock={() => toggleTrackLock(`audio-${index}`)} onToggleMute={() => toggleAudioTrackMute(index)} viewDuration={Math.max(10, duration) / zoom} beatMarkers={beatTimelineMarkers}
            items={doc.audioClips.filter((x) => x.trackIndex === index).map((x) => ({
              id:x.id,title:assets.find((a) => a.id === x.mediaId)?.filename ?? x.mediaId,selected:selectedClip?.id === x.id && selectedClip.type === "audio",onSelect:() => setSelectedClip({id:x.id,type:"audio"}),
              start:x.timelineStart,duration:x.duration,
              change:(start:number, source:number, len:number) => editAudio(x.id,start,source,len),
              split:() => splitAudio(x.id,playhead),remove:() => remove(x.id,"audio"),
            }))} snapEnabled={snapEnabled} snapPoints={snapPoints} onSnapGuide={setSnapGuide} />
        ))}
        <Track label={trackNames["captions"] || "CAPTIONS"} trackKey="captions" accent={trackColors["captions"] || "amber"} onRename={(name) => updateTrackMeta("captions", { name })} onAccentChange={(color) => updateTrackMeta("captions", { color })} color="caption" locked={!!lockedTracks["captions"]} hidden={captionsHidden} onToggleVisibility={() => toggleTrackVisibility("captions") } onToggleLock={() => toggleTrackLock("captions")} viewDuration={Math.max(10, duration) / zoom} beatMarkers={beatTimelineMarkers}
          items={doc.captions.map((x) => ({
            id:x.id,title:x.text,selected:selectedClip?.id === x.id && selectedClip.type === "caption",onSelect:() => setSelectedClip({id:x.id,type:"caption"}),start:x.start,duration:x.duration,
            change:(start:number, _source:number, len:number) => editCaption(x.id,start,len),
            split:() => splitCaption(x.id,playhead),remove:() => remove(x.id,"caption"),
          }))} snapEnabled={snapEnabled} snapPoints={snapPoints} onSnapGuide={setSnapGuide} />
        {snapGuide !== null && <div className="snap-guide-readout">Snap guide · {snapGuide.toFixed(2)}s</div>}
      </div>
      {errors.length > 0 && <ul className="timeline-errors">{errors.map((error) => <li key={error}>{error}</li>)}</ul>}
      <details className="graph-preview"><summary>Inspect generated render graph</summary><pre>{JSON.stringify(graph, null, 2)}</pre></details>
    </section>
  );
}


function Track({ label, color, items, viewDuration, beatMarkers = [], snapEnabled, snapPoints, onSnapGuide, locked = false, muted = false, onToggleLock, onToggleMute, hidden = false, solo = false, onToggleVisibility, onToggleSolo, trackKey, accent = "violet", onRename, onAccentChange }: {
  label: string;
  color: string;
  viewDuration: number;
  beatMarkers?: number[];
  snapEnabled: boolean;
  snapPoints: number[];
  onSnapGuide: (time:number | null) => void;
  locked?: boolean; muted?: boolean; hidden?: boolean; solo?: boolean; trackKey: string; accent?: string; onRename: (name: string) => void; onAccentChange: (color: string) => void; onToggleLock: () => void; onToggleMute?: () => void; onToggleVisibility: () => void; onToggleSolo?: () => void;
  items: Array<{
    id:string; title:string; start:number; duration:number;
    change:(start:number,sourceStart:number,duration:number)=>void;
    split:()=>void; remove:()=>void;
  }>;
}) {
  const [drag, setDrag] = useState<{id:string; mode:"move"|"left"|"right"; x:number; start:number; duration:number} | null>(null);
  const pixelsPerSecond = 100 / Math.max(1, viewDuration);
  const begin = (event: React.PointerEvent<HTMLDivElement>, item: typeof items[number], mode:"move"|"left"|"right") => {
    event.preventDefault();
    event.stopPropagation();
    if (locked) return;
    onSnapGuide(null);
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({id:item.id,mode,x:event.clientX,start:item.start,duration:item.duration});
  };
  const move = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    const delta = (event.clientX - drag.x) / (event.currentTarget.getBoundingClientRect().width || 1) * viewDuration;
    const item = items.find((x) => x.id === drag.id);
    if (!item) return;
    let adjustedDelta = delta;
    let guide: number | null = null;
    if (snapEnabled) {
      const rawStart = drag.mode === "move" ? drag.start + delta : drag.mode === "left" ? drag.start + delta : drag.start;
      const rawEnd = drag.mode === "right" ? drag.start + drag.duration + delta : drag.mode === "left" ? drag.start + drag.duration : rawStart + drag.duration;
      const candidates = drag.mode === "move"
        ? snapPoints.flatMap((point) => [{edge:rawStart,time:point},{edge:rawEnd,time:point}])
        : drag.mode === "left" ? snapPoints.map((point) => ({edge:rawStart,time:point}))
        : snapPoints.map((point) => ({edge:rawEnd,time:point}));
      const nearest = candidates.map((candidate) => ({...candidate,distance:Math.abs(candidate.edge-candidate.time)}))
        .filter((candidate) => candidate.distance <= Math.max(0.08, 8 / pixelsPerSecond))
        .sort((a,b) => a.distance-b.distance)[0];
      if (nearest) {
        adjustedDelta += nearest.time - nearest.edge;
        guide = nearest.time;
      }
    }
    onSnapGuide(guide);
    if (drag.mode === "move") item.change(Math.max(0,drag.start+adjustedDelta),0,drag.duration);
    if (drag.mode === "left") {
      const shift = Math.max(-drag.start,Math.min(drag.duration-0.1,adjustedDelta));
      item.change(drag.start+shift,shift,drag.duration-shift);
    }
    if (drag.mode === "right") item.change(drag.start,0,Math.max(0.1,drag.duration+adjustedDelta));
  };
  const end = () => { setDrag(null); onSnapGuide(null); };
  return <div className={`track-row accent-${accent}${locked ? " track-locked" : ""}${muted ? " track-muted" : ""}${hidden ? " track-hidden" : ""}${solo ? " track-solo" : ""}`}>
    <div className="track-controls">
    <input className="track-name-input" aria-label={`Rename ${label}`} value={label} maxLength={32} onChange={(event) => onRename(event.target.value)} />
      <select className="track-accent-select" aria-label={`Color for ${label}`} value={accent} onChange={(event) => onAccentChange(event.target.value)}>
        <option value="violet">Violet</option><option value="mint">Mint</option><option value="amber">Amber</option><option value="rose">Rose</option><option value="blue">Blue</option>
      </select>
      <div className="track-control-buttons">
        <button type="button" className={locked ? "active" : ""} aria-label={`${locked ? "Unlock" : "Lock"} ${label}`} title={locked ? "Unlock track" : "Lock track"} onClick={onToggleLock}>{locked ? "🔒" : "🔓"}</button>
        <button type="button" className={hidden ? "active" : ""} aria-label={`${hidden ? "Show" : "Hide"} ${label}`} title={hidden ? "Show track in export" : "Hide track from export"} onClick={onToggleVisibility}>{hidden ? "◉̸" : "◉"}</button>
        {onToggleSolo && <button type="button" className={solo ? "active" : ""} aria-label={`${solo ? "Unsolo" : "Solo"} ${label}`} title={solo ? "Disable solo" : "Solo this track"} onClick={onToggleSolo}>S</button>}
        {onToggleMute && <button type="button" className={muted ? "active" : ""} aria-label={`${muted ? "Unmute" : "Mute"} ${label}`} title={muted ? "Unmute track" : "Mute track"} onClick={onToggleMute}>{muted ? "🔇" : "🔊"}</button>}
      </div>
    </div>
    <div className="track-rail" style={{minWidth:560}} onPointerMove={move} onPointerUp={end} onPointerCancel={end}>
      {beatMarkers.filter((time) => time >= 0 && time <= viewDuration).map((time, index) => <span key={`beat-${time}-${index}`} className="timeline-beat-marker" style={{left:`${time / viewDuration * 100}%`}} title={`Detected beat candidate · ${time.toFixed(2)}s`} aria-hidden="true" />)}
      {drag && snapEnabled && <span className="magnetic-guide" style={{left:`${Math.min(100,Math.max(0,((snapPoints.find((point) => Math.abs(point - (snapGuide ?? -999)) < 0.0001) ?? -1)/viewDuration)*100))}%`}} />}
      {items.map((item) => <div className={`track-clip ${color}${item.selected ? " selected" : ""}`} key={item.id} onClick={item.onSelect} role="button" tabIndex={0} aria-pressed={!!item.selected} onKeyDown={(e)=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();item.onSelect();}}}
        style={{left:`${item.start/viewDuration*100}%`,width:`${Math.max(1.5,item.duration/viewDuration*100)}%`}}
        title={`${item.title} · ${item.duration.toFixed(1)}s`}>
        <button className="trim-handle left" aria-label={`Trim start of ${item.title}`} disabled={locked} onPointerDown={(e)=>begin(e,item,"left")} />
        <span onPointerDown={(e)=>begin(e,item,"move")}>{item.title || "Clip"}</span>
        <div className="clip-actions">
          <button aria-label={`Split ${item.title} at playhead`} disabled={locked} onClick={(e)=>{e.stopPropagation();item.split();}}>✂</button>
          <button aria-label={`Remove ${item.title}`} disabled={locked} onClick={(e)=>{e.stopPropagation();item.remove();}}>×</button>
        </div>
        <button className="trim-handle right" aria-label={`Trim end of ${item.title}`} disabled={locked} onPointerDown={(e)=>begin(e,item,"right")} />
      </div>)}
      {items.length===0&&<small>Empty track</small>}
    </div>
  </div>;
}
