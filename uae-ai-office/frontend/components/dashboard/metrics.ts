// Pure derivations over data the existing /v1 API already returns.
//
// Rule for this module: every number it produces must be traceable to a real
// field on a real response. Where the backend has no source for a metric the
// function returns `null` so the UI can render a neutral empty state instead
// of inventing a value.
import type {
  CollaborationNotificationPublic,
  DailyBriefSummary,
  DashboardSummaryResponse,
  ProjectPublic,
  SupportTicketPublic,
  TaskPublic,
} from "@/lib/types";

const DAY_MS = 86_400_000;

/** Bundle of everything the dashboard loads. `null` means "not available". */
export interface DashboardData {
  summary: DashboardSummaryResponse | null;
  tasks: TaskPublic[] | null;
  projects: ProjectPublic[] | null;
  notifications: CollaborationNotificationPublic[] | null;
  briefs: DailyBriefSummary[] | null;
  briefsCapped: boolean;
  tickets: SupportTicketPublic[] | null;
}

export const TREND_DAYS = 14;

function utcDayKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function parseDay(value: string): string | null {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : utcDayKey(parsed.getTime());
}

/** Counts per UTC day for the last `days` days, oldest bucket first. */
export function dailyCounts(values: (string | null | undefined)[], days = TREND_DAYS): number[] {
  const buckets = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    const key = parseDay(value);
    if (key) buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }
  const now = Date.now();
  const series: number[] = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    series.push(buckets.get(utcDayKey(now - i * DAY_MS)) ?? 0);
  }
  return series;
}

const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);

export interface Trend {
  /** Percentage change of the recent half against the previous half. */
  percent: number | null;
  /** Absolute count in the recent half -- used when there is no baseline. */
  recent: number;
  previous: number;
}

export function trendOf(series: number[]): Trend | null {
  if (series.length < 4 || sum(series) === 0) return null;
  const half = Math.floor(series.length / 2);
  const previous = sum(series.slice(0, half));
  const recent = sum(series.slice(half));
  return {
    percent: previous > 0 ? Math.round(((recent - previous) / previous) * 100) : null,
    recent,
    previous,
  };
}

export function countsTotal(counts: Record<string, number> | undefined | null): number {
  return counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
}

export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

// --- Tasks ---------------------------------------------------------------

const OPEN_STATUSES = new Set(["todo", "in_progress", "blocked"]);

export interface TaskMetrics {
  total: number;
  completed: number;
  inProgress: number;
  todo: number;
  blocked: number;
  cancelled: number;
  open: number;
  overdue: number;
  /** Share of due-dated completed tasks that landed on or before the due date. */
  onTimeRate: number | null;
  onTimeSample: number;
  byAssignee: { name: string | null; count: number }[];
  topPriority: TaskPublic[];
  createdSeries: number[];
  completedSeries: number[];
}

const PRIORITY_RANK: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 };

