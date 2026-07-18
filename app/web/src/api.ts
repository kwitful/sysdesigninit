import type { FileEntry, Phase, PipelineStep } from "./state.js";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type SessionState = {
  session_id: string;
  phase: Phase;
  workspace: string | null;
  last_assistant: string | null;
  last_user: string | null;
  error: string | null;
  docs_count: number;
  pipeline: PipelineStep[];
};

export async function createSession(): Promise<{ session_id: string; phase: Phase }> {
  return request("/api/sessions", { method: "POST" });
}

export async function getSession(id: string): Promise<SessionState> {
  return request(`/api/sessions/${encodeURIComponent(id)}`);
}

export async function postMessage(id: string, text: string): Promise<void> {
  await request(`/api/sessions/${encodeURIComponent(id)}/messages`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function resetSession(id: string): Promise<{ session_id: string; phase: Phase }> {
  return request(`/api/sessions/${encodeURIComponent(id)}/reset`, { method: "POST" });
}

export async function getSessionDocs(
  id: string
): Promise<{ workspace: string | null; files: FileEntry[]; pipeline: PipelineStep[] }> {
  return request(`/api/sessions/${encodeURIComponent(id)}/docs`);
}

export async function getSessionDoc(
  id: string,
  filename: string
): Promise<{ filename: string; markdown: string; html: string }> {
  return request(
    `/api/sessions/${encodeURIComponent(id)}/docs/${encodeURIComponent(filename)}`
  );
}

export async function listWorkspaces(): Promise<{
  workspaces: { name: string; problem: string | null }[];
}> {
  return request("/api/workspaces");
}

export async function getWorkspaceDocs(
  name: string
): Promise<{ workspace: string | null; files: FileEntry[]; pipeline: PipelineStep[] }> {
  return request(`/api/workspaces/${encodeURIComponent(name)}/docs`);
}

export async function getWorkspaceDoc(
  name: string,
  filename: string
): Promise<{ filename: string; markdown: string; html: string }> {
  return request(
    `/api/workspaces/${encodeURIComponent(name)}/docs/${encodeURIComponent(filename)}`
  );
}

export function workspaceDownloadUrl(name: string): string {
  return `/api/workspaces/${encodeURIComponent(name)}/download`;
}
