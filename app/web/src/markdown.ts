/** Inject server-sanitized HTML only. */

export function setDocHtml(container: HTMLElement, html: string): void {
  container.innerHTML = html || "";
}

export function clearDoc(container: HTMLElement, message: string): void {
  container.textContent = message;
}
