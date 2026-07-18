/** Inject server-sanitized HTML only. */
export function setDocHtml(container, html) {
    container.innerHTML = html || "";
}
export function clearDoc(container, message) {
    container.textContent = message;
}
//# sourceMappingURL=markdown.js.map