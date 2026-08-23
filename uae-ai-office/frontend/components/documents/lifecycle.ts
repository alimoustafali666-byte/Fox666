import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { DocumentPublic, DocumentType } from "@/lib/types";

// The backend has no background worker (Steps 1-12): a document moves
// through this lifecycle only when a user explicitly triggers each step
// via POST /documents/{id}/process and POST /documents/{id}/index. This
// helper turns the two separate backend lifecycles (status,
// indexing_status) into the single Uploaded -> Processing -> Processed
// -> Indexing -> Ready progression shown in the UI.
//
// Returns translation KEYS, never display text -- this module has no
// access to the active locale (it isn't a component), so the caller
// resolves labelKey/nextActionLabelKey through useTranslation()'s t().

export type NextAction = "process" | "index" | null;

export interface LifecycleInfo {
  labelKey: TranslationKey;
  tone: BadgeTone;
  nextAction: NextAction;
  nextActionLabelKey: TranslationKey | null;
  errorMessage: string | null;
}

export function getLifecycleInfo(doc: DocumentPublic): LifecycleInfo {
  if (doc.status === "failed") {
    return {
      labelKey: "documents.lifecycle.processingFailed",
      tone: "danger",
      nextAction: "process",
      nextActionLabelKey: "documents.lifecycle.retryProcessing",
      errorMessage: doc.processing_error_message,
    };
  }

  if (doc.status === "uploaded") {
    return {
      labelKey: "documents.lifecycle.uploaded",
      tone: "neutral",
      nextAction: "process",
      nextActionLabelKey: "documents.lifecycle.process",
      errorMessage: null,
    };
  }

  if (doc.status === "processing") {
    return {
      labelKey: "documents.lifecycle.processing",
      tone: "info",
      nextAction: null,
      nextActionLabelKey: null,
      errorMessage: null,
    };
  }

  // status === "processed" from here -- indexing_status decides the rest
  if (doc.indexing_status === "failed") {
    return {
      labelKey: "documents.lifecycle.indexingFailed",
      tone: "danger",
      nextAction: "index",
      nextActionLabelKey: "documents.lifecycle.retryIndexing",
      errorMessage: doc.indexing_error_message,
    };
  }
  if (doc.indexing_status === "indexing") {
    return {
      labelKey: "documents.lifecycle.indexing",
      tone: "info",
      nextAction: null,
      nextActionLabelKey: null,
      errorMessage: null,
    };
  }
  if (doc.indexing_status === "indexed") {
    return { labelKey: "documents.lifecycle.ready", tone: "success", nextAction: null, nextActionLabelKey: null, errorMessage: null };
  }
  // not_indexed
  return {
    labelKey: "documents.lifecycle.processed",
    tone: "info",
    nextAction: "index",
    nextActionLabelKey: "documents.lifecycle.index",
    errorMessage: null,
  };
}

export type LifecycleStepState = "done" | "active" | "pending" | "error";

export interface LifecycleStep {
  key: TranslationKey;
  state: LifecycleStepState;
}

// Same two backend fields as getLifecycleInfo above, but expanded into
// the full 5-stage progression for the visual stepper on the document
// detail page, rather than just "what's the current badge + next
// action". Every stage here is a real, already-observed state -- never
// a projection of what background automation might do next, since none
// exists in this architecture.
export function getLifecycleSteps(doc: DocumentPublic): LifecycleStep[] {
  const processingState: LifecycleStepState =
    doc.status === "processing"
      ? "active"
      : doc.status === "failed"
        ? "error"
        : doc.status === "uploaded"
          ? "pending"
          : "done";

  const processedState: LifecycleStepState = doc.status === "processed" ? "done" : "pending";

  const indexingState: LifecycleStepState =
    doc.status !== "processed"
      ? "pending"
      : doc.indexing_status === "indexing"
        ? "active"
        : doc.indexing_status === "failed"
          ? "error"
          : doc.indexing_status === "indexed"
            ? "done"
            : "pending";

  const readyState: LifecycleStepState = doc.indexing_status === "indexed" ? "done" : "pending";

  return [
    { key: "documents.lifecycle.uploaded", state: "done" },
    { key: "documents.lifecycle.processing", state: processingState },
    { key: "documents.lifecycle.processed", state: processedState },
    { key: "documents.lifecycle.indexing", state: indexingState },
    { key: "documents.lifecycle.ready", state: readyState },
  ];
}

export const DOCUMENT_TYPE_KEYS: Record<DocumentType, TranslationKey> = {
  contract: "documents.types.contract",
  boq: "documents.types.boq",
  quotation: "documents.types.quotation",
  invoice: "documents.types.invoice",
  purchase_order: "documents.types.purchase_order",
  project_report: "documents.types.project_report",
  other: "documents.types.other",
};

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

