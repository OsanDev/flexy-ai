const API = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function csrfToken(): string {
  const item = document.cookie.split("; ").find((part) => part.startsWith("flexy_csrf="));
  if (!item) throw new Error("Session security token is missing. Sign in again.");
  return decodeURIComponent(item.slice("flexy_csrf=".length));
}

export interface DirectorSuggestion { kind: string; title: string; detail: string; }
export interface DirectorPlan {
  provider: string; model?: string; summary: string; suggestions: DirectorSuggestion[];
  warnings: string[]; aspect_ratio: { id: string; label: string; width: number; height: number };
  asset_summary: { video: number; audio: number; image: number };
  timeline_draft?: { clips?: unknown; audio_clips?: unknown; warnings?: unknown }; message: string;
}

export const aiDirectorApi = {
  async plan(input: {
    projectId: string; instruction: string; project: Record<string, unknown>;
    assets: Array<{id:string;filename:string;mime_type:string;duration:number|null}>;
  }): Promise<DirectorPlan> {
    const response = await fetch(`${API}/api/assistant/plan`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
      body: JSON.stringify({ project_id: input.projectId, instruction: input.instruction,
        project: input.project, assets: input.assets }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : "FLEXY AI could not prepare a plan.";
      throw new Error(detail);
    }
    return payload as DirectorPlan;
  },
};
