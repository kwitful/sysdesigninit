import * as api from "./api.js";
import { createInitialState, isBusy } from "./state.js";
import { getRefs, render } from "./ui.js";
const POLL_MS = 1500;
const state = createInitialState();
const refs = getRefs();
function paint() {
    render(state, refs);
}
function stopPolling() {
    if (state.pollTimer !== null) {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}
function startPolling() {
    if (state.pollTimer !== null)
        return;
    state.pollTimer = window.setInterval(() => {
        void tick();
    }, POLL_MS);
}
async function ensureSession() {
    if (state.sessionId)
        return state.sessionId;
    const created = await api.createSession();
    state.sessionId = created.session_id;
    state.phase = created.phase;
    return state.sessionId;
}
async function refreshPast() {
    try {
        const data = await api.listWorkspaces();
        state.pastWorkspaces = data.workspaces;
    }
    catch {
        /* non-fatal */
    }
}
async function loadDoc(filename) {
    state.selectedFile = filename;
    state.docHtml = "";
    state.docMarkdown = "";
    paint();
    try {
        const doc = state.browsingWorkspace
            ? await api.getWorkspaceDoc(state.browsingWorkspace, filename)
            : state.sessionId
                ? await api.getSessionDoc(state.sessionId, filename)
                : null;
        if (!doc)
            return;
        if (state.selectedFile !== filename)
            return;
        state.docMarkdown = doc.markdown;
        state.docHtml = doc.html;
    }
    catch (err) {
        state.error = err instanceof Error ? err.message : "Failed to load document.";
    }
    paint();
}
async function refreshDocs() {
    try {
        const data = state.browsingWorkspace
            ? await api.getWorkspaceDocs(state.browsingWorkspace)
            : state.sessionId
                ? await api.getSessionDocs(state.sessionId)
                : null;
        if (!data)
            return;
        state.files = data.files;
        if (data.pipeline) {
            state.pipeline = data.pipeline;
        }
        if (!state.browsingWorkspace && data.workspace) {
            state.workspace = data.workspace;
        }
        // Auto-select first ready file if none selected
        if (!state.selectedFile) {
            const first = data.files.find((f) => f.ready);
            if (first)
                await loadDoc(first.name);
        }
        else if (state.selectedFile) {
            const still = data.files.find((f) => f.name === state.selectedFile && f.ready);
            if (still && !state.docHtml)
                await loadDoc(still.name);
        }
    }
    catch (err) {
        state.error = err instanceof Error ? err.message : "Failed to list documents.";
    }
}
async function tick() {
    if (!state.sessionId || state.browsingWorkspace) {
        if (!isBusy(state.phase))
            stopPolling();
        return;
    }
    try {
        const snap = await api.getSession(state.sessionId);
        state.phase = snap.phase;
        state.workspace = snap.workspace;
        state.pipeline = snap.pipeline;
        state.error = snap.error;
        if (snap.last_assistant &&
            snap.last_assistant !== state.lastAssistantSeen) {
            state.lastAssistantSeen = snap.last_assistant;
            const last = state.messages[state.messages.length - 1];
            if (!(last && last.role === "assistant" && last.text === snap.last_assistant)) {
                state.messages.push({ role: "assistant", text: snap.last_assistant });
            }
        }
        if (snap.workspace || snap.docs_count > 0 || isBusy(snap.phase)) {
            await refreshDocs();
        }
        if (!isBusy(snap.phase)) {
            stopPolling();
            await refreshPast();
        }
    }
    catch (err) {
        state.error = err instanceof Error ? err.message : "Poll failed.";
        stopPolling();
    }
    paint();
}
async function onSend(text) {
    const trimmed = text.trim();
    if (!trimmed || isBusy(state.phase) || state.browsingWorkspace)
        return;
    state.browsingWorkspace = null;
    state.error = null;
    state.messages.push({ role: "user", text: trimmed });
    refs.inputEl.value = "";
    paint();
    try {
        const id = await ensureSession();
        await api.postMessage(id, trimmed);
        state.phase = "thinking";
        startPolling();
        await tick();
    }
    catch (err) {
        if (err instanceof api.ApiError && err.status === 409) {
            state.error = "A turn is already in progress.";
        }
        else {
            state.error = err instanceof Error ? err.message : "Send failed.";
            state.phase = "error";
        }
        // Roll back optimistic user message? Keep it for context.
        paint();
    }
}
async function onNewDesign() {
    stopPolling();
    state.browsingWorkspace = null;
    state.messages = [];
    state.lastAssistantSeen = null;
    state.files = [];
    state.pipeline = [];
    state.selectedFile = null;
    state.docHtml = "";
    state.docMarkdown = "";
    state.workspace = null;
    state.error = null;
    state.phase = "idle";
    try {
        if (state.sessionId) {
            const reset = await api.resetSession(state.sessionId);
            state.sessionId = reset.session_id;
            state.phase = reset.phase;
        }
        else {
            await ensureSession();
        }
        await refreshPast();
    }
    catch (err) {
        state.error = err instanceof Error ? err.message : "Reset failed.";
    }
    paint();
}
async function openPastWorkspace(name) {
    stopPolling();
    state.browsingWorkspace = name;
    state.selectedFile = null;
    state.docHtml = "";
    state.docMarkdown = "";
    state.error = null;
    state.pipeline = [];
    paint();
    await refreshDocs();
    paint();
}
async function init() {
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
    refs.copyBtn.addEventListener("click", () => {
        if (!state.docMarkdown)
            return;
        void navigator.clipboard.writeText(state.docMarkdown).then(() => {
            const prev = refs.copyBtn.textContent;
            refs.copyBtn.textContent = "Copied";
            window.setTimeout(() => {
                refs.copyBtn.textContent = prev;
            }, 1200);
        }, () => {
            state.error = "Clipboard copy failed.";
            paint();
        });
    });
    refs.fileListEl.addEventListener("click", (e) => {
        const target = e.target;
        const btn = target?.closest("button.file-btn");
        if (!btn?.dataset.filename)
            return;
        void loadDoc(btn.dataset.filename);
    });
    refs.pastListEl.addEventListener("click", (e) => {
        const target = e.target;
        const btn = target?.closest("button.past-btn");
        if (!btn?.dataset.workspace)
            return;
        void openPastWorkspace(btn.dataset.workspace);
    });
    try {
        await ensureSession();
        await refreshPast();
    }
    catch (err) {
        state.error = err instanceof Error ? err.message : "Failed to start session.";
    }
    paint();
}
void init();
//# sourceMappingURL=main.js.map