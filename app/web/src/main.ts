import * as api from "./api.js";
import {
  createInitialState,
  isBusy,
  STORAGE_KEY,
  type AppState,
} from "./state.js";
import { getRefs, render, scrollTranscriptToEnd } from "./ui.js";

const POLL_MS = 1500;
const BRIEF_FILE = "00-problem-brief.md";
const REVIEW_FILE = "00-review.md";

const state: AppState = createInitialState();
const refs = getRefs();
let eventSource: EventSource | null = null;
let applyingHash = false;

function paint(): void {
  render(state, refs);
}

function saveSessionStorage(): void {
  if (!state.sessionId || state.browsingWorkspace) return;
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        sessionId: state.sessionId,
        messages: state.messages,
        workspace: state.workspace,
      })
    );
  } catch {
    /* ignore quota */
  }
}

function loadSessionStorage(): {
  sessionId: string;
  messages: AppState["messages"];
  workspace: string | null;
} | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as {
      sessionId?: string;
      messages?: AppState["messages"];
      workspace?: string | null;
    };
    if (!data.sessionId) return null;
    return {
      sessionId: data.sessionId,
      messages: Array.isArray(data.messages) ? data.messages : [],
      workspace: data.workspace ?? null,
    };
  } catch {
    return null;
  }
}

