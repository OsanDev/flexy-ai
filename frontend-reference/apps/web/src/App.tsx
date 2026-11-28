import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ExportPanel } from "./components/ExportPanel";
import { TimelineComposer } from "./components/TimelineComposer";
import { AssetLibrary } from "./components/AssetLibrary";
import { ProjectDashboard } from "./components/ProjectDashboard";
import type { MediaAsset } from "./lib/mediaApi";
import { projectApi } from "./lib/projectApi";
import type { TimelineDocument } from "./lib/timelineGraph";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const DEFAULT_GRAPH = {
  clips: [],
  audio_clips: [],
  captions: [],
  export_preset: "1080p",
};

function cookieValue(name: string): string | null {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

// Persist a recovery copy immediately when the editor emits a document change.
// The debounced cloud autosave remains authoritative, but this closes the small
// window between a React render/effect and a user closing or refreshing the tab.
function recoveryStorageKey(accountId: string, projectId: string): string {
  return `flexy:recovery:${accountId}:${projectId}`;
}

function writeLocalRecoverySnapshot(accountId: string, projectId: string, document: TimelineDocument): boolean {
  const id = projectId.trim();
  if (!accountId || !id || typeof window === "undefined") return false;
  try {
    localStorage.setItem(recoveryStorageKey(accountId, id), JSON.stringify({ document, updatedAt: Date.now() }));
    return true;
  } catch {
    // Storage can be unavailable or full. Cloud autosave still runs independently.
    return false;
  }
}

async function authRequest(path: string, email: string, password: string) {
  const response = await fetch(`${API_BASE}/api/auth/${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail ?? `Authentication failed (${response.status})`);
  return payload;
}

export default function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [authUnavailable, setAuthUnavailable] = useState(false);
  const [authRetry, setAuthRetry] = useState(0);
  const [account, setAccount] = useState("");
  const [accountId, setAccountId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [graphText, setGraphText] = useState(JSON.stringify(DEFAULT_GRAPH, null, 2));
  const [timelineGraph, setTimelineGraph] = useState<Record<string, unknown>>(DEFAULT_GRAPH);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const handleAssetsChange = useCallback((items: MediaAsset[]) => setAssets(items), []);
  const [timelineErrors, setTimelineErrors] = useState<string[]>([]);
  const [projectLoaded, setProjectLoaded] = useState(false);
  const [loadedProjectId, setLoadedProjectId] = useState("");
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectRevision, setProjectRevision] = useState(0);
  const [projectName, setProjectName] = useState("Untitled project");
  const [projectDocument, setProjectDocument] = useState<TimelineDocument | undefined>(undefined);
  const [projectPayload, setProjectPayload] = useState<Record<string, unknown>>({});
  const [projectDirty, setProjectDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState("Not connected");
  const [saveError, setSaveError] = useState("");
  const [savePulse, setSavePulse] = useState(0);
  const [recoveryAvailable, setRecoveryAvailable] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [renamingProject, setRenamingProject] = useState(false);
  const [timelineMount, setTimelineMount] = useState(0);
  const projectDocumentRef = useRef<TimelineDocument | undefined>(undefined);
  const projectSessionRef = useRef(0);
  const pendingProjectSavesRef = useRef<Map<string, Promise<unknown>>>(new Map());
  const savingProjectsRef = useRef<Set<string>>(new Set());
  const [graphMode, setGraphMode] = useState<"timeline" | "json">("timeline");
  const [error, setError] = useState("");

  // Restore an existing HttpOnly-cookie session after a page refresh.
  // The session token never needs to be read by JavaScript; /me validates it server-side.
  useEffect(() => {
    let cancelled = false;
    setAuthChecking(true);
    setAuthUnavailable(false);
    fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })
      .then(async (response) => {
        if (response.status === 401) return null;
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail ?? `Session check failed (${response.status}).`);
        return payload as { id: string; email: string };
      })
      .then((session) => {
        if (cancelled) return;
        if (session?.email) {
          setAccount(session.email);
          setAccountId(session.id);
          setSignedIn(true);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setAuthUnavailable(true);
          setError(cause instanceof Error ? cause.message : "Could not reach the session service.");
        }
      })
      .finally(() => { if (!cancelled) setAuthChecking(false); });
    return () => { cancelled = true; };
  }, [authRetry]);

  const signOut = async () => {
    setError("");
    try {
      const csrf = cookieValue("flexy_csrf");
      if (!csrf) throw new Error("Session security token is missing. Refresh and sign in again.");
      const response = await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!response.ok) throw new Error(`Sign out failed (${response.status}).`);
      setSignedIn(false);
      setAccount("");
      setAccountId("");
      setProjectLoaded(false);
      setLoadedProjectId("");
      setProjectDocument(undefined);
      projectDocumentRef.current = undefined;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign out.");
    }
  };

  const signIn = async (event: FormEvent, mode: "login" | "register") => {
    event.preventDefault();
    setError("");
    try {
      const result = await authRequest(mode, email, password);
      setAccount(result.email);
      setAccountId(result.id);
      setSignedIn(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not authenticate.");
    }
  };

  useEffect(() => {
    let cancelled = false;
    const sessionId = ++projectSessionRef.current;
    const id = projectId.trim();
    setProjectLoaded(false);
    setLoadedProjectId("");
    setProjectDocument(undefined);
    projectDocumentRef.current = undefined;
    setProjectPayload({});
    setProjectDirty(false);
    setSaveError("");
    setRecoveryAvailable(false);
    if (!signedIn || !id) { setSaveStatus("Not connected"); return; }
    setProjectLoading(true);
    setSaveStatus("Loading project…");
    void (async () => {
      try {
        // If this project was reopened while an earlier save is still in flight,
        // wait for that write before reading its revision and timeline document.
        const pendingSave = pendingProjectSavesRef.current.get(id);
        if (pendingSave) await pendingSave.catch(() => undefined);
        if (cancelled || projectSessionRef.current !== sessionId) return;
        const cloud = await projectApi.load(id);
        if (cancelled || projectSessionRef.current !== sessionId) return;
        setProjectRevision(cloud.revision);
        setProjectName(cloud.name);
        setProjectPayload(cloud.project);
        const saved = cloud.project.timeline_document as TimelineDocument | undefined;
        const restored = saved && Array.isArray(saved.videoClips) ? saved : undefined;
        setProjectDocument(restored);
        projectDocumentRef.current = restored;
        setProjectTitleDraft(cloud.name);
        try {
          const local = localStorage.getItem(recoveryStorageKey(accountId, id));
          if (local && restored) {
            const parsed = JSON.parse(local) as { document?: TimelineDocument; updatedAt?: number };
            if (parsed.document && Array.isArray(parsed.document.videoClips)
                && JSON.stringify(parsed.document) !== JSON.stringify(restored)) {
              setRecoveryAvailable(true);
            }
          }
        } catch { /* Ignore an invalid local recovery snapshot. */ }
        setProjectLoaded(true);
        setLoadedProjectId(id);
        setSaveStatus("All changes saved");
      } catch (cause) {
        if (cancelled || projectSessionRef.current !== sessionId) return;
        setSaveStatus("Project unavailable");
        setSaveError(cause instanceof Error ? cause.message : "Could not load project.");
      } finally {
        if (!cancelled && projectSessionRef.current === sessionId) setProjectLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, signedIn, accountId]);

  useEffect(() => {
    if (!projectLoaded || loadedProjectId !== projectId.trim() || !projectId.trim() || !projectDocument || !projectDirty) return;
    try {
      localStorage.setItem(recoveryStorageKey(accountId, projectId.trim()), JSON.stringify({
        document: projectDocument, updatedAt: Date.now()
      }));
    } catch { /* Cloud autosave remains the primary persistence path. */ }
  }, [projectLoaded, loadedProjectId, projectId, projectDocument, projectDirty, accountId]);

  const restoreLocalRecovery = () => {
    try {
      const raw = localStorage.getItem(recoveryStorageKey(accountId, projectId.trim()));
      const parsed = raw ? JSON.parse(raw) as {document?: TimelineDocument} : null;
      if (!parsed?.document) return;
      projectDocumentRef.current = parsed.document;
      setProjectDocument(parsed.document);
      setProjectDirty(true);
      setTimelineMount((value) => value + 1);
      setRecoveryAvailable(false);
      setSaveStatus("Recovered local draft");
    } catch {
      setRecoveryAvailable(false);
      setSaveError("The local recovery draft could not be read.");
    }
  };

  const discardLocalRecovery = () => {
    try { localStorage.removeItem(recoveryStorageKey(accountId, projectId.trim())); } catch {}
    setRecoveryAvailable(false);
  };

  const renameCurrentProject = async () => {
    const next = projectTitleDraft.trim();
    if (!next || !projectId.trim() || next === projectName) return;
    setRenamingProject(true); setSaveError("");
    try {
      await projectApi.rename(projectId.trim(), next);
      setProjectName(next);
      setSaveStatus("Project name updated");
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : "Project rename failed.");
    } finally { setRenamingProject(false); }
  };

  // Warn before navigating away while cloud persistence is still pending.
  // The local recovery snapshot is best-effort; it is not a substitute for a successful cloud save.
  useEffect(() => {
    if (!projectLoaded || loadedProjectId !== projectId.trim() || !projectDirty) return;
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeave);
    return () => window.removeEventListener("beforeunload", warnBeforeLeave);
  }, [projectLoaded, loadedProjectId, projectId, projectDirty]);

  useEffect(() => {
    const targetProjectId = projectId.trim();
    if (!projectLoaded || loadedProjectId !== targetProjectId || !projectDirty || !targetProjectId || !projectDocument || savingProjectsRef.current.has(targetProjectId)) return;
    const sessionId = projectSessionRef.current;
    setSaveStatus("Unsaved changes");
    const timer = window.setTimeout(() => {
      if (projectSessionRef.current !== sessionId || loadedProjectId !== targetProjectId) return;
      setSaveStatus("Saving…");
      const payload = { ...projectPayload, timeline_document: projectDocument };
      savingProjectsRef.current.add(targetProjectId);
      const saveRequest = projectApi.save(targetProjectId, projectName, payload, projectRevision);
      pendingProjectSavesRef.current.set(targetProjectId, saveRequest);
      saveRequest.then((result) => {
        if (projectSessionRef.current !== sessionId || loadedProjectId !== targetProjectId || projectId.trim() !== targetProjectId) return;
        setProjectRevision(result.revision);
        setProjectPayload(payload);
        if (projectDocumentRef.current === projectDocument) {
          setProjectDirty(false);
          setSaveError("");
          setSaveStatus("All changes saved");
          try { localStorage.removeItem(recoveryStorageKey(accountId, targetProjectId)); } catch {}
        }
      }).catch((cause) => {
        if (projectSessionRef.current !== sessionId || loadedProjectId !== targetProjectId || projectId.trim() !== targetProjectId) return;
        setSaveStatus("Save needs attention");
        setSaveError(cause instanceof Error ? cause.message : "Autosave failed.");
      }).finally(() => {
        if (pendingProjectSavesRef.current.get(targetProjectId) === saveRequest) {
          pendingProjectSavesRef.current.delete(targetProjectId);
        }
        savingProjectsRef.current.delete(targetProjectId);
        if (projectSessionRef.current === sessionId && loadedProjectId === targetProjectId
            && projectId.trim() === targetProjectId && projectDocumentRef.current !== projectDocument) {
          setSavePulse((value) => value + 1);
        }
      });
    }, 1200);
    return () => { window.clearTimeout(timer); };
  }, [projectLoaded, loadedProjectId, projectDirty, projectId, projectDocument, projectPayload, projectName, projectRevision, savePulse]);

  let graph: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(graphText);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      graph = parsed as Record<string, unknown>;
    }
  } catch { /* display invalid JSON state below */ }

  // Historical integration note: v4.2.34 previewing playback remains part of this editor.
  // Integration contract: Add media IDs that already belong to this project.
  // The TimelineComposer receives assets and onGraphChange from the shared workspace.
  // <TimelineComposer assets={assets} onGraphChange={handleTimelineGraphChange} />
  return (
    <main className="lab-shell">
      {/* Historical contract: PROJECT DASHBOARD / v4.2.37 was the first dashboard milestone. */}
      <nav className="topbar">
        <a className="brand" href="#"><span className="brand-mark">F</span> FLEXY <b>AI</b></a>
        <span className="lab-label">VIDEO EDITOR / v4.6.0</span>
      </nav>

      <section className="hero">
        <p className="eyebrow">VIDEO WORKFLOW TEST ENVIRONMENT</p>
        <h1>From timeline<br/><span>to final cut.</span></h1>
        <p className="hero-copy">A browser integration lab for importing media, editing a timeline, previewing playback and testing protected exports.</p>
      </section>

      {authChecking ? (
        <section className="panel auth-panel" role="status"><p className="eyebrow">SECURE SESSION</p><h2>Restoring your workspace…</h2><p className="hint">Checking your existing sign-in securely.</p></section>
      ) : authUnavailable ? (
        <section className="panel auth-panel" aria-labelledby="session-unavailable-title">
          <p className="eyebrow">SECURE SESSION</p><h2 id="session-unavailable-title">Can’t reach your workspace</h2>
          <p className="hint">FLEXY could not contact the session service. Your sign-in has not been treated as expired. Check your connection and API address, then retry.</p>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary" type="button" onClick={() => { setError(""); setAuthRetry((value) => value + 1); }}>Retry connection</button>
        </section>
      ) : !signedIn ? (
        <section className="panel auth-panel">
          <div className="panel-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h2>Sign in to continue</h2></div><span className="status-dot">● SECURE SESSION</span></div>
          <form onSubmit={(event) => void signIn(event, "login")}>
            <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>
            <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} autoComplete="current-password" /></label>
            <button className="primary" type="submit">Sign in <span>↗</span></button>
            <button className="secondary" type="button" onClick={(event) => void signIn(event as unknown as FormEvent, "register")}>Create account</button>
          </form>
          {error && <p className="error" role="alert">{error}</p>}
          <p className="hint">Use the backend API configured in <code>VITE_API_BASE_URL</code>. The API must allow this page's origin.</p>
        </section>
      ) : (
        <section className="workspace">
          <div className="session-row">
            <div><p className="eyebrow">SIGNED IN AS</p><strong>{account}</strong></div>
            <button className="secondary" onClick={() => void signOut()}>Sign out</button>
          </div>
          <ProjectDashboard onOpen={(id) => { setProjectId(id); setGraphMode("timeline"); }} />
          {projectId.trim() && <button className="secondary dashboard-back" onClick={() => {
            setProjectId(""); setProjectLoaded(false); setProjectDocument(undefined);
            projectDocumentRef.current = undefined; setAssets([]);
          }}>← Back to projects</button>}
          {projectId.trim() && <AssetLibrary projectId={projectId.trim()} onAssetsChange={handleAssetsChange} />}
          <section className="panel project-panel">
            <p className="eyebrow">PROJECT SETTINGS</p>
            <h2>{projectLoaded ? "Project workspace" : "Connect an existing project"}</h2>
            {projectLoaded && <div className="project-title-settings">
              <label>Project name<input value={projectTitleDraft} onChange={(e) => setProjectTitleDraft(e.target.value)} maxLength={120} /></label>
              <button className="secondary" onClick={() => void renameCurrentProject()} disabled={renamingProject || !projectTitleDraft.trim() || projectTitleDraft.trim() === projectName}>{renamingProject ? "Saving…" : "Save name"}</button>
            </div>}
            {recoveryAvailable && <div className="recovery-banner" role="status">
              <div><strong>Unsaved local draft found</strong><p>A newer local editing snapshot is available for this project.</p></div>
              <button className="primary" onClick={restoreLocalRecovery}>Restore draft</button>
              <button className="secondary" onClick={discardLocalRecovery}>Discard</button>
            </div>}
            <label>Project ID<input value={projectId} onChange={(e) => setProjectId(e.target.value)} placeholder="Paste an existing project ID" /></label>
            <p className="hint">Connect an existing project you own. Its timeline loads from the cloud and autosaves after edits.</p>
            <div className="cloud-save-status" aria-live="polite"><strong>{saveStatus}</strong>{projectLoaded && <span>Revision {projectRevision}</span>}</div>
            {saveError && <div className="save-retry-row" role="alert"><p className="error">{saveError}</p><button className="secondary" type="button" onClick={() => { setSaveError(""); setSaveStatus("Retrying save…"); setSavePulse((value) => value + 1); }} disabled={!projectDirty || !projectLoaded}>Retry save</button></div>}
            <div className="timeline-tabs">
              <button className={graphMode === "timeline" ? "active" : ""} onClick={() => setGraphMode("timeline")}>Timeline composer</button>
              <button className={graphMode === "json" ? "active" : ""} onClick={() => setGraphMode("json")}>Advanced JSON</button>
            </div>
            {graphMode === "timeline" ? (
              projectLoading ? <p className="hint">Loading your cloud project…</p> :
              projectLoaded ? <TimelineComposer key={`${projectId.trim()}:${timelineMount}`} assets={assets} projectId={projectId.trim()} projectContext={projectPayload} initialDocument={projectDocument}
                onDocumentChange={(next) => {
                  const targetProjectId = projectId.trim();
                  if (loadedProjectId === targetProjectId && targetProjectId) {
                    writeLocalRecoverySnapshot(accountId, targetProjectId, next);
                  }
                  projectDocumentRef.current = next;
                  setProjectDocument(next);
                  setProjectDirty(true);
                }}
                onGraphChange={(next, issues) => { setTimelineGraph(next); setTimelineErrors(issues); }} /> :
              <p className="hint">Connect a valid project ID to load its saved timeline before editing.</p>
            ) : (
              <label>Render graph (JSON)<textarea spellCheck={false} value={graphText} onChange={(e) => setGraphText(e.target.value)} rows={10} /></label>
            )}
            {graphMode === "json" && !graph && <p className="error">The render graph must be valid JSON.</p>}
          </section>
          {projectId.trim() && (graphMode === "timeline" || graph) && (
            <ExportPanel projectId={projectId.trim()} graph={graphMode === "timeline" ? timelineGraph : graph!} />
          )}
          {graphMode === "timeline" && timelineErrors.length > 0 && (
            <p className="hint">Timeline needs attention: {timelineErrors.join(" ")}</p>
          )}
        </section>
      )}
      <footer>FLEXY AI · DEVELOPMENT HARNESS · NOT A PRODUCTION EDITOR</footer>
    </main>
  );
}
