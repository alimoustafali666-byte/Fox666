"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation, formatDate, formatDateTime, type TranslationKey } from "@/lib/i18n";
import type { DailyBriefPublic, ProjectStatus, TaskStatus } from "@/lib/types";
import { PROJECT_STATUS_KEYS } from "@/components/projects/statusLabels";
import { TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import {
  AskIcon,
  BoltIcon,
  BrainIcon,
  ClockIcon,
  DocumentsIcon,
  GaugeIcon,
  ShieldIcon,
  ProjectsIcon,
  PulseIcon,
  ReportsIcon,
  SparkIcon,
  StarIcon,
  TargetIcon,
  TasksIcon,
  TrendDownIcon,
  TrendUpIcon,
  UploadIcon,
} from "@/components/layout/icons";
import {
  AnalyticsInitCanvas,
  AreaChart,
  Meter,
  MeterAwaiting,
  ProgressRing,
  PulseOrb,
  RowsSkeleton,
  Sparkline,
} from "./charts";
import { PulseWave } from "./PulseWave";
import {
  countsTotal,
  dailyCounts,
  healthScore,
  percent,
  responseTime,
  taskMetrics,
  trendOf,
  TREND_DAYS,
  type DashboardData,
  type Trend,
} from "./metrics";
import styles from "./DashboardOverview.module.css";

type Tone = "blue" | "green" | "violet" | "amber";

const TONE_STROKE: Record<Tone, [string, string]> = {
  blue: ["#35d9f2", "#4d8dff"],
  green: ["#2fd48a", "#7ef0b6"],
  violet: ["#8b6bff", "#e05ad0"],
  amber: ["#ffa43d", "#ff7a5c"],
};

const PROJECT_STATUS_COLOR: Record<ProjectStatus, [string, string]> = {
  completed: ["#2fd48a", "#7ef0b6"],
  active: ["#3b82f6", "#35d9f2"],
  on_hold: ["#ffa43d", "#ffcb7d"],
  planning: ["#8b6bff", "#c0a8ff"],
  cancelled: ["#6b7c96", "#94a3b8"],
};

const TASK_STATUS_COLOR: Record<TaskStatus, [string, string]> = {
  completed: ["#2fd48a", "#7ef0b6"],
  in_progress: ["#3b82f6", "#35d9f2"],
  blocked: ["#ffa43d", "#ffcb7d"],
  todo: ["#8b6bff", "#c0a8ff"],
  cancelled: ["#6b7c96", "#94a3b8"],
};

// Display order follows the master design: delivered first, then in flight.
// Only the statuses this application actually has -- nothing invented to
// match the screenshot's wording.
const PROJECT_ORDER: ProjectStatus[] = ["completed", "active", "on_hold", "planning", "cancelled"];
const TASK_ORDER: TaskStatus[] = ["completed", "in_progress", "blocked", "todo", "cancelled"];

const EM_DASH = "—";
const EMPTY_SERIES: number[] = new Array(TREND_DAYS).fill(0);

type Translate = (key: TranslationKey, params?: Record<string, string | number>) => string;

// -- building blocks ----------------------------------------------------

function Panel({
  children,
  className,
  title,
  action,
  icon,
}: {
  children: ReactNode;
  className?: string;
  title: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <section className={className ? `${styles.panel} ${className}` : styles.panel}>
      <header className={styles.panelHead}>
        {icon ? <span className={styles.panelIcon}>{icon}</span> : null}
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

/**
 * Designed zero-data state. The visual is fixed decoration (a spectrum ring or
 * an initialization canvas) -- it never encodes a number -- and it is always
 * paired with copy that says what is missing plus, where useful, the action
 * that would fill it.
 */
function PanelEmpty({
  visual,
  text,
  ctaLabel,
  ctaHref,
}: {
  visual: ReactNode;
  text: string;
  ctaLabel?: string;
  ctaHref?: string;
}) {
  return (
    <div className={styles.emptyState}>
      {visual}
      <p>{text}</p>
      {ctaLabel && ctaHref ? (
        <Link href={ctaHref} className={styles.emptyCta}>
          {ctaLabel}
        </Link>
      ) : null}
    </div>
  );
}

/** Compact readiness gauge -- derived from what the app actually returned. */
function ReadinessTile({
  label,
  have,
  total,
  detail,
  from,
  to,
  icon,
}: {
  label: string;
  have: number;
  total: number;
  detail: string;
  from: string;
  to: string;
  icon: ReactNode;
}) {
  const share = total > 0 ? Math.round((have / total) * 100) : 0;
  return (
    <div className={styles.readyTile} data-state={share >= 100 ? "ready" : share > 0 ? "partial" : "waiting"}>
      <span className={styles.readyIcon}>{icon}</span>
      <span className={styles.readyBody}>
        <span className={styles.readyTop}>
          <span className={styles.readyLabel}>{label}</span>
          <strong>
            {have}
            <em>/{total}</em>
          </strong>
        </span>
        <Meter value={share} from={from} to={to} />
        <span className={styles.readyDetail}>{detail}</span>
      </span>
    </div>
  );
}

function Delta({ trend, t }: { trend: Trend | null; t: Translate }) {
  // The KPI chip already carries the awaiting-trend state; no duplicate line.
  if (!trend) return null;
  if (trend.percent === null) {
    return (
      <span className={styles.delta} data-dir="up">
        <TrendUpIcon width={12} height={12} />
        +{trend.recent}
        <em>{t("dashboard.v2.kpi.newLabel")}</em>
      </span>
    );
  }
  const up = trend.percent >= 0;
  return (
    <span className={styles.delta} data-dir={up ? "up" : "down"}>
      {up ? <TrendUpIcon width={12} height={12} /> : <TrendDownIcon width={12} height={12} />}
      {up ? "+" : ""}
      {trend.percent}%<em>{t("dashboard.v2.master.vsLast7")}</em>
    </span>
  );
}

function KpiCard({
  tone,
  icon,
  label,
  caption,
  value,
  series,
  trend,
  t,
}: {
  tone: Tone;
  icon: ReactNode;
  label: string;
  caption: string;
  value: string;
  series: number[] | null;
  trend: Trend | null;
  t: Translate;
}) {
  const [from, to] = TONE_STROKE[tone];
  const hasSeries = Boolean(series && series.some((point) => point > 0));
  return (
    <article className={styles.kpi} data-tone={tone}>
      <span className={styles.kpiBloom} aria-hidden="true" />
      <div className={styles.kpiHead}>
        <span className={styles.kpiIcon}>{icon}</span>
        <span className={styles.kpiTitles}>
          <span className={styles.kpiLabel}>{label}</span>
          <span className={styles.kpiCaption}>{caption}</span>
        </span>
      </div>
      <div className={styles.kpiBody}>
        <div className={styles.kpiFigures}>
          <strong className={styles.kpiValue}>{value}</strong>
          <Delta trend={trend} t={t} />
        </div>
        <div className={styles.kpiChart}>
          <Sparkline values={series ?? EMPTY_SERIES} from={from} to={to} />
        </div>
      </div>
      <span className={styles.kpiChip} data-state={hasSeries ? "live" : "waiting"}>
        <i />
        {hasSeries ? t("dashboard.v2.live") : t("dashboard.v2.enrich.awaitingTrend")}
      </span>
    </article>
  );
}

function StatusLegend({
  rows,
}: {
  rows: { color: string; label: string; value: number; share: number }[];
}) {
  return (
    <ul className={styles.legend}>
      {rows.map((row) => (
        <li key={row.label}>
          <i style={{ background: row.color }} />
          <span>{row.label}</span>
          <strong>{row.value}</strong>
          <em>{row.share}%</em>
        </li>
      ))}
    </ul>
  );
}

function StatusRow({ label, state, detail }: { label: string; state: "ok" | "warn" | "off"; detail: string }) {
  return (
    <li className={styles.statusRow} data-state={state}>
      <i />
      <span>{label}</span>
      <strong>{detail}</strong>
    </li>
  );
}

function PerfRow({
  icon,
  accent,
  label,
  value,
  meter,
  from,
  to,
  note,
}: {
  icon: ReactNode;
  accent: string;
  label: string;
  value: string | null;
  meter: number | null;
  from: string;
  to: string;
  note: string;
}) {
  return (
    <li className={styles.perfRow}>
      <span className={styles.perfIcon} data-accent={accent}>
        {icon}
      </span>
      <span className={styles.perfMain}>
        <span className={styles.perfTop}>
          <span className={styles.perfLabel}>{label}</span>
          <strong className={styles.perfValue} data-empty={value ? undefined : "true"}>
            {value ?? EM_DASH}
          </strong>
        </span>
        {meter !== null ? <Meter value={meter} from={from} to={to} /> : <MeterAwaiting />}
        <span className={styles.perfNote}>{note}</span>
      </span>
    </li>
  );
}

// -- dashboard ----------------------------------------------------------

export function DashboardOverview({
  data,
  brief,
  loading,
  canRegenerate,
  regenerating,
  onRegenerate,
}: {
  data: DashboardData;
  brief: DailyBriefPublic | null;
  loading: boolean;
  canRegenerate: boolean;
  regenerating: boolean;
  onRegenerate: () => void;
}) {
  const { user } = useAuth();
  const { t, locale } = useTranslation();

  const { summary, projects, notifications, briefs, briefsCapped, tickets } = data;
  const tasks = taskMetrics(data.tasks);

  // -- portfolio --
  const projectCounts = summary?.project_status_counts ?? null;
  const totalProjects = countsTotal(projectCounts);
  const projectRows = projectCounts
    ? PROJECT_ORDER.filter((status) => (projectCounts[status] ?? 0) > 0).map((status) => ({
        status,
        count: projectCounts[status] ?? 0,
      }))
    : [];
  const projectProgress = percent(projectCounts?.completed ?? 0, totalProjects);

  // -- documents --
  const documentCounts = summary?.document_status_counts ?? null;
  const totalDocuments = countsTotal(documentCounts);
  const processedDocuments = documentCounts?.processed ?? 0;
  const failedDocuments = documentCounts?.failed ?? 0;
  const pendingDocuments = (documentCounts?.uploaded ?? 0) + (documentCounts?.processing ?? 0);
  const documentRate = totalDocuments > 0 ? percent(processedDocuments, totalDocuments) : null;

  // -- tasks --
  function taskCount(status: TaskStatus): number {
    if (!tasks) return 0;
    switch (status) {
      case "completed": return tasks.completed;
      case "in_progress": return tasks.inProgress;
      case "blocked": return tasks.blocked;
      case "todo": return tasks.todo;
      case "cancelled": return tasks.cancelled;
    }
  }

  const taskRows = tasks
    ? TASK_ORDER.filter((status) => taskCount(status) > 0).map((status) => ({ status, count: taskCount(status) }))
    : [];

  // Short record lists for the foot of the two ring panels. Both are simple
  // orderings of arrays the page already loaded -- no extra request, no
  // derived figure, and nothing shown that is not a real record.
  const recentProjects = projects
    ? [...projects].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 4)
    : [];
  const nextTasks = data.tasks
    ? data.tasks
        .filter((task) => task.status !== "completed" && task.status !== "cancelled")
        .sort((a, b) => {
          if (a.due_date && b.due_date) return a.due_date.localeCompare(b.due_date);
          if (a.due_date) return -1;
          if (b.due_date) return 1;
          return b.updated_at.localeCompare(a.updated_at);
        })
        .slice(0, 4)
    : [];

  // -- real 14-day series --
  const projectSeries = projects ? dailyCounts(projects.map((project) => project.created_at)) : null;
  const notificationSeries = notifications ? dailyCounts(notifications.map((entry) => entry.created_at)) : null;
  const briefSeries = briefs ? dailyCounts(briefs.map((entry) => entry.brief_date)) : null;

  // -- performance --
  const response = responseTime(tickets);
  // Only measurable once there is open work; "0 of 0 overdue" is not a 100%.
  const overdueShare = tasks && tasks.open > 0 ? percent(tasks.overdue, tasks.open) : null;
  const taskCompletionRate = tasks && tasks.total > 0 ? percent(tasks.completed, tasks.total) : null;
  const health = healthScore({
    taskCompletionRate,
    onTimeRate: tasks?.onTimeRate ?? null,
    overdueShare,
    documentProcessedRate: documentRate,
    projectDeliveryRate: totalProjects > 0 ? projectProgress : null,
  });

  const goodSignals = health ? health.factors.filter((factor) => factor.value >= 70).length : 0;
  const grade = health
    ? health.score >= 85
      ? t("dashboard.v2.master.pulse.excellent")
      : health.score >= 70
        ? t("dashboard.v2.master.pulse.strong")
        : health.score >= 50
          ? t("dashboard.v2.master.pulse.steady")
          : t("dashboard.v2.master.pulse.attention")
    : null;

  const sortedFactors = health ? [...health.factors].sort((a, b) => a.value - b.value) : [];
  const weakest = sortedFactors[0] ?? null;
  const strongest = sortedFactors[sortedFactors.length - 1] ?? null;

  function pickRecommendation(): { text: string; href: string; tone: string } | null {
    if (tasks && tasks.overdue > 0)
      return { text: t("dashboard.v2.rec.overdue", { count: tasks.overdue }), href: "/tasks", tone: "rose" };
    if (failedDocuments > 0)
      return { text: t("dashboard.v2.rec.failedDocs", { count: failedDocuments }), href: "/documents", tone: "rose" };
    if (tasks && tasks.blocked > 0)
      return { text: t("dashboard.v2.rec.blocked", { count: tasks.blocked }), href: "/tasks", tone: "amber" };
    if (summary && summary.my_tasks.high_priority_open > 0)
      return {
        text: t("dashboard.v2.rec.highPriority", { count: summary.my_tasks.high_priority_open }),
        href: "/tasks",
        tone: "amber",
      };
    if (summary && !summary.latest_brief)
      return { text: t("dashboard.v2.rec.brief"), href: "/brief", tone: "violet" };
    if (pendingDocuments > 0)
      return { text: t("dashboard.v2.rec.pendingDocs", { count: pendingDocuments }), href: "/documents", tone: "blue" };
    if (summary && summary.unread_notifications > 0)
      return {
        text: t("dashboard.v2.rec.notifications", { count: summary.unread_notifications }),
        href: "/messages/notifications",
        tone: "magenta",
      };
    if (projectCounts && (projectCounts.planning ?? 0) > 0)
      return { text: t("dashboard.v2.rec.planning", { count: projectCounts.planning }), href: "/projects", tone: "cyan" };
    if (health) return { text: t("dashboard.v2.rec.clear"), href: "/projects", tone: "green" };
    return null;
  }

  const recommendation = pickRecommendation();

  const firstName = user?.full_name?.split(" ")[0] || user?.email || "";
  const hour = new Date().getHours();
  const greetingKey: TranslationKey =
    hour < 12
      ? "dashboard.v2.greetingMorning"
      : hour < 18
        ? "dashboard.v2.greetingAfternoon"
        : "dashboard.v2.greetingEvening";

  // How many of the five scoring inputs actually have data behind them.
  const signalsAvailable = [
    taskCompletionRate,
    tasks?.onTimeRate ?? null,
    overdueShare,
    documentRate,
    totalProjects > 0 ? projectProgress : null,
  ].filter((value) => value !== null).length;

  const activity = summary?.recent_activity ?? null;

  // Readiness is availability, not performance: which sources answered, and
  // which content types exist. Nothing here is a business metric.
  const sourcesUp = [summary, data.tasks, projects, notifications, briefs, tickets].filter(
    (source) => source !== null,
  ).length;
  const contentReady = [totalProjects > 0, (tasks?.total ?? 0) > 0, totalDocuments > 0, (briefs?.length ?? 0) > 0].filter(
    Boolean,
  ).length;
  const activityReady = (activity?.length ?? 0) > 0 || (notifications?.length ?? 0) > 0 ? 1 : 0;
  const hasAnalytics = Boolean(
    (projectSeries && projectSeries.some((point) => point > 0)) ||
      (tasks && tasks.completedSeries.some((point) => point > 0)) ||
      (briefSeries && briefSeries.some((point) => point > 0)),
  );
  const blankSeries = new Array(TREND_DAYS).fill(0) as number[];

  return (
    <div className={styles.overview}>
      {/* Greeting band */}
      <header className={styles.hero}>
        <PulseWave className={styles.wave} />
        <div className={styles.heroText}>
          {/* No emoji: it renders as a missing glyph wherever the emoji font
              is absent, and the band reads as an executive header without it. */}
          <h1>{t(greetingKey, { name: firstName })}</h1>
          <p>{t("dashboard.subtitle")}</p>
          <div className={styles.quickActions}>
            <Link href="/projects" data-accent="violet">
              <ProjectsIcon width={13} height={13} />
              {t("dashboard.v2.actions.newProject")}
            </Link>
            <Link href="/documents" data-accent="blue">
              <UploadIcon width={13} height={13} />
              {t("dashboard.uploadDocument")}
            </Link>
            <Link href="/tasks" data-accent="green">
              <TasksIcon width={13} height={13} />
              {t("dashboard.v2.actions.assignTask")}
            </Link>
            <Link href="/reports" data-accent="amber">
              <ReportsIcon width={13} height={13} />
              {t("dashboard.v2.actions.generateReport")}
            </Link>
          </div>
        </div>
        <div className={styles.heroSide}>
          <span className={styles.pulse} data-loading={loading ? "true" : undefined}>
            <i />
            {loading ? t("dashboard.v2.syncing") : t("dashboard.v2.live")}
          </span>
          <span className={styles.briefState}>
            {brief ? t("dashboard.todaysBrief") : loading ? t("dashboard.loadingBrief") : t("dashboard.noBriefMember")}
          </span>
          {canRegenerate ? (
            <button type="button" className={styles.briefButton} onClick={onRegenerate} disabled={regenerating}>
              <SparkIcon width={14} height={14} />
              {regenerating
                ? t("dashboard.generating")
                : brief
                  ? t("dashboard.regenerate")
                  : t("dashboard.generateBrief")}
            </button>
          ) : null}
        </div>
      </header>

      {/* KPI row */}
      <div className={styles.kpiGrid}>
        <KpiCard
          tone="blue"
          icon={<ProjectsIcon width={16} height={16} />}
          label={t("dashboard.v2.kpi.projects")}
          caption={t("dashboard.v2.kpi.projectsCaption")}
          value={summary ? String(totalProjects) : EM_DASH}
          series={projectSeries}
          trend={projectSeries ? trendOf(projectSeries) : null}
          t={t}
        />
        <KpiCard
          tone="green"
          icon={<TasksIcon width={16} height={16} />}
          label={t("dashboard.v2.kpi.tasksCompleted")}
          caption={t("dashboard.v2.kpi.tasksCompletedCaption")}
          value={tasks ? String(tasks.completed) : EM_DASH}
          series={tasks?.completedSeries ?? null}
          trend={tasks ? trendOf(tasks.completedSeries) : null}
          t={t}
        />
        <KpiCard
          tone="violet"
          icon={<AskIcon width={16} height={16} />}
          label={t("dashboard.v2.kpi.messages")}
          caption={t("dashboard.v2.kpi.messagesCaption")}
          value={summary ? String(summary.unread_notifications) : EM_DASH}
          series={notificationSeries}
          trend={notificationSeries ? trendOf(notificationSeries) : null}
          t={t}
        />
        <KpiCard
          tone="amber"
          icon={<ReportsIcon width={16} height={16} />}
          label={t("dashboard.v2.kpi.reports")}
          caption={t("dashboard.v2.kpi.reportsCaption")}
          value={briefs ? `${briefs.length}${briefsCapped ? "+" : ""}` : EM_DASH}
          series={briefSeries}
          trend={briefSeries ? trendOf(briefSeries) : null}
          t={t}
        />
      </div>

      {/* Intelligence row */}
      <div className={styles.grid}>
        <Panel
          className={styles.spanThree}
          title={t("dashboard.v2.master.pulse.title")}
          icon={<PulseIcon width={16} height={16} />}
        >
          <div className={styles.pulseRow}>
            <PulseOrb
              size={132}
              score={health ? health.score : null}
              centerValue={health ? String(health.score) : t("dashboard.v2.enrich.building")}
              centerLabel={health ? t("dashboard.v2.master.pulse.score") : t("dashboard.v2.enrich.signals", { have: signalsAvailable, need: 2 })}
            />
            <div className={styles.pulseText}>
              {health && grade ? (
                <>
                  <span className={styles.pulseHeadline}>{t("dashboard.v2.master.pulse.headline")}</span>
                  <strong className={styles.pulseGrade}>{grade}</strong>
                  <p>{t("dashboard.v2.master.pulse.body", { good: goodSignals, total: health.factors.length })}</p>
                  <Link href="/reports" className={styles.pulseLink}>
                    {t("dashboard.v2.master.pulse.viewFull")}
                  </Link>
                </>
              ) : (
                <>
                  <strong className={styles.pulseGrade}>{t("dashboard.v2.enrich.building")}</strong>
                  <p>{t("dashboard.v2.master.pulse.buildingBody")}</p>
                  <Link href="/projects" className={styles.pulseLink}>
                    {t("dashboard.v2.actions.newProject")}
                  </Link>
                </>
              )}
            </div>
          </div>
        </Panel>

        <Panel className={styles.spanThree} title={t("dashboard.v2.master.performanceTitle")}>
          {tasks || response ? (
            <ul className={styles.perfList}>
              <PerfRow
                icon={<TargetIcon width={14} height={14} />}
                accent="green"
                label={t("dashboard.v2.performance.onTime")}
                value={tasks && tasks.onTimeRate !== null ? `${tasks.onTimeRate}%` : null}
                meter={tasks && tasks.onTimeRate !== null ? tasks.onTimeRate : null}
                from="#2fd48a"
                to="#7ef0b6"
                note={
                  tasks && tasks.onTimeRate !== null
                    ? t("dashboard.v2.performance.sample", { count: tasks.onTimeSample })
                    : t("dashboard.v2.master.awaiting")
                }
              />
              <PerfRow
                icon={<ClockIcon width={14} height={14} />}
                accent="blue"
                label={t("dashboard.v2.performance.responseTime")}
                value={
                  response
                    ? response.hours >= 48
                      ? t("dashboard.v2.performance.days", { value: Math.round(response.hours / 24) })
                      : t("dashboard.v2.performance.hours", { value: response.hours })
                    : null
                }
                meter={response ? Math.max(4, 100 - Math.min(100, response.hours)) : null}
                from="#3b82f6"
                to="#35d9f2"
                note={
                  response
                    ? t("dashboard.v2.performance.sample", { count: response.sample })
                    : t("dashboard.v2.master.awaiting")
                }
              />
              <PerfRow
                icon={<GaugeIcon width={14} height={14} />}
                accent="violet"
                label={t("dashboard.v2.performance.quality")}
                value={null}
                meter={null}
                from="#8b6bff"
                to="#c0a8ff"
                note={t("dashboard.v2.noSource")}
              />
              <PerfRow
                icon={<StarIcon width={14} height={14} />}
                accent="amber"
                label={t("dashboard.v2.performance.satisfaction")}
                value={null}
                meter={null}
                from="#ffa43d"
                to="#ffcb7d"
                note={t("dashboard.v2.noSource")}
              />
            </ul>
          ) : (
            <PanelEmpty visual={<RowsSkeleton />} text={t("dashboard.v2.master.emptyPerformance")} />
          )}
        </Panel>

        <Panel
          className={styles.spanThree}
          title={t("dashboard.v2.master.projectsTitle")}
          action={<Link href="/projects" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
        >
          {totalProjects > 0 ? (
            <div className={styles.ringRow}>
              <ProgressRing
                size={140}
                segments={projectRows.map((row) => ({
                  value: row.count,
                  from: PROJECT_STATUS_COLOR[row.status][0],
                  to: PROJECT_STATUS_COLOR[row.status][1],
                }))}
                centerValue={String(totalProjects)}
                centerLabel={t("dashboard.v2.kpi.projects")}
              />
              <StatusLegend
                rows={projectRows.map((row) => ({
                  color: PROJECT_STATUS_COLOR[row.status][0],
                  label: t(PROJECT_STATUS_KEYS[row.status]),
                  value: row.count,
                  share: percent(row.count, totalProjects),
                }))}
              />
              {recentProjects.length > 0 ? (
                <div className={styles.ringList}>
                  {recentProjects.map((project) => (
                    <Link key={project.id} href={`/projects/${project.id}`} className={styles.ringListRow}>
                      <i style={{ ["--row-color" as string]: PROJECT_STATUS_COLOR[project.status][0] }} />
                      <span>{project.name}</span>
                      <em>{t(PROJECT_STATUS_KEYS[project.status])}</em>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <PanelEmpty
              visual={
                <ProgressRing
                  size={132}
                  empty
                  segments={[]}
                  centerValue="0"
                  centerLabel={t("dashboard.v2.enrich.zeroProjects")}
                />
              }
              text={t("dashboard.v2.enrich.projectsGuidance")}
              ctaLabel={t("dashboard.v2.actions.newProject")}
              ctaHref="/projects"
            />
          )}
        </Panel>

        <div className={`${styles.spanThree} ${styles.intelStack}`}>
          <section className={`${styles.panel} ${styles.insightPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="violet">
                <BrainIcon width={16} height={16} />
              </span>
              <h2>{t("dashboard.v2.master.insights.title")}</h2>
            </header>
            {health && strongest && weakest ? (
              <div className={styles.insightBody}>
                <span className={styles.insightGlyph} aria-hidden="true">
                  <BrainIcon width={24} height={24} />
                </span>
                <p>
                  {weakest.value < 70
                    ? t("dashboard.v2.master.insights.weakest", {
                        metric: factorLabel(weakest.key, t),
                        value: Math.round(weakest.value),
                      })
                    : t("dashboard.v2.master.insights.strongest", {
                        metric: factorLabel(strongest.key, t),
                        value: Math.round(strongest.value),
                      })}
                </p>
                <Link href="/reports" className={styles.insightLink}>
                  {t("dashboard.v2.master.insights.view")}
                </Link>
              </div>
            ) : (
              <div className={styles.insightBody}>
                <span className={styles.insightGlyph} aria-hidden="true">
                  <BrainIcon width={24} height={24} />
                </span>
                <p>{t("dashboard.v2.enrich.aiWaiting")}</p>
                <Link href="/projects" className={styles.insightLink}>
                  {t("dashboard.v2.actions.newProject")}
                </Link>
              </div>
            )}
          </section>

          <section className={`${styles.panel} ${styles.recPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="cyan">
                <BoltIcon width={16} height={16} />
              </span>
              <h2>{t("dashboard.v2.intel.recommendation")}</h2>
            </header>
            {recommendation ? (
              <div className={styles.recBody} data-tone={recommendation.tone}>
                <span className={styles.recIcon}>
                  <TargetIcon width={15} height={15} />
                </span>
                <p>{recommendation.text}</p>
                <Link href={recommendation.href} className={styles.insightLink}>
                  {t("dashboard.exec.viewAll")}
                </Link>
              </div>
            ) : (
              <p className={styles.softEmpty}>{t("dashboard.v2.intel.recommendationEmpty")}</p>
            )}
          </section>

          <section className={`${styles.panel} ${styles.systemPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="green">
                <ShieldIcon width={16} height={16} />
              </span>
              <h2>{t("dashboard.v2.intel.status")}</h2>
            </header>
            <ul className={styles.statusFeed}>
              <StatusRow
                label={t("dashboard.v2.intel.statusData")}
                state={summary ? "ok" : "off"}
                detail={summary ? t("dashboard.v2.intel.operational") : t("dashboard.v2.intel.unavailable")}
              />
              <StatusRow
                label={t("dashboard.v2.intel.statusDocs")}
                state={!documentCounts ? "off" : failedDocuments > 0 ? "warn" : "ok"}
                detail={
                  !documentCounts
                    ? t("dashboard.v2.intel.unavailable")
                    : failedDocuments > 0
                      ? t("dashboard.v2.intel.attention")
                      : t("dashboard.v2.intel.operational")
                }
              />
              <StatusRow
                label={t("dashboard.v2.intel.statusBrief")}
                state={summary?.latest_brief ? "ok" : "warn"}
                detail={summary?.latest_brief ? t("dashboard.v2.intel.upToDate") : t("dashboard.v2.intel.never")}
              />
              <StatusRow
                label={t("dashboard.v2.intel.statusRealtime")}
                state={notifications ? "ok" : "off"}
                detail={
                  notifications
                    ? notifications.length > 0
                      ? t("dashboard.v2.intel.operational")
                      : t("dashboard.v2.intel.quiet")
                    : t("dashboard.v2.intel.unavailable")
                }
              />
            </ul>
          </section>
        </div>
      </div>

      {/* Analytics row */}
      <div className={styles.grid}>
        <Panel
          className={styles.spanFive}
          title={t("dashboard.v2.master.analyticsTitle")}
          action={
            <div className={styles.chartLegendRow}>
              <span data-series="projects"><i />{t("dashboard.v2.master.analyticsProjects")}</span>
              <span data-series="tasks"><i />{t("dashboard.v2.master.analyticsTasks")}</span>
              <span data-series="reports"><i />{t("dashboard.v2.master.analyticsReports")}</span>
            </div>
          }
        >
          {hasAnalytics ? (
            <AreaChart
              labels={buildDayLabels(locale)}
              series={[
                {
                  values: projectSeries ?? blankSeries,
                  from: "#3b82f6",
                  to: "#35d9f2",
                  label: t("dashboard.v2.master.analyticsProjects"),
                },
                {
                  values: tasks?.completedSeries ?? blankSeries,
                  from: "#2fd48a",
                  to: "#7ef0b6",
                  label: t("dashboard.v2.master.analyticsTasks"),
                },
                {
                  values: briefSeries ?? blankSeries,
                  from: "#8b6bff",
                  to: "#e05ad0",
                  label: t("dashboard.v2.master.analyticsReports"),
                },
              ]}
            />
          ) : (
            <div className={styles.initState}>
              <AnalyticsInitCanvas />
              <div className={styles.initCaption}>
                <span className={styles.initBadge}>
                  <i />
                  {t("dashboard.v2.enrich.analyticsInit")}
                </span>
                <p>{t("dashboard.v2.master.analyticsEmpty")}</p>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          className={styles.spanThree}
          title={t("dashboard.v2.master.tasksTitle")}
          action={<Link href="/tasks" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
        >
          {tasks && tasks.total > 0 ? (
            <div className={styles.ringRow}>
              <ProgressRing
                size={136}
                segments={taskRows.map((row) => ({
                  value: row.count,
                  from: TASK_STATUS_COLOR[row.status][0],
                  to: TASK_STATUS_COLOR[row.status][1],
                }))}
                centerValue={String(tasks.total)}
                centerLabel={t("dashboard.v2.tasksOverview.center")}
              />
              <StatusLegend
                rows={taskRows.map((row) => ({
                  color: TASK_STATUS_COLOR[row.status][0],
                  label: t(TASK_STATUS_KEYS[row.status]),
                  value: row.count,
                  share: percent(row.count, tasks.total),
                }))}
              />
              {nextTasks.length > 0 ? (
                <div className={styles.ringList}>
                  {nextTasks.map((task) => (
                    <Link key={task.id} href={`/tasks/${task.id}`} className={styles.ringListRow}>
                      <i style={{ ["--row-color" as string]: TASK_STATUS_COLOR[task.status][0] }} />
                      <span>{task.title}</span>
                      <em>
                        {task.due_date
                          ? formatDate(locale, task.due_date, { month: "short", day: "numeric" })
                          : t("common.emptyValue")}
                      </em>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <PanelEmpty
              visual={
                <ProgressRing
                  size={132}
                  empty
                  segments={[]}
                  centerValue="0"
                  centerLabel={t("dashboard.v2.enrich.zeroTasks")}
                />
              }
              text={t("dashboard.v2.enrich.tasksGuidance")}
              ctaLabel={t("dashboard.v2.actions.assignTask")}
              ctaHref="/tasks"
            />
          )}
        </Panel>

        <Panel
          className={styles.spanFour}
          title={t("dashboard.v2.master.activityTitle")}
          action={<Link href="/settings/audit-log" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
        >
          {activity && activity.length > 0 ? (
            <ul className={styles.timeline}>
              {activity.slice(0, 5).map((entry, index) => (
                <li key={`${entry.created_at}-${index}`}>
                  <span className={styles.timelineIcon} data-kind={entry.resource_type}>
                    {entry.resource_type === "document" ? (
                      <DocumentsIcon width={14} height={14} />
                    ) : (
                      <TasksIcon width={14} height={14} />
                    )}
                  </span>
                  <span className={styles.timelineBody}>
                    <strong>{entry.action}</strong>
                    <span>{t("dashboard.v2.master.activityBy", { actor: entry.actor })}</span>
                  </span>
                  <time>{formatDateTime(locale, entry.created_at)}</time>
                </li>
              ))}
            </ul>
          ) : notifications && notifications.length > 0 ? (
            <ul className={styles.timeline}>
              {notifications.slice(0, 5).map((entry) => (
                <li key={entry.id}>
                  <span className={styles.timelineIcon} data-unread={entry.read_at ? undefined : "true"}>
                    <AskIcon width={14} height={14} />
                  </span>
                  <span className={styles.timelineBody}>
                    <strong>{entry.title}</strong>
                    {entry.body ? <span>{entry.body}</span> : null}
                  </span>
                  <time>{formatDateTime(locale, entry.created_at)}</time>
                </li>
              ))}
            </ul>
          ) : (
            <PanelEmpty visual={<RowsSkeleton />} text={t("dashboard.v2.master.emptyActivity")} />
          )}
        </Panel>
      </div>

      {/* Readiness strip -- pure availability, derived from what loaded */}
      <section className={`${styles.panel} ${styles.readyPanel}`}>
        <header className={styles.panelHead}>
          <span className={styles.panelIcon} data-accent="cyan">
            <GaugeIcon width={16} height={16} />
          </span>
          <h2>{t("dashboard.v2.enrich.readiness")}</h2>
        </header>
        <div className={styles.readyGrid}>
          <ReadinessTile
            label={t("dashboard.v2.enrich.dataSources")}
            have={sourcesUp}
            total={6}
            detail={sourcesUp === 6 ? t("dashboard.v2.enrich.ready") : t("dashboard.v2.enrich.partial")}
            from="#35d9f2"
            to="#3b82f6"
            icon={<ShieldIcon width={14} height={14} />}
          />
          <ReadinessTile
            label={t("dashboard.v2.enrich.content")}
            have={contentReady}
            total={4}
            detail={contentReady === 0 ? t("dashboard.v2.enrich.waiting") : contentReady === 4 ? t("dashboard.v2.enrich.ready") : t("dashboard.v2.enrich.partial")}
            from="#2fd48a"
            to="#7ef0b6"
            icon={<ProjectsIcon width={14} height={14} />}
          />
          <ReadinessTile
            label={t("dashboard.v2.enrich.aiSignals")}
            have={Math.min(signalsAvailable, 2)}
            total={2}
            detail={signalsAvailable >= 2 ? t("dashboard.v2.enrich.ready") : t("dashboard.v2.enrich.waiting")}
            from="#8b6bff"
            to="#e05ad0"
            icon={<BrainIcon width={14} height={14} />}
          />
          <ReadinessTile
            label={t("dashboard.v2.enrich.activityFeed")}
            have={activityReady}
            total={1}
            detail={activityReady ? t("dashboard.v2.enrich.ready") : t("dashboard.v2.enrich.waiting")}
            from="#ffa43d"
            to="#ff7a5c"
            icon={<PulseIcon width={14} height={14} />}
          />
        </div>
      </section>
    </div>
  );
}

// -- helpers ------------------------------------------------------------

function buildDayLabels(locale: string): string[] {
  const format = new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" });
  const now = Date.now();
  const day = 86_400_000;
  const stride = (TREND_DAYS - 1) / 4;
  return [0, 1, 2, 3, 4].map((i) => format.format(new Date(now - Math.round((TREND_DAYS - 1 - i * stride)) * day)));
}

function factorLabel(key: string, t: Translate): string {
  switch (key) {
    case "tasks": return t("dashboard.v2.growth.tasksDelivered");
    case "onTime": return t("dashboard.v2.performance.onTime");
    case "overdue": return t("dashboard.v2.tasksOverview.overdue");
    case "documents": return t("dashboard.v2.growth.documents");
    default: return t("dashboard.v2.growth.projectsDelivered");
  }
}
