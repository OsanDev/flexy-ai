import { useEffect, useMemo, useRef, useState } from "react";
import { mediaApi, type MediaAsset } from "../lib/mediaApi";
import type { TimelineDocument } from "../lib/timelineGraph";
import { volumeAtTime } from "../lib/audioAutomation";
import { dbfsToMeterPercent, peakToDbfs } from "../lib/audioMeter";

const API = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const mediaUrl = (id: string) => `${API}/api/media/${encodeURIComponent(id)}`;

type Props = {
  document: TimelineDocument;
  assets: MediaAsset[];
  projectId: string;
  playhead: number;
  onPlayheadChange: (time: number) => void;
  playbackRate: number;
  onPlaybackRateChange: (rate: number) => void;
};

export function PlaybackPreview({ document, assets, projectId, playhead, onPlayheadChange, playbackRate, onPlaybackRateChange }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const audioGraphRef = useRef<{
    context: AudioContext;
    clips: Record<string, { source: MediaElementAudioSourceNode; gain: GainNode; bus: "dialogue" | "music" | "effects" }>;
    busGains: Record<"dialogue" | "music" | "effects", GainNode>;
    busAnalysers: Record<"dialogue" | "music" | "effects", AnalyserNode>;
    masterGain: GainNode;
    masterAnalyser: AnalyserNode;
  } | null>(null);
  const meterFrameRef = useRef<number | null>(null);
  const [meterLevels, setMeterLevels] = useState<Record<string, number>>({ dialogue: -90, music: -90, effects: -90, master: -90 });
  const [meterAvailable, setMeterAvailable] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyUrl, setProxyUrl] = useState<string | null>(null);
  const [proxyBusy, setProxyBusy] = useState(false);
  const [proxyError, setProxyError] = useState("");
  const scrubFrameRef = useRef<number | null>(null);
  const pendingScrubRef = useRef<number | null>(null);
  const activeClip = useMemo(() => document.videoClips
    .filter((clip) => playhead >= clip.timelineStart && playhead < clip.timelineStart + clip.duration)
    .sort((a,b) => b.trackIndex - a.trackIndex)[0] ?? null, [document.videoClips, playhead]);
  const activeCaption = document.captions.find((caption) =>
    playhead >= caption.start && playhead < caption.start + caption.duration);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeClip) return;
    const desired = activeClip.sourceStart + Math.max(0, playhead - activeClip.timelineStart);
    if (Number.isFinite(desired) && Math.abs(video.currentTime - desired) > 0.35) {
      try { video.currentTime = desired; } catch { /* metadata may not be ready */ }
    }
  }, [activeClip?.id, activeClip?.sourceStart, activeClip?.timelineStart, playhead]);

  useEffect(() => {
    for (const clip of document.audioClips) {
      const audio = audioRefs.current[clip.id];
      if (!audio) continue;
      const inside = playhead >= clip.timelineStart && playhead < clip.timelineStart + clip.duration;
      const sourceTime = clip.sourceStart + Math.max(0, playhead - clip.timelineStart);
      if (inside && Math.abs(audio.currentTime - sourceTime) > 0.45) {
        try { audio.currentTime = sourceTime; } catch { /* metadata may not be ready */ }
      }
      const elapsed = Math.max(0, playhead - clip.timelineStart);
      const remaining = Math.max(0, clip.duration - elapsed);
      const fadeInGain = clip.fadeIn > 0 ? Math.min(1, elapsed / clip.fadeIn) : 1;
      const fadeOutGain = clip.fadeOut > 0 ? Math.min(1, remaining / clip.fadeOut) : 1;
      const automationGain = volumeAtTime(clip.volumeKeyframes ?? [], elapsed, 1);
      const graph = audioGraphRef.current;
      const clipNode = graph?.clips[clip.id];
      if (clipNode) {
        audio.volume = 1;
        clipNode.gain.gain.setTargetAtTime(Math.max(0, clip.volume * fadeInGain * fadeOutGain * automationGain), graph!.context.currentTime, 0.015);
      } else {
        const mixer = document.audioMixer ?? {
          dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false },
          effects: { gain: 1, muted: false }, master: { gain: 1, muted: false },
        };
        const bus = clip.bus ?? (clip.role === "other" ? "effects" : clip.role);
        const busSettings = mixer[bus];
        const mixerGain = busSettings.muted || mixer.master.muted ? 0 : busSettings.gain * mixer.master.gain;
        audio.volume = muted ? 0 : Math.min(1, Math.max(0, clip.volume * fadeInGain * fadeOutGain * automationGain * mixerGain));
      }
      audio.playbackRate = playbackRate;
      if (playing && inside) void audio.play().catch(() => undefined);
      else audio.pause();
    }
  }, [document.audioClips, playhead, playing, muted, playbackRate]);

  const ensureAudioGraph = () => {
    if (audioGraphRef.current) {
      void audioGraphRef.current.context.resume();
      return audioGraphRef.current;
    }
    try {
      const context = new AudioContext();
      const busNames = ["dialogue", "music", "effects"] as const;
      const busGains = {} as Record<typeof busNames[number], GainNode>;
      const busAnalysers = {} as Record<typeof busNames[number], AnalyserNode>;
      for (const bus of busNames) {
        const gain = context.createGain();
        const analyser = context.createAnalyser();
        analyser.fftSize = 2048;
        gain.connect(analyser);
        busGains[bus] = gain;
        busAnalysers[bus] = analyser;
      }
      const masterGain = context.createGain();
      const masterAnalyser = context.createAnalyser();
      masterAnalyser.fftSize = 2048;
      for (const bus of busNames) busAnalysers[bus].connect(masterGain);
      masterGain.connect(masterAnalyser);
      masterAnalyser.connect(context.destination);
      const mixer = document.audioMixer ?? {
        dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false },
        effects: { gain: 1, muted: false }, master: { gain: 1, muted: false },
      };
      for (const bus of busNames) busGains[bus].gain.value = mixer[bus].muted ? 0 : mixer[bus].gain;
      masterGain.gain.value = muted || mixer.master.muted ? 0 : mixer.master.gain;
      const graph = { context, clips: {} as Record<string, { source: MediaElementAudioSourceNode; gain: GainNode; bus: "dialogue" | "music" | "effects" }>, busGains, busAnalysers, masterGain, masterAnalyser };
      audioGraphRef.current = graph;
      for (const clip of document.audioClips) {
        const element = audioRefs.current[clip.id];
        if (!element) continue;
        const source = context.createMediaElementSource(element);
        const gain = context.createGain();
        const bus = clip.bus ?? (clip.role === "other" ? "effects" : clip.role);
        source.connect(gain);
        gain.connect(busGains[bus]);
        graph.clips[clip.id] = { source, gain, bus };
      }
      void context.resume();
      setMeterAvailable(true);
      return graph;
    } catch {
      setMeterAvailable(false);
      return null;
    }
  };

  useEffect(() => {
    const graph = audioGraphRef.current;
    if (!graph) return;
    const mixer = document.audioMixer ?? {
      dialogue: { gain: 1, muted: false }, music: { gain: 1, muted: false },
      effects: { gain: 1, muted: false }, master: { gain: 1, muted: false },
    };
    for (const bus of ["dialogue", "music", "effects"] as const) {
      const settings = mixer[bus];
      graph.busGains[bus].gain.setTargetAtTime(settings.muted ? 0 : settings.gain, graph.context.currentTime, 0.02);
    }
    graph.masterGain.gain.setTargetAtTime(muted || mixer.master.muted ? 0 : mixer.master.gain, graph.context.currentTime, 0.02);
  }, [document.audioMixer, muted, document.audioClips]);

  useEffect(() => {
    if (!playing) setMeterLevels({ dialogue: -90, music: -90, effects: -90, master: -90 });
  }, [playing]);

  useEffect(() => {
    const graph = audioGraphRef.current;
    if (!graph || !playing) return;
    let lastPublish = 0;
    const sample = (time: number) => {
      const readPeak = (analyser: AnalyserNode) => {
        const samples = new Float32Array(analyser.fftSize);
        analyser.getFloatTimeDomainData(samples);
        let peak = 0;
        for (const value of samples) peak = Math.max(peak, Math.abs(value));
        return peakToDbfs(peak);
      };
      if (time - lastPublish > 90) {
        setMeterLevels({
          dialogue: readPeak(graph.busAnalysers.dialogue),
          music: readPeak(graph.busAnalysers.music),
          effects: readPeak(graph.busAnalysers.effects),
          master: readPeak(graph.masterAnalyser),
        });
        lastPublish = time;
      }
      meterFrameRef.current = requestAnimationFrame(sample);
    };
    meterFrameRef.current = requestAnimationFrame(sample);
    return () => { if (meterFrameRef.current !== null) cancelAnimationFrame(meterFrameRef.current); meterFrameRef.current = null; };
  }, [playing]);

  useEffect(() => () => {
    if (meterFrameRef.current !== null) cancelAnimationFrame(meterFrameRef.current);
    const graph = audioGraphRef.current;
    if (graph) void graph.context.close();
    audioGraphRef.current = null;
  }, []);

  useEffect(() => {
    const graph = audioGraphRef.current;
    if (!graph) return;
    const currentIds = new Set(document.audioClips.map((clip) => clip.id));
    for (const [clipId, nodes] of Object.entries(graph.clips)) {
      if (currentIds.has(clipId)) continue;
      nodes.source.disconnect();
      nodes.gain.disconnect();
      delete graph.clips[clipId];
    }
    for (const clip of document.audioClips) {
      const nextBus = clip.bus ?? (clip.role === "other" ? "effects" : clip.role);
      const existing = graph.clips[clip.id];
      if (existing) {
        if (existing.bus !== nextBus) {
          existing.gain.disconnect();
          existing.gain.connect(graph.busGains[nextBus]);
          existing.bus = nextBus;
        }
        continue;
      }
      const element = audioRefs.current[clip.id];
      if (!element) continue;
      try {
        const source = graph.context.createMediaElementSource(element);
        const gain = graph.context.createGain();
        source.connect(gain);
        gain.connect(graph.busGains[nextBus]);
        graph.clips[clip.id] = { source, gain, bus: nextBus };
      } catch { setMeterAvailable(false); }
    }
  }, [document.audioClips]);

  useEffect(() => {
    if (!playing) return;
    const video = videoRef.current;
    if (video && activeClip) { video.playbackRate = playbackRate; void video.play().catch(() => setPlaying(false)); }
    else video?.pause();
    return () => video?.pause();
  }, [playing, activeClip?.id, playbackRate]);

  const togglePlayback = () => {
    const next = !playing;
    if (next) ensureAudioGraph();
    setPlaying(next);
    if (next) {
      const video = videoRef.current;
      if (video && activeClip) { video.playbackRate = playbackRate; void video.play().catch(() => setPlaying(false)); }
    } else {
      videoRef.current?.pause();
      Object.values(audioRefs.current).forEach((audio) => audio?.pause());
    }
  };

  const seek = (time: number) => onPlayheadChange(Math.max(0, Math.min(duration || 1800, time)));
  const scheduleScrub = (time: number) => {
    pendingScrubRef.current = Math.max(0, Math.min(duration || 1800, time));
    if (scrubFrameRef.current !== null) return;
    scrubFrameRef.current = requestAnimationFrame(() => {
      scrubFrameRef.current = null;
      if (pendingScrubRef.current !== null) {
        onPlayheadChange(pendingScrubRef.current);
        pendingScrubRef.current = null;
      }
    });
  };
  useEffect(() => () => {
    if (scrubFrameRef.current !== null) cancelAnimationFrame(scrubFrameRef.current);
  }, []);
  const onVideoTime = () => {
    if (!activeClip || !videoRef.current) return;
    const local = videoRef.current.currentTime - activeClip.sourceStart;
    seek(activeClip.timelineStart + Math.max(0, local));
  };
  const activeAsset = activeClip ? assets.find((asset) => asset.id === activeClip.mediaId) : null;
  const isVideo = activeAsset?.mime_type.startsWith("video/");
  const isImage = activeAsset?.mime_type.startsWith("image/");

  useEffect(() => {
    let cancelled = false;
    let createdUrl: string | null = null;
    setProxyError("");
    setProxyUrl(null);
    if (!proxyEnabled || !activeClip || !isVideo) {
      setProxyBusy(false);
      return () => { cancelled = true; };
    }
    setProxyBusy(true);
    mediaApi.proxyPreview(projectId, activeClip.mediaId)
      .then((url) => {
        createdUrl = url;
        if (cancelled) URL.revokeObjectURL(url);
        else setProxyUrl(url);
      })
      .catch((cause) => {
        if (!cancelled) setProxyError(cause instanceof Error ? cause.message : "Proxy preview could not be created.");
      })
      .finally(() => { if (!cancelled) setProxyBusy(false); });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [proxyEnabled, activeClip?.mediaId, isVideo, activeAsset?.id, projectId]);

  useEffect(() => {
    const end = Math.max(0,
      ...document.videoClips.map((x) => x.timelineStart + x.duration),
      ...document.audioClips.map((x) => x.timelineStart + x.duration),
      ...document.captions.map((x) => x.start + x.duration));
    setDuration(end);
    if (playhead > end && end > 0) onPlayheadChange(end);
  }, [document.videoClips, document.audioClips, document.captions]);

  return <section className="playback-preview" aria-label="Timeline playback preview">
    <div className="preview-heading"><div><span className="eyebrow">LIVE PREVIEW</span><strong>Playback monitor</strong></div>
      <span className={playing ? "preview-status is-playing" : "preview-status"}>{playing ? "PLAYING" : "PAUSED"}</span>
    </div>
    <div className="preview-stage">
      {isVideo && activeClip ? <video ref={videoRef} src={proxyEnabled && proxyUrl ? proxyUrl : mediaUrl(activeClip.mediaId)} onTimeUpdate={onVideoTime}
        onLoadedMetadata={(event) => { const v=event.currentTarget; try { v.currentTime=activeClip.sourceStart + Math.max(0,playhead-activeClip.timelineStart); } catch {} }}
        playsInline preload="metadata" /> :
       isImage && activeClip ? <img src={mediaUrl(activeClip.mediaId)} alt="Current timeline frame" /> :
       <div className="preview-empty"><span>FLEXY AI</span><small>{activeClip ? "This asset type cannot be previewed here" : "Add a video or image clip to preview"}</small></div>}
      {activeCaption && (() => {
        const style = activeCaption.style;
        const animation = style?.animation ?? "none";
        const words = activeCaption.text.trim().split(/\\s+/).filter(Boolean);
        const elapsed = Math.max(0, playhead - activeCaption.start);
        const animationTime = Math.max(0.1, Math.min(2, style?.animationDuration ?? 0.45));
        const revealProgress = Math.min(1, elapsed / Math.min(activeCaption.duration, animationTime));
        const activeWord = Math.min(words.length - 1, Math.floor((elapsed / Math.max(0.001, activeCaption.duration)) * words.length));
        return <div key={`${activeCaption.id}-${animation}`} className={`preview-caption caption-preset-${style?.preset ?? "classic"} caption-position-${style?.position ?? "bottom"} caption-animation-${animation}`}
          style={{
            fontSize: `${Math.max(12, Math.min(72, style?.fontSize ?? 28))}px`,
            color: style?.color ?? "#ffffff",
            backgroundColor: style?.backgroundColor ?? "#000000b8",
            fontWeight: style?.bold === false ? 500 : 800,
            textAlign: style?.alignment ?? "center",
            WebkitTextStroke: `${Math.max(0, Math.min(8, style?.outlineWidth ?? 0))}px ${style?.outlineColor ?? "#000000"}`,
            textShadow: `0 2px ${Math.max(0, Math.min(32, style?.shadowBlur ?? 0))}px ${style?.shadowColor ?? "#000000"}`,
            top: style?.position === "top" ? `${Math.max(0, Math.min(100, style?.verticalOffset ?? 7))}%` : undefined,
            bottom: style?.position !== "top" ? `${Math.max(0, Math.min(100, style?.verticalOffset ?? 7))}%` : undefined,
            animationDuration: `${animationTime}s`,
          }}>
          {animation === "word" ? words.slice(0, Math.ceil(words.length * revealProgress)).join(" ") :
            animation === "karaoke" ? words.map((word, index) => <span key={`${index}-${word}`} className={index === activeWord ? "caption-word-active" : "caption-word"}>{word}{index < words.length - 1 ? " " : ""}</span>) :
            activeCaption.text}
        </div>;
      })()}
    </div>
    {document.audioClips.map((clip) => <audio key={clip.id} ref={(node) => { audioRefs.current[clip.id] = node; }}
      src={mediaUrl(clip.mediaId)} preload="metadata" />)}
    <div className="preview-controls">
      <button className="primary" onClick={togglePlayback}>{playing ? "Pause" : "Play"}</button>
      <button className="secondary" onClick={() => { setPlaying(false); seek(0); }}>Restart</button>
      <button className="secondary" onClick={() => setMuted(!muted)}>{muted ? "Unmute" : "Mute"}</button>
      <button className={proxyEnabled ? "primary" : "secondary"} onClick={() => setProxyEnabled((value) => !value)}
        disabled={!isVideo || proxyBusy}>{proxyBusy ? "Preparing proxy…" : proxyEnabled ? "Proxy preview: ON" : "Performance preview"}</button>
      <label className="speed-control">Speed <select aria-label="Playback speed" value={playbackRate} onChange={(event) => onPlaybackRateChange(Number(event.target.value))}>
        {[0.25,0.5,0.75,1,1.25,1.5,2].map((rate) => <option key={rate} value={rate}>{rate}×</option>)}
      </select></label>
      <span>{playhead.toFixed(2)}s / {duration.toFixed(2)}s</span>
    </div>
    <section className="preview-audio-meters" aria-label="Live audio peak meters">
      <div className="meter-heading"><strong>LIVE AUDIO METERS</strong><small>{meterAvailable ? (playing ? "Peak dBFS · browser playback" : "Waiting for playback") : "Web Audio metering unavailable"}</small></div>
      {(["dialogue", "music", "effects", "master"] as const).map((bus) => {
        const db = meterLevels[bus];
        const percent = dbfsToMeterPercent(db);
        return <div className="preview-meter-row" key={bus}>
          <span>{bus}</span><div className="preview-meter-track"><i style={{ width: `${percent}%` }} /></div><output>{db <= -89 ? "−∞" : `${db.toFixed(1)} dB`}</output>
        </div>;
      })}
    </section>
    <input aria-label="Preview seek" className="preview-seek" type="range" min="0" max={Math.max(0.1,duration)} step="0.01"
      value={Math.min(playhead,duration || 0)} onChange={(event) => scheduleScrub(Number(event.target.value))} />
    {proxyError && <p className="preview-note" role="alert">{proxyError}</p>}
    <p className="preview-note">Performance preview creates a cached 540p proxy to reduce decode load. Original media remains unchanged. Preview uses your signed-in media session. Browser playback and audio synchronization depend on the media server and browser support.</p>
  </section>;
}
