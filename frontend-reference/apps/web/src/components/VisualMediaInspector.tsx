import { useEffect, useRef, useState } from "react";
import type { MediaAsset } from "../lib/mediaApi";
import { mediaApi, type SceneVisionResult } from "../lib/mediaApi";
import { analyzePreviewPixels, type VisualProfile } from "../lib/visualMediaAnalysis";
import { rankShots } from "../lib/visualShotRanking";

type Props = {
  assets: MediaAsset[];
  projectId: string;
  onCreateEditPlan?: (instruction: string) => void;
  onAddShotToTimeline?: (asset: MediaAsset, sourceStart: number) => void;
};
type InspectedAsset = { asset: MediaAsset; url: string | null; profile: VisualProfile | null; error?: string };
type StoryboardScene = {
  timestamp: number; description: string | null; objects: string[]; actions: string[];
  editing_notes: string[]; confidence?: number; available: boolean; notice: string;
  visual_interest?: number; thumbnailUrl: string | null;
};

export function VisualMediaInspector({ assets, projectId, onCreateEditPlan, onAddShotToTimeline }: Props) {
  const visualAssets = assets.filter((asset) => asset.mime_type.startsWith("image/") || asset.mime_type.startsWith("video/")).slice(0, 12);
  const [items, setItems] = useState<InspectedAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [visionBusy, setVisionBusy] = useState<string | null>(null);
  const [visionResults, setVisionResults] = useState<Record<string, SceneVisionResult["analysis"]>>({});
  const [visionErrors, setVisionErrors] = useState<Record<string, string>>({});
  const [storyboardBusy, setStoryboardBusy] = useState<string | null>(null);
  const [storyboards, setStoryboards] = useState<Record<string, StoryboardScene[]>>({});
  const [storyboardErrors, setStoryboardErrors] = useState<Record<string, string>>({});
  const [framePreview, setFramePreview] = useState<{ assetId: string; timestamp: number; url: string } | null>(null);
  const [framePreviewBusy, setFramePreviewBusy] = useState<string | null>(null);
  const [visualWeight, setVisualWeight] = useState(25);
  const storyboardUrls = useRef<string[]>([]);

  useEffect(() => () => {
    if (framePreview?.url) URL.revokeObjectURL(framePreview.url);
  }, [framePreview]);

  useEffect(() => () => {
    storyboardUrls.current.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    setItems([]);
    if (!visualAssets.length) { setLoading(false); return () => { active = false; }; }
    setLoading(true);
    void (async () => {
      const results: InspectedAsset[] = [];
      for (const asset of visualAssets) {
        try {
          const url = await mediaApi.preview(projectId, asset);
          if (url) {
            if (!active) { URL.revokeObjectURL(url); break; }
            urls.push(url);
            const image = new Image();
            image.src = url;
            const loaded = await new Promise<boolean>((resolve) => {
              image.onload = () => resolve(true);
              image.onerror = () => resolve(false);
            });
            results.push({ asset, url, profile: loaded ? analyzePreviewPixels(image) : null });
          } else results.push({ asset, url: null, profile: null, error: "Preview unavailable" });
        } catch {
          results.push({ asset, url: null, profile: null, error: "Could not load preview" });
        }
        if (active) setItems([...results]);
      }
      if (active) setLoading(false);
    })();
    return () => {
      active = false;
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [projectId, assets]);

  const analyzeScene = async (asset: MediaAsset) => {
    setVisionBusy(asset.id);
    setVisionErrors((current) => ({ ...current, [asset.id]: "" }));
    const timestamp = Math.max(0, Math.min((asset.duration ?? 1) / 2, Math.max(0, (asset.duration ?? 1) - 0.1)));
    try {
      const result = await mediaApi.sceneVision(projectId, asset.id, timestamp);
      setVisionResults((current) => ({ ...current, [asset.id]: result.analysis }));
    } catch (cause) {
      setVisionErrors((current) => ({ ...current, [asset.id]: cause instanceof Error ? cause.message : "Scene analysis failed." }));
    } finally {
      setVisionBusy((current) => current === asset.id ? null : current);
    }
  };

  const previewShot = async (asset: MediaAsset, timestamp: number) => {
    setFramePreviewBusy(`${asset.id}:${timestamp}`);
    try {
      const url = await mediaApi.preview(projectId, asset, timestamp);
      if (!url) throw new Error("Source frame preview is unavailable.");
      setFramePreview((current) => {
        if (current?.url) URL.revokeObjectURL(current.url);
        return { assetId: asset.id, timestamp, url };
      });
    } catch (cause) {
      setStoryboardErrors((current) => ({ ...current, [asset.id]: cause instanceof Error ? cause.message : "Could not preview this source frame." }));
    } finally {
      setFramePreviewBusy(null);
    }
  };

  const buildStoryboard = async (asset: MediaAsset) => {
    setStoryboardBusy(asset.id);
    setStoryboardErrors((current) => ({ ...current, [asset.id]: "" }));
    const oldUrls = (storyboards[asset.id] ?? []).flatMap((scene) => scene.thumbnailUrl ? [scene.thumbnailUrl] : []);
    oldUrls.forEach((url) => {
      URL.revokeObjectURL(url);
      storyboardUrls.current = storyboardUrls.current.filter((item) => item !== url);
    });
    setStoryboards((current) => ({ ...current, [asset.id]: [] }));
    try {
      const detected = await mediaApi.detectScenes(projectId, asset.id, 50, true);
      const duration = Math.max(0.2, asset.duration ?? 0.2);
      const rawCandidates = detected.scenes.length
        ? [0, ...detected.scenes.map((scene) => scene.start)]
        : Array.from({ length: Math.min(6, Math.max(1, Math.ceil(duration / 5))) }, (_, index, all) =>
            all.length === 1 ? 0 : (index * (duration - 0.1)) / (all.length - 1));
      const candidates = rawCandidates
        .filter((time, index, all) => time >= 0 && time < duration && all.findIndex((value) => Math.abs(value - time) < 0.75) === index)
        .sort((a, b) => a - b);
      const chosen = candidates.length <= 6 ? candidates : Array.from({ length: 6 }, (_, index) => candidates[Math.round(index * (candidates.length - 1) / 5)]);
      if (!chosen.length) throw new Error("No usable scene timestamps were found.");
      const results: StoryboardScene[] = [];
      for (const timestamp of chosen) {
        const response = await mediaApi.sceneVision(projectId, asset.id, Math.min(timestamp + 0.15, Math.max(0, duration - 0.05)));
        const measuredScene = detected.scenes.reduce((best, scene) =>
          Math.abs(scene.start - timestamp) < Math.abs((best?.start ?? Number.POSITIVE_INFINITY) - timestamp) ? scene : best,
          detected.scenes[0]);
        const visualInterest = measuredScene && Math.abs(measuredScene.start - timestamp) <= 0.75
          ? measuredScene.visual_interest : undefined;
        let thumbnailUrl: string | null = null;
        try {
          thumbnailUrl = await mediaApi.preview(projectId, asset, timestamp);
          if (thumbnailUrl) storyboardUrls.current.push(thumbnailUrl);
        } catch {
          // Keep semantic scene analysis usable if a thumbnail request fails.
        }
        results.push({ timestamp, description: response.analysis.description, objects: response.analysis.objects, actions: response.analysis.actions, editing_notes: response.analysis.editing_notes, confidence: response.analysis.confidence, available: response.analysis.available, notice: response.analysis.notice, visual_interest: visualInterest, thumbnailUrl });
        setStoryboards((current) => ({ ...current, [asset.id]: [...results] }));
        if (!response.analysis.available) break;
      }
    } catch (cause) {
      setStoryboardErrors((current) => ({ ...current, [asset.id]: cause instanceof Error ? cause.message : "Could not build the scene storyboard." }));
    } finally {
      setStoryboardBusy((current) => current === asset.id ? null : current);
    }
  };

  return <section className="visual-media-inspector" aria-label="Visual media intelligence">
    <div className="visual-media-heading">
      <div><p className="eyebrow">VISUAL MEDIA INTELLIGENCE</p><h3>Media contact sheet</h3></div>
      <span>{visualAssets.length} of {assets.filter((asset) => asset.mime_type.startsWith("image/") || asset.mime_type.startsWith("video/")).length} assets</span>
    </div>
    <p className="visual-media-intro">Preview frames are sampled locally for visual statistics. For video clips, you can separately request AI scene understanding of one representative frame.</p>
    {!visualAssets.length && <p className="visual-media-empty">Import video or image assets to inspect them here.</p>}
    <div className="visual-media-grid">
      {items.map(({ asset, url, profile, error }) => <article className="visual-media-card" key={asset.id}>
        {url ? <img src={url} alt={`Preview of ${asset.filename}`} loading="lazy"/> : <div className="visual-media-placeholder">{error ?? "Preparing preview…"}</div>}
        <div className="visual-media-card-body">
          <strong title={asset.filename}>{asset.filename}</strong>
          <small>{asset.mime_type.startsWith("video/") ? "Video frame preview" : "Image preview"}</small>
          {profile ? <div className="visual-media-metrics">
            <span>Brightness <b>{profile.brightness}%</b></span>
            <span>Contrast <b>{profile.contrast}%</b></span>
            <span>Tone <b>{profile.tone}</b></span>
            <span>Colour <b>{profile.colorfulness}%</b></span>
          </div> : <small>{error ?? "Analysing preview…"}</small>}
          {asset.mime_type.startsWith("video/") && <button type="button" className="visual-ai-button"
            disabled={visionBusy === asset.id} onClick={() => void analyzeScene(asset)}>
            {visionBusy === asset.id ? "Understanding scene…" : visionResults[asset.id] ? "Re-analyse scene" : "AI scene analysis"}
          </button>}
          {asset.mime_type.startsWith("video/") && <>
            <button type="button" className="visual-ai-button" disabled={storyboardBusy === asset.id || visionBusy === asset.id}
              onClick={() => void buildStoryboard(asset)}>
              {storyboardBusy === asset.id ? "Building storyboard…" : storyboards[asset.id]?.length ? "Refresh scene storyboard" : "Build scene storyboard"}
            </button>
            {storyboardErrors[asset.id] && <small className="visual-ai-error">{storyboardErrors[asset.id]}</small>}
            {storyboards[asset.id]?.some((scene) => scene.available) && onCreateEditPlan && <button type="button" className="visual-ai-button"
              disabled={storyboardBusy === asset.id || visionBusy === asset.id}
              onClick={() => {
                const ranked = rankShots(storyboards[asset.id], { visualWeight }).filter((shot) => shot.available);
                const sceneBrief = ranked.map((shot, index) =>
                  `${index + 1}. ${shot.timestamp.toFixed(1)}s | blended review score ${shot.score}/100 (semantic ${shot.semanticScore}/100, pixel influence ${visualWeight}%) | pixel visual-interest ${typeof shot.visual_interest === "number" ? `${Math.round(shot.visual_interest * 100)}/100` : "not available"} | description: ${shot.description ?? "Not provided"} | visible: ${shot.objects.join(", ") || "not specified"} | actions: ${shot.actions.join(", ") || "not specified"} | notes: ${shot.editing_notes.join(", ") || "none"}`
                ).join("\\n");
                onCreateEditPlan(`Create an editing recommendation and a reviewable starter timeline using this analyzed footage. Use the following sampled scene evidence from asset "${asset.filename}" (asset ID: ${asset.id}). Recommend a strong opening, a coherent sequence, moments that may benefit from shortening, and suitable transitions only where justified. Explain the reasoning and any uncertainty. Prefer higher review scores as candidates, but do not treat the score as visual quality. Scene evidence:\\n${sceneBrief}\\nUse only assets in this project's media library. Keep source ranges within available durations. Return a timeline draft for approval; do not claim any edits have been applied.`);
              }}>
              Ask AI Director for edit recommendations
            </button>}
            {storyboards[asset.id]?.some((scene) => scene.available) && <div className="visual-shot-ranking">
              <strong>Shot review ranking</strong>
              <small>Adjust how much pixel-based contrast, edge and colour evidence influences the review order. This is not a measure of artistic quality.</small>
              <label className="visual-ranking-control" htmlFor={`visual-weight-${asset.id}`}>
                <span>Pixel evidence influence</span><b>{visualWeight}%</b>
              </label>
              <input id={`visual-weight-${asset.id}`} type="range" min="0" max="100" step="5" value={visualWeight}
                onChange={(event) => setVisualWeight(Number(event.target.value))} aria-describedby={`visual-weight-help-${asset.id}`} />
              <small id={`visual-weight-help-${asset.id}`}>Semantic AI detail: {100 - visualWeight}% · Pixel evidence: {visualWeight}%. Scenes without pixel scores retain their semantic-only score.</small>
              {rankShots(storyboards[asset.id], { visualWeight }).filter((shot) => shot.available).map((shot, index) => <article key={`rank-${asset.id}-${shot.timestamp}`}>
                <div><b>#{index + 1} · {shot.timestamp.toFixed(1)}s</b><span>{shot.score}/100 blended review</span></div>
                <small>Semantic detail {shot.semanticScore}/100{shot.visualScore !== null ? ` · Pixel evidence ${shot.visualScore}/100` : " · Pixel score unavailable"}</small>
                <small>{shot.reasons.join(" · ")}</small>
              </article>)}
              <small>Suggested review order only. FLEXY does not rearrange your timeline.</small>
            </div>}
            {storyboards[asset.id]?.length > 0 && <div className="visual-storyboard">
              <strong>Scene storyboard · {storyboards[asset.id].length} frames</strong>
              {storyboards[asset.id].map((scene, index) => <article key={`${asset.id}-${scene.timestamp}-${index}`}>
                {scene.thumbnailUrl ? <img className="visual-storyboard-thumbnail" src={scene.thumbnailUrl} alt={`Scene ${index + 1} frame at ${scene.timestamp.toFixed(1)} seconds`} loading="lazy" /> : <div className="visual-storyboard-thumbnail-placeholder">Frame preview unavailable</div>}
                <b>Scene {index + 1} · {scene.timestamp.toFixed(1)}s</b>
                <div className="visual-shot-actions">
                  <button type="button" onClick={() => void previewShot(asset, scene.timestamp)}
                    disabled={framePreviewBusy === `${asset.id}:${scene.timestamp}`}>
                    {framePreviewBusy === `${asset.id}:${scene.timestamp}` ? "Loading frame…" : "Preview source frame"}
                  </button>
                  {onAddShotToTimeline && scene.available && <button type="button" onClick={() => onAddShotToTimeline(asset, scene.timestamp)}>
                    Add 3s shot to timeline
                  </button>}
                </div>
                {scene.available ? <>
                  <p>{scene.description}</p>
                  {scene.objects.length > 0 && <small>Visible: {scene.objects.join(", ")}</small>}
                  {scene.actions.length > 0 && <small>Actions: {scene.actions.join(", ")}</small>}
                </> : <small>{scene.notice}</small>}
              </article>)}
            </div>}
            {framePreview?.assetId === asset.id && <div className="visual-frame-preview">
              <img src={framePreview.url} alt={`Source frame at ${framePreview.timestamp.toFixed(1)} seconds`} />
              <small>Source frame preview · {framePreview.timestamp.toFixed(1)}s</small>
            </div>}
          </>}
          {visionErrors[asset.id] && <small className="visual-ai-error">{visionErrors[asset.id]}</small>}
          {visionResults[asset.id] && <div className="visual-ai-result">
            {visionResults[asset.id].available ? <>
              <strong>Scene description</strong><p>{visionResults[asset.id].description}</p>
              {visionResults[asset.id].objects.length > 0 && <small>Visible: {visionResults[asset.id].objects.join(", ")}</small>}
              {visionResults[asset.id].actions.length > 0 && <small>Actions: {visionResults[asset.id].actions.join(", ")}</small>}
              {visionResults[asset.id].editing_notes.length > 0 && <small>Editing notes: {visionResults[asset.id].editing_notes.join(" · ")}</small>}
              {typeof visionResults[asset.id].confidence === "number" && <small>Model confidence: {(visionResults[asset.id].confidence! * 100).toFixed(0)}%</small>}
            </> : <small>{visionResults[asset.id].notice}</small>}
          </div>}
        </div>
      </article>)}
    </div>
    {loading && <small className="visual-media-loading">Inspecting media previews…</small>}
    {visualAssets.length > 12 && <small className="visual-media-loading">Showing the first 12 visual assets.</small>}
    <small className="visual-media-disclaimer">AI scene analysis is optional. Building a storyboard detects scene boundaries and sends up to six representative frames to the configured vision provider. It requires FLEXY_AI_API_KEY on the backend. Model descriptions can be wrong; verify them before editing. Images and pixel statistics remain local to the browser.</small>
  </section>;
}
