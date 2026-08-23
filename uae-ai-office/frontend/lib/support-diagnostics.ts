import type { SupportDiagnosticsInput } from "./types";

// Mirrors the backend's explicit allowlist (app.modules.support.diagnostics) --
// only ever a handful of bounded, inherently-safe fields. Never reads
// anything from storage, cookies, or the auth token.
export function collectDiagnostics(extra?: {
  documentId?: string;
  projectId?: string;
}): SupportDiagnosticsInput {
  const diagnostics: SupportDiagnosticsInput = {};

  if (typeof window !== "undefined") {
    diagnostics.page = window.location.pathname;
  }
  if (typeof navigator !== "undefined" && navigator.userAgent) {
    diagnostics.user_agent_summary = navigator.userAgent.slice(0, 200);
  }
  if (extra?.documentId) diagnostics.document_id = extra.documentId;
  if (extra?.projectId) diagnostics.project_id = extra.projectId;

  return diagnostics;
}

