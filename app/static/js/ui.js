import { isBusy } from "./state.js";
import { clearDoc, setDocHtml } from "./markdown.js";
export function getRefs() {
    const el = (id) => {
        const node = document.getElementById(id);
        if (!node)
            throw new Error(`Missing element #${id}`);
        return node;
    };
    return {
        phaseEl: el("phase"),
        errorEl: el("error-banner"),
        transcriptEl: el("transcript"),
        chatEmptyEl: el("chat-empty"),
        formEl: el("chat-form"),
        inputEl: el("chat-input"),
        sendBtn: el("send-btn"),
        newDesignBtn: el("new-design-btn"),
        pipelineEl: el("pipeline"),
        fileListEl: el("file-list"),
        docsEmptyEl: el("docs-empty"),
        docTitleEl: el("doc-title"),
        docBodyEl: el("doc-body"),
        copyBtn: el("copy-btn"),
        downloadBtn: el("download-btn"),
        pastListEl: el("past-list"),
        pastEmptyEl: el("past-empty"),
        workspaceLabelEl: el("workspace-label"),
    };
}
function phaseLabel(phase) {
    switch (phase) {
        case "idle":
            return "Ready";
        case "thinking":
            return "Thinking…";
        case "generating":
            return "Generating docs…";
        case "complete":
            return "Complete";
        case "error":
            return "Error";
        default:
            return phase;
    }
}
export function render(state, refs) {
    refs.phaseEl.textContent = phaseLabel(state.phase);
    refs.phaseEl.dataset.phase = state.phase;
    if (state.error) {
        refs.errorEl.hidden = false;
        refs.errorEl.textContent = state.error;
    }
    else {
        refs.errorEl.hidden = true;
        refs.errorEl.textContent = "";
    }
    const busy = isBusy(state.phase);
    const browsing = !!state.browsingWorkspace;
    refs.sendBtn.disabled = busy || browsing;
    refs.inputEl.disabled = busy || browsing;
    refs.newDesignBtn.disabled = busy;
    // Chat
    refs.transcriptEl.replaceChildren();
    if (state.messages.length === 0) {
        refs.chatEmptyEl.hidden = false;
    }
    else {
        refs.chatEmptyEl.hidden = true;
        for (const msg of state.messages) {
            const div = document.createElement("div");
            div.className = `msg msg-${msg.role}`;
            const role = document.createElement("div");
            role.className = "msg-role";
            role.textContent = msg.role === "user" ? "You" : "Assistant";
            const body = document.createElement("div");
            body.className = "msg-body";
            body.textContent = msg.text;
            div.append(role, body);
            refs.transcriptEl.appendChild(div);
        }
    }
    // Workspace label
    const activeWs = state.browsingWorkspace || state.workspace;
    refs.workspaceLabelEl.textContent = activeWs
        ? `Workspace: ${activeWs}${browsing ? " (read-only)" : ""}`
        : "No workspace yet";
    // Pipeline
    refs.pipelineEl.replaceChildren();
    for (const step of state.pipeline) {
        const li = document.createElement("li");
        li.className = `pipe-step pipe-${step.status}`;
        li.textContent = step.label;
        li.title = step.id;
        refs.pipelineEl.appendChild(li);
    }
    // Files
    refs.fileListEl.replaceChildren();
    const readyFiles = state.files.filter((f) => f.ready);
    if (readyFiles.length === 0) {
        refs.docsEmptyEl.hidden = false;
    }
    else {
        refs.docsEmptyEl.hidden = true;
        for (const f of readyFiles) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
                "file-btn" + (state.selectedFile === f.name ? " is-selected" : "");
            btn.textContent = f.name;
            btn.dataset.filename = f.name;
            refs.fileListEl.appendChild(btn);
        }
    }
    // Doc pane
    if (state.selectedFile && state.docHtml) {
        refs.docTitleEl.textContent = state.selectedFile;
        setDocHtml(refs.docBodyEl, state.docHtml);
        refs.copyBtn.disabled = !state.docMarkdown;
    }
    else if (state.selectedFile) {
        refs.docTitleEl.textContent = state.selectedFile;
        clearDoc(refs.docBodyEl, "Loading…");
        refs.copyBtn.disabled = true;
    }
    else {
        refs.docTitleEl.textContent = "Document";
        clearDoc(refs.docBodyEl, readyFiles.length === 0
            ? "Documents will appear here as the pipeline writes them."
            : "Select a file to read.");
        refs.copyBtn.disabled = true;
    }
    // Download
    if (activeWs && readyFiles.length > 0) {
        refs.downloadBtn.hidden = false;
        refs.downloadBtn.href = `/api/workspaces/${encodeURIComponent(activeWs)}/download`;
    }
    else {
        refs.downloadBtn.hidden = true;
        refs.downloadBtn.removeAttribute("href");
    }
    // Past workspaces
    refs.pastListEl.replaceChildren();
    if (state.pastWorkspaces.length === 0) {
        refs.pastEmptyEl.hidden = false;
    }
    else {
        refs.pastEmptyEl.hidden = true;
        for (const w of state.pastWorkspaces) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
                "past-btn" +
                    (state.browsingWorkspace === w.name ||
                        (!state.browsingWorkspace && state.workspace === w.name)
                        ? " is-selected"
                        : "");
            btn.dataset.workspace = w.name;
            const title = document.createElement("span");
            title.className = "past-name";
            title.textContent = w.name;
            btn.appendChild(title);
            if (w.problem) {
                const sub = document.createElement("span");
                sub.className = "past-problem";
                sub.textContent = w.problem;
                btn.appendChild(sub);
            }
            refs.pastListEl.appendChild(btn);
        }
    }
}
//# sourceMappingURL=ui.js.map