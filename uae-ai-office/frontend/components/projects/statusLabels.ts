import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { ProjectStatus } from "@/lib/types";

// Returns translation KEYS, never display text -- this module has no
// access to the active locale (it isn't a component), so the caller
// resolves the label through useTranslation()'s t().

export const PROJECT_STATUS_KEYS: Record<ProjectStatus, TranslationKey> = {
  planning: "projects.statuses.planning",
  active: "projects.statuses.active",
  on_hold: "projects.statuses.on_hold",
  completed: "projects.statuses.completed",
  cancelled: "projects.statuses.cancelled",
};

export const PROJECT_STATUS_TONE: Record<ProjectStatus, BadgeTone> = {
  planning: "neutral",
  active: "success",
  on_hold: "warning",
  completed: "info",
  cancelled: "danger",
};

