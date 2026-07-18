export function createInitialState() {
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
export function isBusy(phase) {
    return phase === "thinking" || phase === "generating";
}
//# sourceMappingURL=state.js.map