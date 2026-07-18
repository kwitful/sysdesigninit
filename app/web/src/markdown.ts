/** Inject server-sanitized HTML only. */

export function setDocHtml(container: HTMLElement, html: string): void {
  container.innerHTML = html || "";
}

export function setDocRaw(container: HTMLElement, markdown: string): void {
  container.replaceChildren();
  const pre = document.createElement("pre");
  pre.className = "doc-raw";
  pre.textContent = markdown || "";
  container.appendChild(pre);
}

export function clearDoc(container: HTMLElement, message: string): void {
  container.textContent = message;
}
