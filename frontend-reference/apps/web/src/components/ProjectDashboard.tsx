import { FormEvent, useCallback, useEffect, useState } from "react";
import { projectApi, type ProjectSummary } from "../lib/projectApi";
import { mediaApi } from "../lib/mediaApi";

type Props = { onOpen: (projectId: string) => void };
type SortMode = "updated_desc" | "created_desc" | "created_asc" | "name_asc" | "name_desc";

export function ProjectDashboard({ onOpen }: Props) {
  const [projects,setProjects] = useState<ProjectSummary[]>([]);
  const [folders,setFolders] = useState<string[]>([]);
  const [search,setSearch] = useState("");
  const [folder,setFolder] = useState("");
  const [favoritesOnly,setFavoritesOnly] = useState(false);
  const [sort,setSort] = useState<SortMode>("updated_desc");
  const [covers,setCovers] = useState<Record<string,string>>({});
  const [name,setName] = useState("");
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState("");
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await projectApi.list({search, folder, favoritesOnly, sort});
      setProjects(result.projects); setFolders(result.folders);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load projects.");
    } finally { setLoading(false); }
  },[search,folder,favoritesOnly,sort]);

  useEffect(() => { void load(); },[load]);

  useEffect(() => {
    let cancelled = false;
    const created: string[] = [];
    const hydrate = async () => {
      const pairs = await Promise.all(projects.slice(0,24).map(async (project) => {
        try {
          const {media} = await mediaApi.list(project.id);
          const candidate = media.find(item => item.mime_type.startsWith("image/") || item.mime_type.startsWith("video/"));
          if (!candidate) return [project.id, ""] as const;
          const url = await mediaApi.preview(project.id,candidate);
          if (url) created.push(url);
          return [project.id,url ?? ""] as const;
        } catch { return [project.id,""] as const; }
      }));
      if (cancelled) created.forEach(url => URL.revokeObjectURL(url));
      else setCovers(Object.fromEntries(pairs.filter(([,url]) => !!url)));
    };
    setCovers({});
    void hydrate();
    return () => { cancelled = true; created.forEach(url => URL.revokeObjectURL(url)); };
  },[projects]);

  const create = async (event:FormEvent) => {
    event.preventDefault(); if (!name.trim()) return;
    setBusy("create"); setError("");
    try { const result=await projectApi.create(name.trim()); onOpen(result.id); }
    catch(cause) { setError(cause instanceof Error ? cause.message : "Project creation failed."); }
    finally { setBusy(""); }
  };
  const rename = async (project:ProjectSummary) => {
    const next=window.prompt("New project name",project.name);
    if (!next?.trim() || next.trim()===project.name) return;
    setBusy(project.id); setError("");
    try { await projectApi.rename(project.id,next.trim()); setNotice("Project renamed."); await load(); }
    catch(cause) { setError(cause instanceof Error ? cause.message : "Rename failed."); }
    finally { setBusy(""); }
  };
  const organize = async (project:ProjectSummary) => {
    const next=window.prompt("Folder name (leave empty for Unfiled)",project.folder_name ?? "");
    if (next===null) return;
    setBusy(project.id); setError("");
    try { await projectApi.organize(project.id,{folder_name:next.trim()}); setNotice("Folder updated."); await load(); }
    catch(cause) { setError(cause instanceof Error ? cause.message : "Folder update failed."); }
    finally { setBusy(""); }
  };
  const toggleFavorite = async (project:ProjectSummary) => {
    setBusy(project.id); setError("");
    try {
      await projectApi.organize(project.id,{is_favorite:!Boolean(project.is_favorite)});
      setNotice(project.is_favorite ? "Removed from favorites." : "Added to favorites.");
      await load();
    } catch(cause) { setError(cause instanceof Error ? cause.message : "Favorite update failed."); }
    finally { setBusy(""); }
  };
  const duplicate = async (project:ProjectSummary) => {
    setBusy(project.id); setError("");
    try { const copy=await projectApi.duplicate(project.id); setNotice("Project duplicated."); await load(); onOpen(copy.id); }
    catch(cause) { setError(cause instanceof Error ? cause.message : "Duplicate failed."); }
    finally { setBusy(""); }
  };
  const remove = async (project:ProjectSummary) => {
    if (!window.confirm(`Delete “${project.name}”? This also removes its media and render history.`)) return;
    setBusy(project.id); setError("");
    try { await projectApi.remove(project.id); setNotice("Project deleted."); await load(); }
    catch(cause) { setError(cause instanceof Error ? cause.message : "Delete failed."); }
    finally { setBusy(""); }
  };

  return <section className="project-dashboard panel">
    <div className="dashboard-heading"><div><p className="eyebrow">YOUR CREATIVE SPACE</p><h2>Projects</h2><p className="hint">Your edits, neatly arranged and ready to roll.</p></div><span className="project-count">{projects.length} PROJECTS</span></div>
    <form className="create-project-form" onSubmit={(e)=>void create(e)}>
      <label>New project name<input value={name} onChange={(e)=>setName(e.target.value)} placeholder="e.g. Summer travel edit" maxLength={120}/></label>
      <button className="primary" disabled={!name.trim() || !!busy}>+ Create project</button>
    </form>
    <div className="dashboard-filters">
      <label className="project-search">Search projects<input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search by project name…"/></label>
      <label>Folder<select value={folder} onChange={e=>setFolder(e.target.value)}><option value="">All folders</option>{folders.map(item=><option key={item} value={item}>{item}</option>)}</select></label>
      <label>Sort<select value={sort} onChange={e=>setSort(e.target.value as SortMode)}><option value="updated_desc">Recently updated</option><option value="created_desc">Newest created</option><option value="created_asc">Oldest created</option><option value="name_asc">Name A to Z</option><option value="name_desc">Name Z to A</option></select></label>
      <label className="favorite-filter"><input type="checkbox" checked={favoritesOnly} onChange={e=>setFavoritesOnly(e.target.checked)}/> Favorites only</label>
    </div>
    {notice && <p className="dashboard-notice" role="status">{notice}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p className="hint">Loading your projects…</p> :
      projects.length===0 ? <div className="project-empty"><strong>No projects found</strong><span>Create a project above or change the current filters.</span></div> :
      <div className="project-grid">{projects.map((project)=> <article className="project-card" key={project.id}>
        <div className="project-card-art">
          {covers[project.id] ? <img src={covers[project.id]} alt={`${project.name} preview`} /> : <span>F</span>}
          <small>FLEXY AI PROJECT</small>
          <button className={`favorite-toggle ${project.is_favorite ? "active" : ""}`} title={project.is_favorite ? "Remove favorite" : "Add favorite"} aria-label={project.is_favorite ? "Remove favorite" : "Add favorite"} onClick={()=>void toggleFavorite(project)} disabled={!!busy}>{project.is_favorite ? "★" : "☆"}</button>
        </div>
        <div className="project-card-body"><strong title={project.name}>{project.name}</strong>
          <small>Updated {new Date(project.updated_at).toLocaleString()}</small>
          <small>{project.folder_name || "Unfiled"} · Revision {project.revision}</small>
          <button className="primary open-project" onClick={()=>onOpen(project.id)}>Open project ↗</button>
          <div className="project-card-actions">
            <button onClick={()=>void rename(project)} disabled={!!busy}>Rename</button>
            <button onClick={()=>void organize(project)} disabled={!!busy}>Folder</button>
            <button onClick={()=>void duplicate(project)} disabled={!!busy}>Duplicate</button>
            <button onClick={()=>void remove(project)} disabled={!!busy}>Delete</button>
          </div>
        </div>
      </article>)}</div>}
  </section>;
}