function clearSessionStorage(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function stopPolling(): void {
  if (state.pollTimer !== null) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function stopSse(): void {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function stopLive(): void {
  stopPolling();
  stopSse();
}

function startPolling(): void {
  if (state.pollTimer !== null) return;
  state.pollTimer = window.setInterval(() => {
    void tick();
  }, POLL_MS);
}

function startSse(): void {
  if (!state.sessionId || !state.useSse) {
    startPolling();
    return;
  }
  stopSse();
  try {
    const es = new EventSource(api.sessionEventsUrl(state.sessionId));
    eventSource = es;
    es.addEventListener("state", (ev) => {
      try {
        const snap = JSON.parse((ev as MessageEvent).data) as api.SessionState;
        applySnapshot(snap);
        void afterSnapshot(snap);
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("done", () => {
      stopSse();
    });
    es.onerror = () => {
      stopSse();
      state.useSse = false;
      if (isBusy(state.phase)) startPolling();
    };
  } catch {
    state.useSse = false;
    startPolling();
  }
}

function startLive(): void {
  if (state.useSse) startSse();
  else startPolling();
}

async function ensureSession(): Promise<string> {
  if (state.sessionId) return state.sessionId;
  const created = await api.createSession();
  state.sessionId = created.session_id;
  state.phase = created.phase;
  saveSessionStorage();
  return state.sessionId;
}

async function refreshPast(): Promise<void> {
  try {
    const data = await api.listWorkspaces(state.pastFilter || undefined);
    state.pastWorkspaces = data.workspaces;
  } catch {
    /* non-fatal */
  }
}

function readyPipelineOrder(): string[] {
  return state.pipeline.filter((p) => p.status === "ready").map((p) => p.id);
}

async function loadDoc(filename: string): Promise<void> {
  state.selectedFile = filename;
  state.docHtml = "";
  state.docMarkdown = "";
  state.toc = [];
  paint();
  try {
    const doc = state.browsingWorkspace
      ? await api.getWorkspaceDoc(state.browsingWorkspace, filename)
      : state.sessionId
        ? await api.getSessionDoc(state.sessionId, filename)
        : null;
    if (!doc) return;
    if (state.selectedFile !== filename) return;
    state.docMarkdown = doc.markdown;
    state.docHtml = doc.html;
    state.toc = doc.toc || [];
    updateHash();
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Failed to load document.";
  }
  paint();
}

async function refreshDocs(): Promise<void> {
  try {
    const data = state.browsingWorkspace
      ? await api.getWorkspaceDocs(state.browsingWorkspace)
      : state.sessionId
        ? await api.getSessionDocs(state.sessionId)
        : null;
    if (!data) return;
    state.files = data.files;
    if (data.pipeline) state.pipeline = data.pipeline;
    if (!state.browsingWorkspace && data.workspace) {
      state.workspace = data.workspace;
    }
    const ready = data.files.filter((f) => f.ready);
    if (!state.selectedFile && ready.length) {
      const prefer =
        ready.find((f) => f.name === BRIEF_FILE) ||
        ready[0];
      if (prefer) await loadDoc(prefer.name);
    } else if (state.selectedFile) {
      const still = ready.find((f) => f.name === state.selectedFile);
      if (still && !state.docHtml && state.viewMode === "rendered") {
        await loadDoc(still.name);
      }
    }
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Failed to list documents.";
  }
}

function applySnapshot(snap: api.SessionState): void {
  state.phase = snap.phase;
  state.workspace = snap.workspace;
  state.pipeline = snap.pipeline;
  state.error = snap.error;
  state.statusMessage = snap.status_message;
  state.docsCount = snap.docs_count;
  state.docsTotal = snap.docs_total;
  state.elapsedMs = snap.elapsed_ms;
  state.currentStep = snap.current_step;
  state.activity = snap.activity || [];
  state.justCompleted = snap.just_completed;
  state.brief = snap.brief;
  state.overwriteWarning = snap.overwrite_warning;
  if (snap.just_completed || snap.phase === "complete") {
    state.showCompletionCard = true;
  }
  if (snap.messages && snap.messages.length) {
    // Prefer server messages when longer (hydrated)
    if (snap.messages.length >= state.messages.length) {
      state.messages = snap.messages.map((m) => ({
        role: m.role,
        text: m.text,
        ts: m.ts,
      }));
    }
  }
  if (
    snap.last_assistant &&
    snap.last_assistant !== state.lastAssistantSeen
  ) {
    state.lastAssistantSeen = snap.last_assistant;
    const last = state.messages[state.messages.length - 1];
    if (!(last && last.role === "assistant" && last.text === snap.last_assistant)) {
      state.messages.push({ role: "assistant", text: snap.last_assistant });
    }
  }
  saveSessionStorage();
}

async function afterSnapshot(snap: api.SessionState): Promise<void> {
  if (snap.workspace || snap.docs_count > 0 || isBusy(snap.phase)) {
    await refreshDocs();
    if (
      (snap.just_completed || snap.phase === "complete") &&
      !state.browsingWorkspace
    ) {
      const hasBrief = state.files.some((f) => f.name === BRIEF_FILE && f.ready);
      if (hasBrief && state.selectedFile !== BRIEF_FILE) {
        await loadDoc(BRIEF_FILE);
      }
    }
  }
  if (!isBusy(snap.phase)) {
    stopLive();
    await refreshPast();
  }
  paint();
  scrollTranscriptToEnd(refs);
}

async function tick(): Promise<void> {
  if (!state.sessionId || state.browsingWorkspace) {
    if (!isBusy(state.phase)) stopLive();
    return;
  }
  try {
    const snap = await api.getSession(state.sessionId);
    applySnapshot(snap);
    await afterSnapshot(snap);
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Poll failed.";
    stopLive();
    paint();
  }
}

async function onSend(text: string): Promise<void> {
  const trimmed = text.trim();
  if (!trimmed || isBusy(state.phase) || state.browsingWorkspace) return;

  state.browsingWorkspace = null;
  state.error = null;
  state.statusMessage = null;
  state.messages.push({ role: "user", text: trimmed });
  refs.inputEl.value = "";
  paint();
  scrollTranscriptToEnd(refs);
  saveSessionStorage();

  try {
    const id = await ensureSession();
    await api.postMessage(id, trimmed);
    state.phase = "thinking";
    startLive();
    await tick();
  } catch (err) {
    if (err instanceof api.ApiError && err.status === 409) {
      state.error = "A turn is already in progress.";
    } else {
      state.error = err instanceof Error ? err.message : "Send failed.";
      state.phase = "error";
    }
    paint();
  }
}

async function onNewDesign(): Promise<void> {
  if (
    state.messages.length > 0 ||
    state.docsCount > 0 ||
    state.files.some((f) => f.ready)
  ) {
    const ok = window.confirm(
      "Start a new design? Current chat will be cleared (docs on disk remain)."
    );
    if (!ok) return;
  }
  stopLive();
  state.browsingWorkspace = null;
  state.messages = [];
  state.lastAssistantSeen = null;
  state.files = [];
  state.pipeline = [];
  state.selectedFile = null;
  state.docHtml = "";
  state.docMarkdown = "";
  state.toc = [];
  state.workspace = null;
  state.error = null;
  state.statusMessage = null;
  state.phase = "idle";
  state.brief = null;
  state.activity = [];
  state.justCompleted = false;
  state.showCompletionCard = false;
  state.overwriteWarning = null;
  state.docsCount = 0;
  clearSessionStorage();
  // Drop any past-workspace hash so reload does not re-enter browse mode.
  history.replaceState(null, "", location.pathname + location.search);

  try {
    if (state.sessionId) {
      const reset = await api.resetSession(state.sessionId);
      state.sessionId = reset.session_id;
      state.phase = reset.phase;
    } else {
      await ensureSession();
    }
    saveSessionStorage();
    await refreshPast();
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Reset failed.";
  }
  paint();
}

async function onCancel(): Promise<void> {
  if (!state.sessionId || !isBusy(state.phase)) return;
  const ok = window.confirm(
    "Stop generation? Partial documents may remain on disk."
  );
  if (!ok) return;
  try {
    const res = await api.cancelSession(state.sessionId);
    state.phase = res.phase;
    state.statusMessage = res.status_message;
    stopLive();
    await tick();
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Cancel failed.";
    paint();
  }
}

async function backToSession(): Promise<void> {
  state.browsingWorkspace = null;
  state.error = null;
  if (state.sessionId) {
    try {
      const snap = await api.getSession(state.sessionId);
      applySnapshot(snap);
      await refreshDocs();
    } catch {
      /* ignore */
    }
  }
  updateHash();
  paint();
}

async function openPastWorkspace(name: string): Promise<void> {
  stopLive();
  state.browsingWorkspace = name;
  state.selectedFile = null;
  state.docHtml = "";
  state.docMarkdown = "";
  state.toc = [];
  state.error = null;
  state.pipeline = [];
  state.showCompletionCard = false;
  state.mobileTab = "docs";
  paint();
  try {
    const chat = await api.getWorkspaceChat(name);
    if (chat.messages.length) {
      state.messages = chat.messages;
    }
  } catch {
    /* optional */
  }
  await refreshDocs();
  updateHash();
  paint();
}

function updateHash(): void {
  if (applyingHash) return;
  const file = state.selectedFile;
  let hash = "";
  if (state.browsingWorkspace && file) {
    hash = `#/w/${encodeURIComponent(state.browsingWorkspace)}/d/${encodeURIComponent(file)}`;
  } else if (state.browsingWorkspace) {
    hash = `#/w/${encodeURIComponent(state.browsingWorkspace)}`;
  } else if (file) {
    hash = `#/d/${encodeURIComponent(file)}`;
  }
  if (location.hash !== hash) {
    history.replaceState(null, "", hash || location.pathname);
  }
}

async function applyHash(): Promise<void> {
  const h = location.hash.replace(/^#/, "");
  if (!h.startsWith("/")) return;
  applyingHash = true;
  try {
    const parts = h.split("/").filter(Boolean);
    // /w/name/d/file or /w/name or /d/file
    if (parts[0] === "w" && parts[1]) {
      const name = decodeURIComponent(parts[1]);
      await openPastWorkspace(name);
      if (parts[2] === "d" && parts[3]) {
        await loadDoc(decodeURIComponent(parts[3]));
      }
    } else if (parts[0] === "d" && parts[1]) {
      await loadDoc(decodeURIComponent(parts[1]));
    }
  } finally {
    applyingHash = false;
  }
}

function neighborDoc(delta: number): string | null {
  const ready = readyPipelineOrder().filter((name) =>
    state.files.some((f) => f.name === name && f.ready)
  );
  if (!state.selectedFile) return null;
  const idx = ready.indexOf(state.selectedFile);
  if (idx < 0) return null;
  return ready[idx + delta] || null;
}

async function init(): Promise<void> {
  refs.formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    void onSend(refs.inputEl.value);
  });

  refs.inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSend(refs.inputEl.value);
    }
  });

  refs.newDesignBtn.addEventListener("click", () => {
    void onNewDesign();
  });

  refs.cancelBtn.addEventListener("click", () => {
    void onCancel();
  });

  refs.backSessionBtn.addEventListener("click", () => {
    void backToSession();
  });

  refs.copyBtn.addEventListener("click", () => {
    if (!state.docMarkdown) return;
    void navigator.clipboard.writeText(state.docMarkdown).then(
      () => {
        const prev = refs.copyBtn.textContent;
        refs.copyBtn.textContent = "Copied";
        window.setTimeout(() => {
          refs.copyBtn.textContent = prev;
        }, 1200);
      },
      () => {
        state.error = "Clipboard copy failed.";
        paint();
      }
    );
  });

  refs.fileListEl.addEventListener("click", (e) => {
    const target = e.target as HTMLElement | null;
    const btn = target?.closest("button.file-btn") as HTMLButtonElement | null;
    if (!btn?.dataset.filename) return;
    void loadDoc(btn.dataset.filename);
  });

  refs.pastListEl.addEventListener("click", (e) => {
    const target = e.target as HTMLElement | null;
    const btn = target?.closest("button.past-btn") as HTMLButtonElement | null;
    if (!btn?.dataset.workspace) return;
    void openPastWorkspace(btn.dataset.workspace);
  });

  refs.pastFilterEl.addEventListener("input", () => {
    state.pastFilter = refs.pastFilterEl.value;
    void refreshPast().then(paint);
  });

  refs.prevDocBtn.addEventListener("click", () => {
    const name = neighborDoc(-1);
    if (name) void loadDoc(name);
  });

  refs.nextDocBtn.addEventListener("click", () => {
    const name = neighborDoc(1);
    if (name) void loadDoc(name);
  });

  refs.toggleViewBtn.addEventListener("click", () => {
    state.viewMode = state.viewMode === "rendered" ? "raw" : "rendered";
    paint();
  });

  refs.openBriefBtn.addEventListener("click", () => {
    void loadDoc(BRIEF_FILE);
  });

  refs.openReviewBtn.addEventListener("click", () => {
    void loadDoc(REVIEW_FILE);
  });

  refs.dismissCompleteBtn.addEventListener("click", () => {
    state.showCompletionCard = false;
    state.justCompleted = false;
    if (state.sessionId) {
      void api.ackComplete(state.sessionId).catch(() => undefined);
    }
    paint();
  });

  refs.docBodyEl.addEventListener("click", (e) => {
    const target = e.target as HTMLElement | null;
    const link = target?.closest("a[data-doc]") as HTMLAnchorElement | null;
    if (link?.dataset.doc) {
      e.preventDefault();
      void loadDoc(link.dataset.doc);
    }
  });

  refs.tocEl.addEventListener("click", (e) => {
    const target = e.target as HTMLElement | null;
    const a = target?.closest("a[data-toc-id]") as HTMLAnchorElement | null;
    if (!a?.dataset.tocId) return;
    e.preventDefault();
    const heading = refs.docBodyEl.querySelector(`#${CSS.escape(a.dataset.tocId)}`);
    heading?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  refs.mobileTabs.addEventListener("click", (e) => {
    const target = e.target as HTMLElement | null;
    const btn = target?.closest("button[data-tab]") as HTMLButtonElement | null;
    if (!btn?.dataset.tab) return;
    state.mobileTab = btn.dataset.tab as AppState["mobileTab"];
    paint();
  });

  window.addEventListener("hashchange", () => {
    void applyHash();
  });

  try {
    const cached = loadSessionStorage();
    if (cached) {
      state.sessionId = cached.sessionId;
      state.messages = cached.messages;
      state.workspace = cached.workspace;
      try {
        const snap = await api.getSession(cached.sessionId);
        applySnapshot(snap);
        if (isBusy(snap.phase)) startLive();
      } catch {
        // Session gone after restart — keep local messages, create new session
        state.sessionId = null;
        await ensureSession();
      }
    } else {
      await ensureSession();
    }
    await refreshPast();
    if (location.hash) await applyHash();
  } catch (err) {
    state.error = err instanceof Error ? err.message : "Failed to start session.";
  }
  paint();
}

void init();
