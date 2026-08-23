import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { TaskPriority, TaskSourceType, TaskStatus } from "@/lib/types";

export const TASK_STATUS_KEYS: Record<TaskStatus, TranslationKey> = {
  todo: "tasks.statuses.todo",
  in_progress: "tasks.statuses.in_progress",
  blocked: "tasks.statuses.blocked",
  completed: "tasks.statuses.completed",
  cancelled: "tasks.statuses.cancelled",
};

export const TASK_STATUS_TONE: Record<TaskStatus, BadgeTone> = {
  todo: "neutral",
  in_progress: "info",
  blocked: "warning",
  completed: "success",
  cancelled: "neutral",
};

export const TASK_PRIORITY_KEYS: Record<TaskPriority, TranslationKey> = {
  low: "tasks.priorities.low",
  normal: "tasks.priorities.normal",
  high: "tasks.priorities.high",
  urgent: "tasks.priorities.urgent",
};

export const TASK_PRIORITY_TONE: Record<TaskPriority, BadgeTone> = {
  low: "neutral",
  normal: "info",
  high: "warning",
  urgent: "danger",
};

export const TASK_SOURCE_KEYS: Record<TaskSourceType, TranslationKey> = {
  manual: "tasks.sources.manual",
  document: "tasks.sources.document",
  message: "tasks.sources.message",
  conversation: "tasks.sources.conversation",
  daily_brief: "tasks.sources.daily_brief",
  ai_suggestion: "tasks.sources.ai_suggestion",
};

