import type { AppState, Phase } from "./state.js";
import { isBusy } from "./state.js";

/** UI journey step derived from phase + data (not a backend enum). */
export type Journey = "clarify" | "generate" | "review" | "history";

export function deriveJourney(
  state: Pick<
    AppState,
    | "phase"
    | "workspace"
    | "docsCount"
    | "docsTotal"
    | "browsingWorkspace"
    | "journeyOverride"
    | "forceHistory"
  >
): Journey {
  if (state.browsingWorkspace || state.forceHistory) {
    return "history";
  }
  if (state.journeyOverride) {
    return state.journeyOverride;
  }

  const phase: Phase = state.phase;
  const allReady = state.docsTotal > 0 && state.docsCount >= state.docsTotal;

  if (phase === "complete" || allReady) {
    return "review";
  }

  if (phase === "generating") {
    return "generate";
  }

  if (isBusy(phase) && state.workspace) {
    return "generate";
  }

  if (state.docsCount > 0 && !allReady) {
    return "generate";
  }

  return "clarify";
}

export function formatElapsed(ms: number | null): string {
  if (ms == null) return "";
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function statusLineText(state: AppState, journey: Journey): string {
  if (state.error) {
    return state.error;
  }
  if (journey === "history") {
    if (state.browsingWorkspace) {
      return "Viewing past design (read-only).";
    }
    return "Browse past designs — select one to open.";
  }
  if (state.statusMessage === "Cancelled") {
    return "Cancelled — partial documents may remain on disk.";
  }

  switch (journey) {
    case "clarify":
      if (state.phase === "thinking") {
        return "Clarifying scope…";
      }
      return "Describe what to design — include product, scale, and interview / mvp / production.";
    case "generate": {
      const parts = [
        `Writing documents — ${state.docsCount}/${state.docsTotal}`,
      ];
      if (state.currentStep?.label) {
        parts.push(state.currentStep.label);
      }
      const elapsed = formatElapsed(state.elapsedMs);
      if (elapsed) parts.push(elapsed);
      return parts.join(" · ");
    }
    case "review":
      return "Done — start with Problem brief, then Review.";
    default:
      return "";
  }
}

export function systemBanner(
  state: AppState,
  journey: Journey
): { kind: "error" | "status" | "overwrite" | "browse"; text: string } | null {
  if (state.browsingWorkspace) {
    return {
      kind: "browse",
      text: "Viewing a past design (read-only).",
    };
  }
  if (state.error) {
    return { kind: "error", text: state.error };
  }
  if (state.statusMessage === "Cancelled") {
    return {
      kind: "status",
      text: "Cancelled — partial documents may remain on disk.",
    };
  }
  if (state.overwriteWarning && state.workspace) {
    return {
      kind: "overwrite",
      text: `A design named “${state.workspace}” already exists — new files will replace existing ones.`,
    };
  }
  if (state.statusMessage) {
    return { kind: "status", text: state.statusMessage };
  }
  void journey;
  return null;
}
