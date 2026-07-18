import { isBusy } from "./state.js";
import { clearDoc, setDocHtml, setDocRaw } from "./markdown.js";
export function getRefs() {
    const el = (id) => {
        const node = document.getElementById(id);
        if (!node)
            throw new Error(`Missing element #${id}`);
        return node;
    };
    return {
        phaseEl: el("phase"),
        progressLive: el("progress-live"),
        errorEl: el("error-banner"),
        statusEl: el("status-banner"),
        browseBanner: el("browse-banner"),
        backSessionBtn: el("back-session-btn"),
        overwriteEl: el("overwrite-banner"),
        transcriptEl: el("transcript"),
        chatEmptyEl: el("chat-empty"),
        briefPanel: el("brief-panel"),
        briefBody: el("brief-body"),
        formEl: el("chat-form"),
        inputEl: el("chat-input"),
        sendBtn: el("send-btn"),
        sendHint: el("send-hint"),
        cancelBtn: el("cancel-btn"),
        newDesignBtn: el("new-design-btn"),
        pipelineEl: el("pipeline"),
        progressStrip: el("progress-strip"),
        activityEl: el("activity-feed"),
        completionCard: el("completion-card"),
        openBriefBtn: el("open-brief-btn"),
        openReviewBtn: el("open-review-btn"),
        dismissCompleteBtn: el("dismiss-complete-btn"),
        fileListEl: el("file-list"),
        docsEmptyEl: el("docs-empty"),
        docTitleEl: el("doc-title"),
        docBodyEl: el("doc-body"),
        tocEl: el("doc-toc"),
        copyBtn: el("copy-btn"),
        downloadBtn: el("download-btn"),
        prevDocBtn: el("prev-doc-btn"),
        nextDocBtn: el("next-doc-btn"),
        toggleViewBtn: el("toggle-view-btn"),
        pastListEl: el("past-list"),
        pastEmptyEl: el("past-empty"),
        pastFilterEl: el("past-filter"),
        workspaceLabelEl: el("workspace-label"),
        mobileTabs: el("mobile-tabs"),
        layoutEl: el("layout"),
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
function formatElapsed(ms) {
    if (ms == null)
        return "";
    const sec = Math.floor(ms / 1000);
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
function formatMtime(ts) {
    if (!ts)
        return "";
    try {
        return new Date(ts * 1000).toLocaleString();
    }
    catch {
        return "";
    }
}
function renderBrief(brief, container) {
    container.replaceChildren();
    if (!brief) {
        container.textContent = "Brief appears after the coordinator saves design context.";
        return;
    }
    const fields = [
        ["Problem", brief.problem],
        ["Critical flows", brief.critical_flows],
        ["Scale", brief.scale],
        ["Maturity", brief.maturity],
        ["Must-haves", brief.must_haves],
        ["Out of scope", brief.out_of_scope],
    ];
    for (const [label, value] of fields) {
        if (!value)
            continue;
        const block = document.createElement("div");
        block.className = "brief-field";
        const h = document.createElement("div");
        h.className = "brief-label";
        h.textContent = label;
        const body = document.createElement("div");
        body.className = "brief-text";
        body.textContent = value;
        block.append(h, body);
        container.appendChild(block);
    }
    if (!container.childElementCount) {
        container.textContent = "Brief sections not parsed yet.";
    }
}
export function render(state, refs) {
    refs.phaseEl.textContent = phaseLabel(state.phase);
    refs.phaseEl.dataset.phase = state.phase;
    const progressParts = [];
    if (isBusy(state.phase)) {
        progressParts.push(`${state.docsCount}/${state.docsTotal} documents`);
        const elapsed = formatElapsed(state.elapsedMs);
        if (elapsed)
            progressParts.push(elapsed);
        if (state.currentStep)
            progressParts.push(state.currentStep.label);
    }
    const progressText = progressParts.join(" · ");
    refs.progressStrip.textContent = progressText;
    refs.progressStrip.hidden = !progressText;
    refs.progressLive.textContent = `${phaseLabel(state.phase)}${progressText ? " — " + progressText : ""}`;
    if (state.error) {
        refs.errorEl.hidden = false;
        refs.errorEl.textContent = state.error;
    }
    else {
        refs.errorEl.hidden = true;
        refs.errorEl.textContent = "";
    }
    if (state.statusMessage) {
        refs.statusEl.hidden = false;
        refs.statusEl.textContent = state.statusMessage;
    }
    else {
        refs.statusEl.hidden = true;
        refs.statusEl.textContent = "";
    }
    if (state.overwriteWarning && !state.browsingWorkspace) {
        refs.overwriteEl.hidden = false;
        refs.overwriteEl.textContent = state.overwriteWarning;
    }
    else {
        refs.overwriteEl.hidden = true;
    }
    const browsing = !!state.browsingWorkspace;
    refs.browseBanner.hidden = !browsing;
    const busy = isBusy(state.phase);
    refs.sendBtn.disabled = busy || browsing;
    refs.inputEl.disabled = busy || browsing;
    refs.newDesignBtn.disabled = busy;
    refs.cancelBtn.hidden = !busy || browsing;
    refs.cancelBtn.disabled = !busy;
    refs.sendHint.hidden = !busy;
    refs.sendHint.textContent = busy
        ? "Wait for the current turn to finish."
        : "";
    // Mobile tabs
    refs.layoutEl.dataset.tab = state.mobileTab;
    refs.mobileTabs.querySelectorAll("button").forEach((btn) => {
        const tab = btn.dataset.tab;
        btn.classList.toggle("is-active", tab === state.mobileTab);
    });
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
    refs.briefPanel.hidden = browsing;
    renderBrief(state.brief, refs.briefBody);
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
    // Activity
    refs.activityEl.replaceChildren();
    if (busy && state.activity.length) {
        refs.activityEl.hidden = false;
        for (const a of state.activity.slice(-8).reverse()) {
            const li = document.createElement("li");
            li.textContent = a.message;
            refs.activityEl.appendChild(li);
        }
    }
    else {
        refs.activityEl.hidden = true;
    }
    // Completion card
    const showComplete = !browsing &&
        (state.showCompletionCard || state.justCompleted || state.phase === "complete") &&
        state.docsCount > 0;
    refs.completionCard.hidden = !showComplete || state.phase === "generating";
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
    // TOC
    refs.tocEl.replaceChildren();
    if (state.toc.length && state.viewMode === "rendered") {
        refs.tocEl.hidden = false;
        for (const t of state.toc) {
            const a = document.createElement("a");
            a.href = `#${t.id}`;
            a.className = `toc-link toc-l${t.level}`;
            a.textContent = t.text;
            a.dataset.tocId = t.id;
            refs.tocEl.appendChild(a);
        }
    }
    else {
        refs.tocEl.hidden = true;
    }
    // Doc pane
    const readyNames = readyFiles.map((f) => f.name);
    const idx = state.selectedFile ? readyNames.indexOf(state.selectedFile) : -1;
    refs.prevDocBtn.disabled = idx <= 0;
    refs.nextDocBtn.disabled = idx < 0 || idx >= readyNames.length - 1;
    refs.toggleViewBtn.textContent =
        state.viewMode === "rendered" ? "Raw" : "Rendered";
    refs.toggleViewBtn.disabled = !state.selectedFile;
    if (state.selectedFile && state.viewMode === "raw" && state.docMarkdown) {
        refs.docTitleEl.textContent = state.selectedFile;
        setDocRaw(refs.docBodyEl, state.docMarkdown);
        refs.copyBtn.disabled = false;
    }
    else if (state.selectedFile && state.docHtml) {
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
    const filtered = state.pastWorkspaces;
    if (filtered.length === 0) {
        refs.pastEmptyEl.hidden = false;
    }
    else {
        refs.pastEmptyEl.hidden = true;
        for (const w of filtered) {
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
            const meta = document.createElement("span");
            meta.className = "past-problem";
            const bits = [
                w.problem || "",
                typeof w.docs_count === "number" ? `${w.docs_count} docs` : "",
                formatMtime(w.mtime),
            ].filter(Boolean);
            meta.textContent = bits.join(" · ");
            btn.appendChild(meta);
            refs.pastListEl.appendChild(btn);
        }
    }
}
export function scrollTranscriptToEnd(refs) {
    refs.transcriptEl.scrollTop = refs.transcriptEl.scrollHeight;
}
//# sourceMappingURL=ui.js.map