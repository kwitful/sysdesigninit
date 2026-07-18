export function createInitialState() {
    return {
        sessionId: null,
        phase: "idle",
        workspace: null,
        problem: null,
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
        browsingProblem: null,
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
        journeyOverride: null,
        forceHistory: false,
        mobileTab: "chat",
        useSse: true,
    };
}
export function isBusy(phase) {
    return phase === "thinking" || phase === "generating";
}
export const STORAGE_KEY = "sysdesigninit.session.v1";
//# sourceMappingURL=state.js.map