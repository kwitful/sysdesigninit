export type Phase = "idle" | "thinking" | "generating" | "complete" | "error";

export type PipelineStep = {
  id: string;
  label: string;
  status: "pending" | "ready";
};

export type FileEntry = {
  name: string;
  ready: boolean;
};

export type ChatMessage = {
  role: "user" | "assistant";
  text: string;
};

export type AppState = {
  sessionId: string | null;
  phase: Phase;
  workspace: string | null;
  messages: ChatMessage[];
  lastAssistantSeen: string | null;
  files: FileEntry[];
  pipeline: PipelineStep[];
  selectedFile: string | null;
  docMarkdown: string;
  docHtml: string;
  error: string | null;
  /** When set, docs are loaded from a past workspace (read-only). */
  browsingWorkspace: string | null;
  pastWorkspaces: { name: string; problem: string | null }[];
  pollTimer: number | null;
};

export function createInitialState(): AppState {
  return {
    sessionId: null,
    phase: "idle",
    workspace: null,
    messages: [],
    lastAssistantSeen: null,
    files: [],
    pipeline: [],
    selectedFile: null,
    docMarkdown: "",
    docHtml: "",
    error: null,
    browsingWorkspace: null,
    pastWorkspaces: [],
    pollTimer: null,
  };
}

export function isBusy(phase: Phase): boolean {
  return phase === "thinking" || phase === "generating";
}
