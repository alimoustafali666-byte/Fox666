import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { BriefItemCategory } from "@/lib/types";

// Returns translation KEYS, never display text -- this module has no
// access to the active locale (it isn't a component), so the caller
// resolves labelKey/descriptionKey through useTranslation()'s t().

export const CATEGORY_ORDER: BriefItemCategory[] = [
  "new_information",
  "pending_action",
  "follow_up",
  "potential_issue",
];

export const CATEGORY_LABEL_KEYS: Record<BriefItemCategory, TranslationKey> = {
  new_information: "brief.categories.new_information.label",
  pending_action: "brief.categories.pending_action.label",
  follow_up: "brief.categories.follow_up.label",
  potential_issue: "brief.categories.potential_issue.label",
};

export const CATEGORY_DESCRIPTION_KEYS: Record<BriefItemCategory, TranslationKey> = {
  new_information: "brief.categories.new_information.description",
  pending_action: "brief.categories.pending_action.description",
  follow_up: "brief.categories.follow_up.description",
  potential_issue: "brief.categories.potential_issue.description",
};

export const CATEGORY_TONE: Record<BriefItemCategory, BadgeTone> = {
  new_information: "info",
  pending_action: "warning",
  follow_up: "primary",
  potential_issue: "danger",
};

// priority: 1 = highest, 3 = lowest (see backend brief_orchestrator's
// 1 <= priority <= 3 validation).
export const PRIORITY_LABEL_KEYS: Record<number, TranslationKey> = {
  1: "brief.priorities.high",
  2: "brief.priorities.medium",
  3: "brief.priorities.low",
};

export const PRIORITY_TONE: Record<number, BadgeTone> = {
  1: "danger",
  2: "warning",
  3: "neutral",
};

