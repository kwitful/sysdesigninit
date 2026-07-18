import type {
  ActivityEvent,
  Brief,
  ChatMessage,
  FileEntry,
  Phase,
  PipelineStep,
  TocEntry,
} from "./state.js";

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
  status_message: string | null;
  docs_count: number;
  docs_total: number;
  elapsed_ms: number | null;
  current_step: { id: string; label: string } | null;
  activity: ActivityEvent[];
  just_completed: boolean;
  pipeline: PipelineStep[];
  messages: ChatMessage[];
  design_context: string | null;
  brief: Brief | null;
  overwrite_warning: string | null;
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

export async function ackComplete(id: string): Promise<void> {
  await request(`/api/sessions/${encodeURIComponent(id)}/ack-complete`, {
    method: "POST",
  });
}

export async function cancelSession(
  id: string
): Promise<{ session_id: string; phase: Phase; status_message: string | null }> {
  return request(`/api/sessions/${encodeURIComponent(id)}/cancel`, { method: "POST" });
}

export async function getSessionDocs(
  id: string
): Promise<{ workspace: string | null; files: FileEntry[]; pipeline: PipelineStep[] }> {
  return request(`/api/sessions/${encodeURIComponent(id)}/docs`);
}

export async function getSessionDoc(
  id: string,
  filename: string
): Promise<{ filename: string; markdown: string; html: string; toc: TocEntry[] }> {
  return request(
    `/api/sessions/${encodeURIComponent(id)}/docs/${encodeURIComponent(filename)}`
  );
}

export async function listWorkspaces(q?: string): Promise<{
  workspaces: {
    name: string;
    problem: string | null;
    mtime?: number | null;
    docs_count?: number;
  }[];
}> {
  const qs = q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  return request(`/api/workspaces${qs}`);
}

export async function getWorkspaceDocs(
  name: string
): Promise<{ workspace: string | null; files: FileEntry[]; pipeline: PipelineStep[] }> {
  return request(`/api/workspaces/${encodeURIComponent(name)}/docs`);
}

export async function getWorkspaceDoc(
  name: string,
  filename: string
): Promise<{ filename: string; markdown: string; html: string; toc: TocEntry[] }> {
  return request(
    `/api/workspaces/${encodeURIComponent(name)}/docs/${encodeURIComponent(filename)}`
  );
}

export async function getWorkspaceChat(
  name: string
): Promise<{ workspace: string; messages: ChatMessage[] }> {
  return request(`/api/workspaces/${encodeURIComponent(name)}/chat`);
}

export function workspaceDownloadUrl(name: string): string {
  return `/api/workspaces/${encodeURIComponent(name)}/download`;
}

export function sessionEventsUrl(id: string): string {
  return `/api/sessions/${encodeURIComponent(id)}/events`;
}
