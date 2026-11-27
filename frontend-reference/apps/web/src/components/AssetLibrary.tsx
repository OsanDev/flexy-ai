import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { mediaApi, type MediaAsset, type WaveformData } from "../lib/mediaApi";
import { validateMediaFiles } from "../lib/mediaValidation";

type Props = { projectId: string; onAssetsChange: (assets: MediaAsset[]) => void };
const size = (n: number) => n < 1048576
  ? `${(n / 1024).toFixed(1)} KB`
  : `${(n / 1048576).toFixed(1)} MB`;

function Waveform({ data }: { data: WaveformData }) {
  const values = data.points ?? data.samples ?? data.waveform ?? [];
  return values.length
    ? <div className="asset-waveform">{values.slice(0, 64).map((value, index) => (
      <i key={index} style={{ height: `${Math.max(8, Math.min(100, Math.abs(Number(value)) * 100))}%` }} />
    ))}</div>
    : <small>Waveform unavailable</small>;
}

export function AssetLibrary({ projectId, onAssetsChange }: Props) {
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [waves, setWaves] = useState<Record<string, WaveformData>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploadProgress, setUploadProgress] = useState({ completed: 0, total: 0 });
  const [retryFiles, setRetryFiles] = useState<File[]>([]);
  const uploadController = useRef<AbortController | null>(null);
  const requestSequence = useRef(0);
  const previewUrls = useRef<string[]>([]);

  const load = useCallback(async () => {
    const sequence = ++requestSequence.current;
    try {
      const result = await mediaApi.list(projectId);
      if (sequence !== requestSequence.current) return;
      setAssets(result.media);
      onAssetsChange(result.media);

      const previewPairs = await Promise.all(result.media.map(async (asset) => {
        try {
          const url = await mediaApi.preview(projectId, asset);
          return url ? [asset.id, url] as const : null;
        } catch {
          return null;
        }
      }));
      const nextUrls = previewPairs.flatMap((pair) => pair ? [pair[1]] : []);
      if (sequence !== requestSequence.current) {
        nextUrls.forEach(URL.revokeObjectURL);
        return;
      }
      previewUrls.current.forEach(URL.revokeObjectURL);
      previewUrls.current = nextUrls;
      setPreviews(Object.fromEntries(previewPairs.filter((pair): pair is readonly [string, string] => pair !== null)));

      const wavePairs = await Promise.all(result.media
        .filter((asset) => asset.mime_type.startsWith("audio/") || asset.mime_type.startsWith("video/"))
        .map(async (asset) => {
          try { return [asset.id, await mediaApi.waveform(projectId, asset.id)] as const; }
          catch { return null; }
        }));
      if (sequence === requestSequence.current) {
        setWaves(Object.fromEntries(wavePairs.filter((pair): pair is readonly [string, WaveformData] => pair !== null)));
        setError("");
      }
    } catch (cause) {
      if (sequence === requestSequence.current) {
        setError(cause instanceof Error ? cause.message : "Could not load media.");
      }
    }
  }, [projectId, onAssetsChange]);

  useEffect(() => {
    void load();
    return () => {
      requestSequence.current += 1;
      previewUrls.current.forEach(URL.revokeObjectURL);
      previewUrls.current = [];
    };
  }, [load]);

  const runUpload = async (files: File[]) => {
    if (!files.length || busy) return;
    const validation = validateMediaFiles(files);
    const rejectedSummary = validation.rejected.map(({ file, reason }) =>
      `${file.name}: ${reason === "too_large" ? "exceeds the 1 GB per-file limit" : "unsupported media format"}`,
    );
    if (!validation.accepted.length) {
      setError(rejectedSummary.join("; ") || "No supported media files were selected.");
      return;
    }

    const acceptedFiles = validation.accepted as File[];
    const controller = new AbortController();
    uploadController.current = controller;
    setBusy(true);
    setError(rejectedSummary.length ? `Skipped ${rejectedSummary.join("; ")}` : "");
    setRetryFiles([]);
    setUploadProgress({ completed: 0, total: acceptedFiles.length });
    let uploaded = 0;
    const failed: File[] = [];
    try {
      for (let index = 0; index < acceptedFiles.length; index += 1) {
        const file = acceptedFiles[index];
        if (controller.signal.aborted) { failed.push(...acceptedFiles.slice(index)); break; }
        setMessage(`Uploading ${file.name} (${uploaded + 1} of ${acceptedFiles.length})…`);
        try {
          await mediaApi.upload(projectId, file, controller.signal);
          uploaded += 1;
          setUploadProgress({ completed: uploaded, total: acceptedFiles.length });
        } catch (cause) {
          if (controller.signal.aborted) { failed.push(...acceptedFiles.slice(index)); break; }
          failed.push(file);
          setError(`${file.name}: ${cause instanceof Error ? cause.message : "Upload failed."}`);
        }
      }
      if (uploaded > 0) {
        setMessage(controller.signal.aborted
          ? `Upload cancelled. ${uploaded} file${uploaded === 1 ? "" : "s"} imported successfully.`
          : `Imported ${uploaded} of ${acceptedFiles.length} files.`);
        await load();
      } else if (controller.signal.aborted) {
        setMessage("Upload cancelled. No files were imported.");
      }
      setRetryFiles(failed);
      if (failed.length) setError(`${failed.length} file${failed.length === 1 ? "" : "s"} need another attempt.`);
      else if (validation.rejected.length) setError(rejectedSummary.join("; "));
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
      setBusy(false);
    }
  };

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const files = Array.from(input.files ?? []);
    input.value = "";
    await runUpload(files);
  };

  const cancelUpload = () => uploadController.current?.abort();


  return <section className="panel asset-library">
    <div className="panel-heading">
      <div><p className="eyebrow">PROJECT MEDIA</p><h2>Asset library</h2></div>
      <label className="upload-button">
        {busy ? `Uploading ${uploadProgress.completed}/${uploadProgress.total}…` : "＋ Import media"}
        <input type="file" accept="video/*,audio/*,image/*" multiple disabled={busy} onChange={(event) => void upload(event)} />
      </label>
    </div>
    <p className="hint">Import video, audio and image files into this project. Development limit: 1 GB per file.</p>
    {message && <p role="status" className="asset-progress">{message}</p>}
    {busy && <div className="asset-upload-actions"><progress max={uploadProgress.total || 1} value={uploadProgress.completed} aria-label="Files uploaded" /><button className="secondary" type="button" onClick={cancelUpload}>Cancel upload</button></div>}
    {!busy && retryFiles.length > 0 && <button className="secondary" type="button" onClick={() => void runUpload(retryFiles)}>Retry {retryFiles.length} failed file{retryFiles.length === 1 ? "" : "s"}</button>}
    {error && <p role="alert" className="error">{error}</p>}
    {!assets.length ? <div className="asset-empty">No media imported yet.</div> : (
      <div className="asset-grid">{assets.map((asset) => (
        <article className="asset-card" key={asset.id}>
          <div className="asset-preview">{previews[asset.id]
            ? <img src={previews[asset.id]} alt={`Preview of ${asset.filename}`} />
            : <span>{asset.mime_type.startsWith("audio/") ? "♫" : asset.mime_type.startsWith("video/") ? "▶" : "▧"}</span>}
          </div>
          <div className="asset-details">
            <strong title={asset.filename}>{asset.filename}</strong>
            <small>{size(asset.size_bytes)} · {asset.duration ? `${asset.duration.toFixed(1)}s` : asset.mime_type.split("/")[0]}</small>
            {waves[asset.id] && <Waveform data={waves[asset.id]} />}
            <code>{asset.id}</code>
          </div>
        </article>
      ))}</div>
    )}
  </section>;
}