export function taskMetrics(tasks: TaskPublic[] | null): TaskMetrics | null {
  if (!tasks) return null;

  const todayKey = utcDayKey(Date.now());
  let completed = 0;
  let inProgress = 0;
  let todo = 0;
  let blocked = 0;
  let cancelled = 0;
  let overdue = 0;
  let onTimeHits = 0;
  let onTimeSample = 0;
  const assignees = new Map<string | null, number>();

  for (const task of tasks) {
    switch (task.status) {
      case "completed": completed += 1; break;
      case "in_progress": inProgress += 1; break;
      case "todo": todo += 1; break;
      case "blocked": blocked += 1; break;
      case "cancelled": cancelled += 1; break;
    }

    const isOpen = OPEN_STATUSES.has(task.status);
    if (isOpen) {
      const key = task.assignee_name ?? null;
      assignees.set(key, (assignees.get(key) ?? 0) + 1);
      if (task.due_date) {
        const due = parseDay(task.due_date);
        if (due && due < todayKey) overdue += 1;
      }
    }

    // On-time delivery: only measurable where the task actually carries both
    // a due date and a completion timestamp.
    if (task.status === "completed" && task.due_date && task.completed_at) {
      const due = parseDay(task.due_date);
      const done = parseDay(task.completed_at);
      if (due && done) {
        onTimeSample += 1;
        if (done <= due) onTimeHits += 1;
      }
    }
  }

  const byAssignee = [...assignees.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  const topPriority = tasks
    .filter((task) => OPEN_STATUSES.has(task.status))
    .sort((a, b) => {
      const rank = (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9);
      if (rank !== 0) return rank;
      if (a.due_date && b.due_date) return a.due_date.localeCompare(b.due_date);
      if (a.due_date) return -1;
      if (b.due_date) return 1;
      return 0;
    })
    .slice(0, 5);

  return {
    total: tasks.length,
    completed,
    inProgress,
    todo,
    blocked,
    cancelled,
    open: todo + inProgress + blocked,
    overdue,
    onTimeRate: onTimeSample > 0 ? Math.round((onTimeHits / onTimeSample) * 100) : null,
    onTimeSample,
    byAssignee,
    topPriority,
    createdSeries: dailyCounts(tasks.map((task) => task.created_at)),
    completedSeries: dailyCounts(tasks.map((task) => task.completed_at)),
  };
}

export function isOverdue(task: TaskPublic): boolean {
  if (!task.due_date || !OPEN_STATUSES.has(task.status)) return false;
  const due = parseDay(task.due_date);
  return due !== null && due < utcDayKey(Date.now());
}

// --- Support tickets -----------------------------------------------------

export interface ResponseMetric {
  hours: number;
  sample: number;
}

/** Mean created -> resolved time across resolved tickets. */
export function responseTime(tickets: SupportTicketPublic[] | null): ResponseMetric | null {
  if (!tickets) return null;
  let total = 0;
  let sample = 0;
  for (const ticket of tickets) {
    if (!ticket.resolved_at) continue;
    const opened = new Date(ticket.created_at).getTime();
    const closed = new Date(ticket.resolved_at).getTime();
    if (Number.isNaN(opened) || Number.isNaN(closed) || closed < opened) continue;
    total += closed - opened;
    sample += 1;
  }
  if (sample === 0) return null;
  return { hours: Math.round((total / sample / 3_600_000) * 10) / 10, sample };
}

// --- Composite health score ---------------------------------------------

export interface ScoreFactor {
  key: string;
  value: number;
  weight: number;
}

export interface HealthScore {
  score: number;
  factors: ScoreFactor[];
}

/**
 * Weighted mean of the delivery signals that actually have data behind them.
 * Factors with no source are simply left out, and the whole score is null
 * when nothing measurable exists yet.
 */
export function healthScore(input: {
  taskCompletionRate: number | null;
  onTimeRate: number | null;
  overdueShare: number | null;
  documentProcessedRate: number | null;
  projectDeliveryRate: number | null;
}): HealthScore | null {
  const candidates: ScoreFactor[] = [];
  if (input.taskCompletionRate !== null) candidates.push({ key: "tasks", value: input.taskCompletionRate, weight: 0.3 });
  if (input.onTimeRate !== null) candidates.push({ key: "onTime", value: input.onTimeRate, weight: 0.3 });
  if (input.overdueShare !== null) candidates.push({ key: "overdue", value: 100 - input.overdueShare, weight: 0.2 });
  if (input.documentProcessedRate !== null) candidates.push({ key: "documents", value: input.documentProcessedRate, weight: 0.1 });
  if (input.projectDeliveryRate !== null) candidates.push({ key: "projects", value: input.projectDeliveryRate, weight: 0.1 });
  // A single signal -- especially a vacuous one like "0 of 0 tasks overdue"
  // -- is not a business score. Below two real signals the UI shows its
  // "building intelligence" state instead of grading an empty workspace.
  if (candidates.length < 2) return null;

  const weight = candidates.reduce((a, factor) => a + factor.weight, 0);
  const score = candidates.reduce((a, factor) => a + factor.value * factor.weight, 0) / weight;
  return { score: Math.round(score), factors: candidates };
}
