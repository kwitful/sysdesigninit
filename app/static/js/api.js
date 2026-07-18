export class ApiError extends Error {
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
async function parseError(res) {
    try {
        const data = (await res.json());
        if (typeof data.detail === "string")
            return data.detail;
        if (Array.isArray(data.detail) && data.detail[0]?.msg)
            return data.detail[0].msg;
    }
    catch {
        /* ignore */
    }
    return res.statusText || `HTTP ${res.status}`;
}
async function request(url, init) {
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
    if (res.status === 204)
        return undefined;
    return (await res.json());
}
export async function createSession() {
    return request("/api/sessions", { method: "POST" });
}
export async function getSession(id) {
    return request(`/api/sessions/${encodeURIComponent(id)}`);
}
export async function postMessage(id, text) {
    await request(`/api/sessions/${encodeURIComponent(id)}/messages`, {
        method: "POST",
        body: JSON.stringify({ text }),
    });
}
export async function resetSession(id) {
    return request(`/api/sessions/${encodeURIComponent(id)}/reset`, { method: "POST" });
}
export async function getSessionDocs(id) {
    return request(`/api/sessions/${encodeURIComponent(id)}/docs`);
}
export async function getSessionDoc(id, filename) {
    return request(`/api/sessions/${encodeURIComponent(id)}/docs/${encodeURIComponent(filename)}`);
}
export async function listWorkspaces() {
    return request("/api/workspaces");
}
export async function getWorkspaceDocs(name) {
    return request(`/api/workspaces/${encodeURIComponent(name)}/docs`);
}
export async function getWorkspaceDoc(name, filename) {
    return request(`/api/workspaces/${encodeURIComponent(name)}/docs/${encodeURIComponent(filename)}`);
}
export function workspaceDownloadUrl(name) {
    return `/api/workspaces/${encodeURIComponent(name)}/download`;
}
//# sourceMappingURL=api.js.map