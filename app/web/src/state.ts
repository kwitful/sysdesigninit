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
  ts?: number;
};

export type ActivityEvent = {
  ts: number;
  kind: "file_ready" | "info";
  filename?: string | null;
  message: string;
};

export type Brief = {
  problem?: string | null;
  critical_flows?: string | null;
  scale?: string | null;
  quality_targets?: string | null;
  constraints?: string | null;
  maturity?: string | null;
  must_haves?: string | null;
  out_of_scope?: string | null;
  reasoning?: string | null;
};

export type TocEntry = {
  id: string;
  text: string;
  level: number;
};

export type MobileTab = "chat" | "docs" | "history";

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
  toc: TocEntry[];
  viewMode: "rendered" | "raw";
  error: string | null;
  statusMessage: string | null;
  browsingWorkspace: string | null;
  pastWorkspaces: {
    name: string;
    problem: string | null;
    mtime?: number | null;
    docs_count?: number;
  }[];
  pastFilter: string;
  pollTimer: number | null;
  docsCount: number;
  docsTotal: number;
  elapsedMs: number | null;
  currentStep: { id: string; label: string } | null;
  activity: ActivityEvent[];
  justCompleted: boolean;
  brief: Brief | null;
  overwriteWarning: string | null;
  showCompletionCard: boolean;
  mobileTab: MobileTab;
  useSse: boolean;
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
    toc: [],
    viewMode: "rendered",
    error: null,
    statusMessage: null,
    browsingWorkspace: null,
    pastWorkspaces: [],
    pastFilter: "",
    pollTimer: null,
    docsCount: 0,
    docsTotal: 12,
    elapsedMs: null,
    currentStep: null,
    activity: [],
    justCompleted: false,
    brief: null,
    overwriteWarning: null,
    showCompletionCard: false,
    mobileTab: "chat",
    useSse: true,
  };
}

export function isBusy(phase: Phase): boolean {
  return phase === "thinking" || phase === "generating";
}

export const STORAGE_KEY = "sysdesigninit.session.v1";
