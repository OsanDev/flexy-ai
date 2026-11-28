import { useCallback, useEffect, useMemo, useState } from "react";
import { renderApi, RenderApiError, type RenderJob, type RenderPreflight } from "../lib/renderApi";

type ExportPanelProps = {
  projectId: string;
  graph: Record<string, unknown>;
  onClose?: () => void;
};

const ACTIVE = new Set(["queued", "processing", "cancelling"]);
const TERMINAL = new Set(["completed", "failed", "cancelled", "interrupted"]);

function messageOf(error: unknown): string {
  if (error instanceof RenderApiError) return error.message;
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export function ExportPanel({ projectId, graph, onClose }: ExportPanelProps) {
  const [preflight, setPreflight] = useState<RenderPreflight | null>(null);
  const [job, setJob] = useState<RenderJob | null>(null);
  const [history, setHistory] = useState<RenderJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportPreset, setExportPreset] = useState("1080p");
  const [frameRate, setFrameRate] = useState("30");
  const exportGraph = useMemo(() => ({
    ...graph,
    export_preset: exportPreset,
    frame_rate: Number(frameRate),
  }), [graph, exportPreset, frameRate]);

  const warnings = useMemo(() => {
    const value = preflight?.warnings;
    return Array.isArray(value) ? value as Array<{ code?: string; message?: string }> : [];
  }, [preflight]);

  const refreshHistory = useCallback(async () => {
    try {
      const result = await renderApi.list(projectId);
      setHistory(result.renders);
    } catch (cause) {
      setError(messageOf(cause));
    }
  }, [projectId]);

  useEffect(() => {
    let active = true;
    setBusy(true);
    setError(null);
    renderApi.preflight(projectId, exportGraph)
      .then((report) => { if (active) setPreflight(report); })
      .catch((cause) => { if (active) setError(messageOf(cause)); })
      .finally(() => { if (active) setBusy(false); });
    void refreshHistory();
    return () => { active = false; };
  }, [projectId, exportGraph, refreshHistory]);

  useEffect(() => {
    if (!job || !ACTIVE.has(job.status)) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const latest = await renderApi.status(job.id);
        if (stopped) return;
        setJob(latest);
        if (TERMINAL.has(latest.status)) {
          await refreshHistory();
          return;
        }
      } catch (cause) {
        if (!stopped) setError(messageOf(cause));
      }
      if (!stopped) timer = setTimeout(poll, 1500);
    };

    timer = setTimeout(poll, 800);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [job?.id, job?.status, refreshHistory]);

  const startExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const report = await renderApi.preflight(projectId, exportGraph);
      setPreflight(report);
      if (report.ready !== true) {
        throw new Error(String(report.message ?? "Export is not ready. Resolve the preflight issues before rendering."));
      }
      const result = await renderApi.create(projectId, exportGraph);
      setJob({
        id: result.id,
        project_id: projectId,
        status: result.status,
        progress: 0,
      });
      await refreshHistory();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(false);
    }
  };

  const cancelExport = async () => {
    if (!job) return;
    setError(null);
    try {
      const result = await renderApi.cancel(job.id);
      setJob((current) => current ? { ...current, status: result.status } : current);
    } catch (cause) {
      setError(messageOf(cause));
    }
  };

  const downloadExport = async (jobId: string) => {
    setError(null);
    try {
      const blob = await renderApi.download(jobId);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = "flexy-export.mp4";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      // Browsers may start consuming the blob URL after click dispatch. Keep it
      // alive briefly so large exports do not become intermittent empty downloads.
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (cause) {
      setError(messageOf(cause));
    }
  };

  const removeHistoryItem = async (jobId: string) => {
    setError(null);
    try {
      await renderApi.remove(jobId);
      setHistory((items) => items.filter((item) => item.id !== jobId));
      if (job?.id === jobId) setJob(null);
    } catch (cause) {
      setError(messageOf(cause));
    }
  };

  return (
    <section aria-labelledby="flexy-export-title" className="flexy-export-panel">
      <header className="flexy-export-panel__header">
        <div>
          <p className="flexy-export-panel__eyebrow">FLEXY AI / DELIVERY</p>
          <h2 id="flexy-export-title">Export video</h2>
          <p>Check your timeline, then render a downloadable video.</p>
        </div>
        {onClose && <button type="button" onClick={onClose} aria-label="Close export panel">×</button>}
      </header>

      {error && <p role="alert" className="flexy-export-panel__error">{error}</p>}

      <div className="flexy-export-panel__settings" aria-label="Export settings">
        <label>
          Resolution
          <select value={exportPreset} onChange={(event) => {
            const nextPreset = event.target.value;
            setExportPreset(nextPreset);
            if (nextPreset === "8k" && frameRate === "120") setFrameRate("60");
          }}>
            <option value="1080p">1080p Full HD</option>
            <option value="2k">2K QHD (2560 × 1440)</option>
            <option value="4k">4K UHD</option>
            <option value="8k">8K UHD (7680 × 4320)</option>
          </select>
        </label>
        <label>
          Frame rate
          <select value={frameRate} onChange={(event) => setFrameRate(event.target.value)}>
            <option value="24">24 FPS · Cinematic</option>
            <option value="30">30 FPS · Standard</option>
            <option value="60">60 FPS · Smooth</option>
            <option value="120" disabled={exportPreset === "8k"}>120 FPS · High frame rate (up to 4K)</option>
          </select>
        </label>
        {(exportPreset === "8k" || frameRate === "120") && (
          <p className="flexy-export-panel__note">
            {frameRate === "120" ? "120 FPS export is available for 1080p, 2K and 4K. Use high-frame-rate source footage for the best result." : "8K export is resource-intensive. Rendering speed depends on server hardware, FFmpeg build and source media."}
            {" "}Rendering performance depends on server hardware and source media.
          </p>
        )}
      </div>

      <div className="flexy-export-panel__preflight" aria-live="polite">
        <h3>Export check</h3>
        {busy && !preflight ? <p>Checking your project…</p> : null}
        {preflight && (
          <>
            <p>{String(preflight.message ?? "Preflight complete.")}</p>
            <dl>
              <div><dt>Resolution</dt><dd>{String(preflight.resolution ?? "Not specified")}</dd></div>
              <div><dt>Frame rate</dt><dd>{String(preflight.frame_rate ?? "Not specified")}</dd></div>
              <div><dt>Duration</dt><dd>{typeof preflight.video_duration === "number" ? `${preflight.video_duration.toFixed(1)} sec` : "Not specified"}</dd></div>
            </dl>
            {warnings.length > 0 && (
              <ul>
                {warnings.map((warning, index) => <li key={`${warning.code ?? "warning"}-${index}`}>{warning.message ?? "Review this export warning."}</li>)}
              </ul>
            )}
          </>
        )}
      </div>

      <div className="flexy-export-panel__actions">
        <button type="button" onClick={startExport} disabled={busy || preflight?.ready !== true}>
          {busy ? "Working…" : "Start export"}
        </button>
        {job && ACTIVE.has(job.status) && (
          <button type="button" onClick={cancelExport}>Cancel export</button>
        )}
      </div>

      {job && (
        <div className="flexy-export-panel__job" aria-live="polite">
          <div className="flexy-export-panel__job-heading">
            <strong>Current export</strong>
            <span>{job.status}</span>
          </div>
          <progress max={100} value={job.progress ?? 0} />
          <p>{Math.max(0, Math.min(100, job.progress ?? 0))}% complete</p>
          {job.error && <p role="alert">{job.error}</p>}
          {job.status === "completed" && (
            <button type="button" onClick={() => void downloadExport(job.id)}>Download MP4</button>
          )}
          {(job.status === "failed" || job.status === "cancelled" || job.status === "interrupted") && (
            <button type="button" onClick={() => void startExport()} disabled={busy || !preflight}>
              Retry export with current settings
            </button>
          )}
        </div>
      )}

      <div className="flexy-export-panel__history">
        <h3>Recent exports</h3>
        {history.length === 0 && <p>No exports yet.</p>}
        <ul>
          {history.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.status}</strong>
                <span>{item.progress ?? 0}%</span>
              </div>
              {item.status === "completed" && (
                <button type="button" onClick={() => void downloadExport(item.id)}>Download</button>
              )}
              {(item.status === "failed" || item.status === "cancelled" || item.status === "interrupted") && (
                <button type="button" onClick={() => void startExport()} disabled={busy || !preflight}>
                  Retry current timeline
                </button>
              )}
              {TERMINAL.has(item.status) && (
                <button type="button" onClick={() => void removeHistoryItem(item.id)}>Remove</button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
