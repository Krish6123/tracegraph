export type Entity = {
  id: string; name: string; entity_type: string; file_path: string;
  line_number: number; parent_id?: string | null;
};
export type Summary = {
  analysis_id: string; repository_path: string; total_entities: number;
  total_relationships: number; status: string; parse_errors?: string[][] | null;
  packages?: string[] | null; commit_hash?: string | null;
};
export type Relationship = { source_id: string; target_id: string; relationship_type: string };
export type Impact = {
  selected_entity: Entity; direct_dependencies: Entity[]; indirect_dependencies: Entity[];
  direct_dependents: Entity[]; indirect_dependents: Entity[];
};
export type GitImpact = {
  changes: { change_type: string; path: string; old_path?: string | null }[];
  mapped_entities: Entity[]; potentially_affected_dependents: Entity[];
};

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(baseUrl + "/api" + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error("Cannot reach the Tracegraph API. Start FastAPI and try again.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* Keep the HTTP status message. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  analyze: (repository_path: string) => request<Summary>("/analyze", {
    method: "POST", body: JSON.stringify({ repository_path }),
  }),
  summary: (id: string) => request<Summary>(`/analysis/${encodeURIComponent(id)}`),
  entities: (id: string) => request<Entity[]>(`/analysis/${encodeURIComponent(id)}/entities`),
  relationships: (id: string) => request<Relationship[]>(`/analysis/${encodeURIComponent(id)}/relationships`),
  impact: (id: string, entity: string) => request<Impact>(
    `/analysis/${encodeURIComponent(id)}/impact?entity_id=${encodeURIComponent(entity)}`,
  ),
  gitImpact: (id: string, base_ref?: string | null, target_ref?: string | null) => {
    const cleanBase = base_ref?.trim();
    const effectiveBase = (cleanBase && cleanBase !== "Saved analysis commit") ? cleanBase : null;
    return request<GitImpact>(
      `/analysis/${encodeURIComponent(id)}/git-impact`, {
        method: "POST", body: JSON.stringify({ base_ref: effectiveBase, target_ref: target_ref?.trim() || null }),
      },
    );
  },
};
