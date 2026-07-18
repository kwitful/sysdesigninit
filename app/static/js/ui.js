import { isBusy } from "./state.js";
import { deriveJourney, statusLineText, systemBanner, } from "./journey.js";
import { clearDoc, setDocHtml, setDocRaw } from "./markdown.js";
export function getRefs() {
    const el = (id) => {
        const node = document.getElementById(id);
        if (!node)
            throw new Error(`Missing element #${id}`);
        return node;
    };
    return {
        header: el("app-header"),
        designTitle: el("design-title"),
        statusLine: el("status-line"),
        progressLive: el("progress-live"),
        systemBanner: el("system-banner"),
        systemBannerText: el("system-banner-text"),
        backSessionBtn: el("back-session-btn"),
        cancelBtn: el("cancel-btn"),
        startOverBtn: el("start-over-btn"),
        layoutEl: el("layout"),
        railClarify: el("rail-clarify"),
        railGenerate: el("rail-generate"),
        railReview: el("rail-review"),
        railHistory: el("rail-history"),
        blockChat: el("block-chat"),
        blockDocs: el("block-docs"),
        chatEmptyEl: el("chat-empty"),
        transcriptEl: el("transcript"),
        formEl: el("chat-form"),
        inputEl: el("chat-input"),
        sendBtn: el("send-btn"),
        sendHint: el("send-hint"),
        reviewStrip: el("review-strip"),
        openBriefBtn: el("open-brief-btn"),
        openReviewBtn: el("open-review-btn"),
        openIndexBtn: el("open-index-btn"),
        prevDocBtn: el("prev-doc-btn"),
        nextDocBtn: el("next-doc-btn"),
        docPosition: el("doc-position"),
        toggleViewBtn: el("toggle-view-btn"),
        copyBtn: el("copy-btn"),
        downloadBtn: el("download-btn"),
        docTitleEl: el("doc-title"),
        docBodyEl: el("doc-body"),
        secClarify: el("sec-clarify"),
        secGenerate: el("sec-generate"),
        secReview: el("sec-review"),
        secHistory: el("sec-history"),
        clarifyTip: el("clarify-tip"),
        briefPanel: el("brief-panel"),
        briefBody: el("brief-body"),
        progressStrip: el("progress-strip"),
        sectionList: el("section-list"),
        sectionListReview: el("section-list-review"),
        activityEl: el("activity-feed"),
        tocEl: el("doc-toc"),
        pastListEl: el("past-list"),
        pastEmptyEl: el("past-empty"),
        pastFilterEl: el("past-filter"),
        mobileTabs: el("mobile-tabs"),
    };
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
    if (!brief)
        return;
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
}
function setRailState(refs, journey, state) {
    const order = [
        "clarify",
        "generate",
        "review",
    ];
    const effective = journey === "history" ? "review" : journey;
    const activeIndex = order.indexOf(effective);
    const canGenerate = state.docsCount > 0 || isBusy(state.phase) || !!state.workspace;
    const canReview = state.phase === "complete" ||
        (state.docsTotal > 0 && state.docsCount >= state.docsTotal);
    const buttons = [
        [refs.railClarify, "clarify", true],
        [refs.railGenerate, "generate", canGenerate],
        [refs.railReview, "review", canReview],
    ];
    for (let i = 0; i < buttons.length; i++) {
        const [btn, step, reachable] = buttons[i];
        btn.classList.remove("is-current", "is-done", "is-upcoming");
        btn.disabled = !reachable;
        if (journey !== "history" && step === journey) {
            btn.classList.add("is-current");
        }
        else if (i < activeIndex || (journey === "history" && reachable)) {
            btn.classList.add("is-done");
        }
        else {
            btn.classList.add("is-upcoming");
        }
    }
    refs.railHistory.classList.toggle("is-current", journey === "history");
}
function fillSectionList(listEl, state, selected) {
    listEl.replaceChildren();
    const steps = state.pipeline.length > 0
        ? state.pipeline
        : state.files.map((f) => ({
            id: f.name,
            label: f.name,
            status: f.ready ? "ready" : "pending",
        }));
    for (const step of steps) {
        const ready = step.status === "ready" ||
            state.files.some((f) => f.name === step.id && f.ready);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className =
            "section-btn" +
                (ready ? " is-ready" : "") +
                (selected === step.id ? " is-selected" : "");
        btn.disabled = !ready;
        btn.dataset.filename = step.id;
        btn.title = step.id;
        btn.textContent = step.label;
        listEl.appendChild(btn);
    }
}
export function render(state, refs) {
    const journey = deriveJourney(state);
    refs.layoutEl.dataset.journey = journey;
    refs.layoutEl.dataset.tab = state.mobileTab;
    const browsing = journey === "history";
    refs.header.classList.toggle("is-browsing", browsing);
    const titleProblem = state.browsingProblem ||
        state.problem ||
        (state.browsingWorkspace || state.workspace
            ? state.browsingWorkspace || state.workspace
            : null);
    refs.designTitle.textContent = titleProblem
        ? `Design: ${titleProblem}`
        : "AI system-design assistant";
    const status = statusLineText(state, journey);
    refs.statusLine.textContent = status;
    refs.progressLive.textContent = status;
    const banner = systemBanner(state, journey);
    if (banner) {
        refs.systemBanner.hidden = false;
        refs.systemBanner.dataset.kind = banner.kind;
        refs.systemBannerText.textContent = banner.text;
        refs.backSessionBtn.hidden = banner.kind !== "browse";
    }
    else {
        refs.systemBanner.hidden = true;
        refs.systemBannerText.textContent = "";
        refs.backSessionBtn.hidden = true;
    }
    setRailState(refs, journey, state);
    const busy = isBusy(state.phase);
    refs.sendBtn.disabled = busy || browsing;
    refs.inputEl.disabled = busy || browsing;
    refs.startOverBtn.disabled = busy;
    refs.cancelBtn.hidden = !busy || browsing;
    refs.cancelBtn.disabled = !busy;
    refs.sendHint.hidden = !busy;
    refs.sendHint.textContent = busy
        ? "Wait for the current turn to finish."
        : "";
    // Mobile tabs
    refs.mobileTabs.querySelectorAll("button").forEach((btn) => {
        const tab = btn.dataset.tab;
        btn.classList.toggle("is-active", tab === state.mobileTab);
    });
    // Primary blocks
    if (journey === "clarify") {
        refs.blockChat.hidden = false;
        refs.blockDocs.hidden = true;
    }
    else if (journey === "history" && !state.browsingWorkspace) {
        // History list only — keep chat visible as soft backdrop or hide docs empty
        refs.blockChat.hidden = false;
        refs.blockDocs.hidden = true;
    }
    else {
        refs.blockChat.hidden = true;
        refs.blockDocs.hidden = false;
    }
    // Chat transcript
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
    // Review strip
    refs.reviewStrip.hidden = journey !== "review";
    // Secondary panels
    refs.secClarify.hidden = journey !== "clarify";
    refs.secGenerate.hidden = journey !== "generate";
    refs.secReview.hidden = journey !== "review";
    refs.secHistory.hidden = journey !== "history";
    // Brief
    if (state.brief) {
        refs.briefPanel.hidden = false;
        refs.clarifyTip.hidden = true;
        renderBrief(state.brief, refs.briefBody);
    }
    else {
        refs.briefPanel.hidden = true;
        refs.clarifyTip.hidden = false;
    }
    // Progress + sections
    if (journey === "generate") {
        refs.progressStrip.hidden = false;
        refs.progressStrip.textContent = status;
        fillSectionList(refs.sectionList, state, state.selectedFile);
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
    }
    if (journey === "review" || journey === "history") {
        fillSectionList(refs.sectionListReview, state, state.selectedFile);
    }
    // TOC
    refs.tocEl.replaceChildren();
    if ((journey === "review" || journey === "history") &&
        state.toc.length &&
        state.viewMode === "rendered") {
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
    // Doc chrome
    const readyNames = state.pipeline
        .filter((p) => p.status === "ready" ||
        state.files.some((f) => f.name === p.id && f.ready))
        .map((p) => p.id);
    const readyFallback = state.files.filter((f) => f.ready).map((f) => f.name);
    const ready = readyNames.length ? readyNames : readyFallback;
    const idx = state.selectedFile ? ready.indexOf(state.selectedFile) : -1;
    refs.prevDocBtn.disabled = idx <= 0;
    refs.nextDocBtn.disabled = idx < 0 || idx >= ready.length - 1;
    const selectedLabel = state.pipeline.find((p) => p.id === state.selectedFile)?.label ||
        state.selectedFile ||
        "—";
    if (state.selectedFile && idx >= 0) {
        refs.docPosition.textContent = `${selectedLabel} · ${idx + 1} of ${ready.length}`;
    }
    else {
        refs.docPosition.textContent = selectedLabel;
    }
    refs.toggleViewBtn.textContent =
        state.viewMode === "rendered" ? "View source" : "View rendered";
    refs.toggleViewBtn.disabled = !state.selectedFile;
    if (state.selectedFile && state.viewMode === "raw" && state.docMarkdown) {
        refs.docTitleEl.textContent = selectedLabel;
        setDocRaw(refs.docBodyEl, state.docMarkdown);
        refs.copyBtn.disabled = false;
    }
    else if (state.selectedFile && state.docHtml) {
        refs.docTitleEl.textContent = selectedLabel;
        setDocHtml(refs.docBodyEl, state.docHtml);
        refs.copyBtn.disabled = !state.docMarkdown;
    }
    else if (state.selectedFile) {
        refs.docTitleEl.textContent = selectedLabel;
        clearDoc(refs.docBodyEl, "Loading…");
        refs.copyBtn.disabled = true;
    }
    else {
        refs.docTitleEl.textContent = "Document";
        clearDoc(refs.docBodyEl, ready.length === 0
            ? "Documents appear as the pipeline writes them."
            : "Select a section to read.");
        refs.copyBtn.disabled = true;
    }
    const activeWs = state.browsingWorkspace || state.workspace;
    if (activeWs && ready.length > 0) {
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
                    (state.browsingWorkspace === w.name ? " is-selected" : "");
            btn.dataset.workspace = w.name;
            if (w.problem)
                btn.dataset.problem = w.problem;
            const title = document.createElement("span");
            title.className = "past-name";
            title.textContent = w.problem || w.name;
            btn.appendChild(title);
            const meta = document.createElement("span");
            meta.className = "past-problem";
            const bits = [
                w.name,
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