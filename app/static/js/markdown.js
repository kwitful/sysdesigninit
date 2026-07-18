/** Inject server-sanitized HTML only. */
export function setDocHtml(container, html) {
    container.innerHTML = html || "";
}
export function setDocRaw(container, markdown) {
    container.replaceChildren();
    const pre = document.createElement("pre");
    pre.className = "doc-raw";
    pre.textContent = markdown || "";
    container.appendChild(pre);
}
export function clearDoc(container, message) {
    container.textContent = message;
}
//# sourceMappingURL=markdown.js.map