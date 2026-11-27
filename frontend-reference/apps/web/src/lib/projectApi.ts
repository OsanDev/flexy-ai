const API = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
function csrf() {
  const item = document.cookie.split("; ").find((part) => part.startsWith("flexy_csrf="));
  if (!item) throw new Error("Session security token is missing. Sign in again.");
  return decodeURIComponent(item.slice("flexy_csrf=".length));
}
async function request<T>(path: string, init: RequestInit = {}, protect = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (protect) headers.set("X-CSRF-Token", csrf());
  const response = await fetch(`${API}${path}`, { ...init, headers, credentials: "include" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : payload.detail?.message;
    throw new Error(detail ?? `Project request failed (${response.status}).`);
  }
  return payload as T;
}
export interface CloudProject {
  id: string; name: string; revision: number; updated_at: string;
  project: Record<string, unknown>;
}
export interface ProjectSummary {
  id: string; name: string; revision: number; created_at: string; updated_at: string;
  folder_name?: string; is_favorite?: boolean | number;
}
export const projectApi = {
  // Backward-compatible signature: list(search) still accepts a plain search string.
  list(filters: {search?:string; folder?:string; favoritesOnly?:boolean; sort?:string} | string = {}) {
    const normalized = typeof filters === "string" ? {search:filters} : filters;
    const query = new URLSearchParams();
    if (normalized.search) query.set("search", normalized.search);
    if (normalized.folder) query.set("folder", normalized.folder);
    if (normalized.favoritesOnly) query.set("favorites_only", "true");
    if (normalized.sort) query.set("sort", normalized.sort);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<{projects:ProjectSummary[];folders:string[];sort:string}>(`/api/projects${suffix}`);
  },
  organize(projectId:string, patch:{folder_name?:string;is_favorite?:boolean}) {
    return request<ProjectSummary>(`/api/projects/${encodeURIComponent(projectId)}/organization`, {
      method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify(patch)
    }, true);
  },
  create(name: string) {
    const id = crypto.randomUUID();
    return request<{id:string;name:string;revision:number}>("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, project: { id, assets: [], tracks: [], timeline_document: {
        videoClips: [], audioClips: [], captions: [], width: 1920, height: 1080,
        frameRate: 30, exportPreset: "1080p", videoBitrate: "12M", ducking: false
      } }, expected_revision: 0 }),
    }, true);
  },
  rename(projectId: string, name: string) {
    return request<{id:string;name:string}>(`/api/projects/${encodeURIComponent(projectId)}/name`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }, true);
  },
  duplicate(projectId: string, name?: string) {
    return request<{id:string;name:string}>(`/api/projects/${encodeURIComponent(projectId)}/duplicate`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }, true);
  },
  remove(projectId: string) {
    return request<{id:string;deleted:boolean}>(`/api/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }, true);
  },
  load(projectId: string) {
    return request<CloudProject>(`/api/projects/${encodeURIComponent(projectId)}`);
  },
  save(projectId: string, name: string, project: Record<string, unknown>, expectedRevision: number) {
    return request<{id:string;name:string;revision:number;updated_at:string}>("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, project: { ...project, id: projectId }, expected_revision: expectedRevision }),
    }, true);
  },
};
