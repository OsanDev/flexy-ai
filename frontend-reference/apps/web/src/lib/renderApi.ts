/**
 * FLEXY AI authenticated render API client.
 *
 * This authenticated client is used by the export panel in the web application.
 * Backend authentication uses HttpOnly flexy_session + readable flexy_csrf cookies.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const CSRF_COOKIE = "flexy_csrf";

export type RenderStatus =
  | "queued" | "processing" | "cancelling"
  | "completed" | "failed" | "cancelled" | "interrupted";

export interface RenderJob {
  id: string;
  project_id: string;
  status: RenderStatus;
  progress: number;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
  download_url?: string;
}

export interface RenderPreflight {
  [key: string]: unknown;
}

export interface CreateRenderResponse {
  id: string;
  status: "queued";
  status_url: string;
}

export class RenderApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "RenderApiError";
  }
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  csrf = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrf) {
    const token = readCookie(CSRF_COOKIE);
    if (!token) {
      throw new RenderApiError("Your session security token is missing. Sign in again.", 403);
    }
    headers.set("X-CSRF-Token", token);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `Render request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the stable status-based message for non-JSON responses.
    }
    throw new RenderApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const renderApi = {
  preflight(projectId: string, graph: Record<string, unknown>) {
    return request<RenderPreflight>(
      `/api/projects/${encodeURIComponent(projectId)}/render-preflight`,
      { method: "POST", body: JSON.stringify({ graph }) },
      true,
    );
  },

  create(projectId: string, graph: Record<string, unknown>) {
    return request<CreateRenderResponse>(
      `/api/projects/${encodeURIComponent(projectId)}/renders`,
      { method: "POST", body: JSON.stringify({ graph }) },
      true,
    );
  },

  list(projectId: string) {
    return request<{ renders: RenderJob[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/renders`,
    );
  },

  status(jobId: string) {
    return request<RenderJob>(`/api/renders/${encodeURIComponent(jobId)}`);
  },

  cancel(jobId: string) {
    return request<{ id: string; status: RenderStatus; message: string }>(
      `/api/renders/${encodeURIComponent(jobId)}/cancel`,
      { method: "POST" },
      true,
    );
  },

  remove(jobId: string) {
    return request<{ id: string; deleted: boolean }>(
      `/api/renders/${encodeURIComponent(jobId)}`,
      { method: "DELETE" },
      true,
    );
  },

  async download(jobId: string): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/api/renders/${encodeURIComponent(jobId)}/download`,
      { credentials: "include" },
    );
    if (!response.ok) {
      let message = `Download failed (${response.status}).`;
      try {
        const body = await response.json();
        if (typeof body.detail === "string") message = body.detail;
      } catch { /* use status fallback */ }
      throw new RenderApiError(message, response.status);
    }
    return response.blob();
  },
};
