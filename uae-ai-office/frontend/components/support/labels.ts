import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { SupportTicketCategory, SupportTicketPriority, SupportTicketStatus } from "@/lib/types";

// Returns translation KEYS, never display text -- same convention as
// components/documents/lifecycle.ts and components/brief/categories.ts.

export const CATEGORY_LABEL_KEYS: Record<SupportTicketCategory, TranslationKey> = {
  getting_started: "support.categories.getting_started",
  account_login: "support.categories.account_login",
  projects: "support.categories.projects",
  documents: "support.categories.documents",
  upload_processing_indexing: "support.categories.upload_processing_indexing",
  ask_your_business: "support.categories.ask_your_business",
  daily_brief: "support.categories.daily_brief",
  language_settings: "support.categories.language_settings",
  roles_permissions: "support.categories.roles_permissions",
  troubleshooting: "support.categories.troubleshooting",
  other: "support.categories.other",
};

export const STATUS_LABEL_KEYS: Record<SupportTicketStatus, TranslationKey> = {
  open: "support.tickets.statuses.open",
  in_progress: "support.tickets.statuses.in_progress",
  waiting_for_user: "support.tickets.statuses.waiting_for_user",
  resolved: "support.tickets.statuses.resolved",
  closed: "support.tickets.statuses.closed",
};

export const STATUS_TONE: Record<SupportTicketStatus, BadgeTone> = {
  open: "info",
  in_progress: "primary",
  waiting_for_user: "warning",
  resolved: "success",
  closed: "neutral",
};

export const PRIORITY_LABEL_KEYS: Record<SupportTicketPriority, TranslationKey> = {
  low: "support.tickets.priorities.low",
  normal: "support.tickets.priorities.normal",
  high: "support.tickets.priorities.high",
  urgent: "support.tickets.priorities.urgent",
};

export const PRIORITY_TONE: Record<SupportTicketPriority, BadgeTone> = {
  low: "neutral",
  normal: "info",
  high: "warning",
  urgent: "danger",
};

