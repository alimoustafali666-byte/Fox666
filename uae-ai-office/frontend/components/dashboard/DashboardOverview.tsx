"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation, formatDateTime, type TranslationKey } from "@/lib/i18n";
import type { DailyBriefPublic, ProjectStatus, TaskPublic } from "@/lib/types";
import { PROJECT_STATUS_KEYS } from "@/components/projects/statusLabels";
import { TASK_PRIORITY_KEYS } from "@/components/tasks/taskLabels";
import {
  AskIcon,
  AuditIcon,
  BriefIcon,
  DocumentsIcon,
  GrowthIcon,
  InsightIcon,
  ProjectsIcon,
  PulseIcon,
  ReportsIcon,
  ShieldIcon,
  SparkIcon,
  TasksIcon,
  TrendDownIcon,
  TrendUpIcon,
  UploadIcon,
} from "@/components/layout/icons";
import { DubaiSkyline } from "@/components/layout/DubaiSkyline";
import { AreaChart, Meter, ProgressRing, Sparkline } from "./charts";
import {
  countsTotal,
  dailyCounts,
  healthScore,
  isOverdue,
  percent,
  responseTime,
  taskMetrics,
  trendOf,
  TREND_DAYS,
  type DashboardData,
  type Trend,
} from "./metrics";
import styles from "./DashboardOverview.module.css";

type Tone = "blue" | "green" | "magenta" | "orange";

const TONE_STROKE: Record<Tone, [string, string]> = {
  blue: ["#35d9f2", "#4d8dff"],
  green: ["#2fd48a", "#7ef0b6"],
  magenta: ["#8b6bff", "#e05ad0"],
  orange: ["#ffa43d", "#ff7a5c"],
};

const STATUS_COLOR: Record<ProjectStatus, [string, string]> = {
  planning: ["#8b6bff", "#b39cff"],
  active: ["#35d9f2", "#4d8dff"],
  on_hold: ["#ffa43d", "#ffcb7d"],
  completed: ["#2fd48a", "#7ef0b6"],
  cancelled: ["#ff5470", "#ff8ea3"],
};

const PRIORITY_COLOR: Record<string, string> = {
  urgent: "#ff5470",
  high: "#ffa43d",
  normal: "#4d8dff",
  low: "#6d7e9d",
};

const EM_DASH = "—";

// --- small building blocks ----------------------------------------------

function Panel({
  children,
  className,
  kicker,
  title,
  action,
  icon,
}: {
  children: ReactNode;
  className?: string;
  kicker: string;
  title: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <section className={className ? `${styles.panel} ${className}` : styles.panel}>
      <header className={styles.panelHead}>
        {icon ? <span className={styles.panelIcon}>{icon}</span> : null}
        <div className={styles.panelTitles}>
          <span className={styles.kicker}>{kicker}</span>
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function Legend({
  rows,
}: {
  rows: { color: string; label: string; value: string; share?: string }[];
}) {
  return (
    <ul className={styles.legend}>
      {rows.map((row) => (
        <li key={row.label}>
          <i style={{ background: row.color }} />
          <span>{row.label}</span>
          <strong>{row.value}</strong>
          {row.share ? <em>{row.share}</em> : null}
        </li>
      ))}
    </ul>
  );
}

function Delta({ trend, noTrend, newLabel, vsLabel }: { trend: Trend | null; noTrend: string; newLabel: string; vsLabel: string }) {
  if (!trend) return <span className={styles.deltaMuted}>{noTrend}</span>;
  if (trend.percent === null) {
    return (
      <span className={styles.delta} data-dir="up">
        <TrendUpIcon width={13} height={13} />
        +{trend.recent}
        <em>{newLabel}</em>
      </span>
    );
  }
  const up = trend.percent >= 0;
  return (
    <span className={styles.delta} data-dir={up ? "up" : "down"}>
      {up ? <TrendUpIcon width={13} height={13} /> : <TrendDownIcon width={13} height={13} />}
      {up ? "+" : ""}
      {trend.percent}%<em>{vsLabel}</em>
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
  noTrend,
  newLabel,
  vsLabel,
}: {
  tone: Tone;
  icon: ReactNode;
  label: string;
  caption: string;
  value: string;
  series: number[] | null;
  trend: Trend | null;
  noTrend: string;
  newLabel: string;
  vsLabel: string;
}) {
  const [from, to] = TONE_STROKE[tone];
  return (
    <article className={styles.kpi} data-tone={tone}>
      <span className={styles.kpiBloom} aria-hidden="true" />
      <div className={styles.kpiHead}>
        <span className={styles.kpiIcon}>{icon}</span>
        <div className={styles.kpiTitles}>
          <span className={styles.kpiLabel}>{label}</span>
          <span className={styles.kpiCaption}>{caption}</span>
        </div>
      </div>
      <div className={styles.kpiValue}>{value}</div>
      <Delta trend={trend} noTrend={noTrend} newLabel={newLabel} vsLabel={vsLabel} />
      {series && series.some((point) => point > 0) ? (
        <Sparkline values={series} from={from} to={to} />
      ) : (
        <div className={styles.sparkPlaceholder} aria-hidden="true" />
      )}
    </article>
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

// --- the dashboard -------------------------------------------------------

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

  // --- portfolio ---------------------------------------------------------
  const projectCounts = summary?.project_status_counts ?? null;
  const totalProjects = countsTotal(projectCounts);
  const projectCompleted = projectCounts?.completed ?? 0;
  const projectActive = projectCounts?.active ?? 0;
  const projectPending = (projectCounts?.planning ?? 0) + (projectCounts?.on_hold ?? 0);
  const projectProgress = percent(projectCompleted, totalProjects);

  // --- documents ---------------------------------------------------------
  const documentCounts = summary?.document_status_counts ?? null;
  const totalDocuments = countsTotal(documentCounts);
  const processedDocuments = documentCounts?.processed ?? 0;
  const failedDocuments = documentCounts?.failed ?? 0;
  const pendingDocuments = (documentCounts?.uploaded ?? 0) + (documentCounts?.processing ?? 0);
  const documentRate = totalDocuments > 0 ? percent(processedDocuments, totalDocuments) : null;

  // --- trends ------------------------------------------------------------
  const projectTrendSeries = projects ? dailyCounts(projects.map((project) => project.created_at)) : null;
  const notificationSeries = notifications ? dailyCounts(notifications.map((entry) => entry.created_at)) : null;
  const briefSeries = briefs ? dailyCounts(briefs.map((entry) => entry.brief_date)) : null;

  // --- performance -------------------------------------------------------
  const response = responseTime(tickets);
  const overdueShare = tasks && tasks.open > 0 ? percent(tasks.overdue, tasks.open) : tasks ? 0 : null;
  const taskCompletionRate = tasks && tasks.total > 0 ? percent(tasks.completed, tasks.total) : null;
  const health = healthScore({
    taskCompletionRate,
    onTimeRate: tasks?.onTimeRate ?? null,
    overdueShare,
    documentProcessedRate: documentRate,
    projectDeliveryRate: totalProjects > 0 ? projectProgress : null,
  });

  // --- recommendation ----------------------------------------------------
  const recommendation = pickRecommendation();

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
    if (summary) return { text: t("dashboard.v2.rec.clear"), href: "/projects", tone: "green" };
    return null;
  }

  const firstName = user?.full_name?.split(" ")[0] || user?.email || "";
  const hour = new Date().getHours();
  const greetingKey: TranslationKey =
    hour < 12
      ? "dashboard.v2.greetingMorning"
      : hour < 18
        ? "dashboard.v2.greetingAfternoon"
        : "dashboard.v2.greetingEvening";

  const dayLabels = buildDayLabels(locale);
  const activity = summary?.recent_activity ?? null;

  return (
    <div className={styles.overview}>
      <div className={styles.atmosphere} aria-hidden="true">
        <DubaiSkyline className={styles.skyline} />
      </div>

      <header className={styles.hero}>
        <div className={styles.heroText}>
          <span className={styles.eyebrow}>{t("dashboard.v2.eyebrow")}</span>
          <h1>{t(greetingKey, { name: firstName })}</h1>
          <p>{t("dashboard.subtitle")}</p>
        </div>
        <div className={styles.heroSide}>
          <span className={styles.pulse} data-loading={loading ? "true" : undefined}>
            <i />
            {loading ? t("dashboard.v2.syncing") : t("dashboard.v2.live")}
          </span>
          <div className={styles.briefBar}>
            <span>
              {brief ? t("dashboard.todaysBrief") : loading ? t("dashboard.loadingBrief") : t("dashboard.noBriefMember")}
            </span>
            {canRegenerate ? (
              <button type="button" onClick={onRegenerate} disabled={regenerating}>
                <SparkIcon width={14} height={14} />
                {regenerating
                  ? t("dashboard.generating")
                  : brief
                    ? t("dashboard.regenerate")
                    : t("dashboard.generateBrief")}
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <div className={styles.kpiGrid}>
        <KpiCard
          tone="blue"
          icon={<ProjectsIcon />}
          label={t("dashboard.v2.kpi.projects")}
          caption={t("dashboard.v2.kpi.projectsCaption")}
          value={summary ? String(totalProjects) : EM_DASH}
          series={projectTrendSeries}
          trend={projectTrendSeries ? trendOf(projectTrendSeries) : null}
          noTrend={t("dashboard.v2.kpi.noTrend")}
          newLabel={t("dashboard.v2.kpi.newLabel")}
          vsLabel={t("dashboard.v2.kpi.vsPrevious")}
        />
        <KpiCard
          tone="green"
          icon={<TasksIcon />}
          label={t("dashboard.v2.kpi.tasksCompleted")}
          caption={t("dashboard.v2.kpi.tasksCompletedCaption")}
          value={tasks ? String(tasks.completed) : EM_DASH}
          series={tasks?.completedSeries ?? null}
          trend={tasks ? trendOf(tasks.completedSeries) : null}
          noTrend={t("dashboard.v2.kpi.noTrend")}
          newLabel={t("dashboard.v2.kpi.newLabel")}
          vsLabel={t("dashboard.v2.kpi.vsPrevious")}
        />
        <KpiCard
          tone="magenta"
          icon={<AskIcon />}
          label={t("dashboard.v2.kpi.messages")}
          caption={t("dashboard.v2.kpi.messagesCaption")}
          value={summary ? String(summary.unread_notifications) : EM_DASH}
          series={notificationSeries}
          trend={notificationSeries ? trendOf(notificationSeries) : null}
          noTrend={t("dashboard.v2.kpi.noTrend")}
          newLabel={t("dashboard.v2.kpi.newLabel")}
          vsLabel={t("dashboard.v2.kpi.vsPrevious")}
        />
        <KpiCard
          tone="orange"
          icon={<ReportsIcon />}
          label={t("dashboard.v2.kpi.reports")}
          caption={t("dashboard.v2.kpi.reportsCaption")}
          value={briefs ? `${briefs.length}${briefsCapped ? "+" : ""}` : EM_DASH}
          series={briefSeries}
          trend={briefSeries ? trendOf(briefSeries) : null}
          noTrend={t("dashboard.v2.kpi.noTrend")}
          newLabel={t("dashboard.v2.kpi.newLabel")}
          vsLabel={t("dashboard.v2.kpi.vsPrevious")}
        />
      </div>

      <div className={styles.layout}>
        <div className={styles.mainCol}>
          {/* A. Project Progress */}
          <Panel
            className={styles.spanFour}
            kicker={t("dashboard.v2.projectProgress.kicker")}
            title={t("dashboard.v2.projectProgress.title")}
            action={<Link href="/projects" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
          >
            {summary && totalProjects > 0 ? (
              <div className={styles.ringRow}>
                <ProgressRing
                  size={152}
                  segments={[
                    { value: projectCompleted, from: "#2fd48a", to: "#7ef0b6" },
                    { value: projectActive, from: "#35d9f2", to: "#4d8dff" },
                    { value: projectPending, from: "#8b6bff", to: "#e05ad0" },
                  ]}
                  centerValue={`${projectProgress}%`}
                  centerLabel={t("dashboard.v2.projectProgress.center")}
                />
                <Legend
                  rows={[
                    {
                      color: "#2fd48a",
                      label: t("dashboard.v2.projectProgress.completed"),
                      value: String(projectCompleted),
                      share: `${percent(projectCompleted, totalProjects)}%`,
                    },
                    {
                      color: "#4d8dff",
                      label: t("dashboard.v2.projectProgress.inProgress"),
                      value: String(projectActive),
                      share: `${percent(projectActive, totalProjects)}%`,
                    },
                    {
                      color: "#8b6bff",
                      label: t("dashboard.v2.projectProgress.pending"),
                      value: String(projectPending),
                      share: `${percent(projectPending, totalProjects)}%`,
                    },
                  ]}
                />
              </div>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.projectsByStatus.empty")}</p>
            )}
          </Panel>

          {/* B. Tasks Overview */}
          <Panel
            className={styles.spanFour}
            kicker={t("dashboard.v2.tasksOverview.kicker")}
            title={t("dashboard.v2.tasksOverview.title")}
            action={<Link href="/tasks" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
          >
            {tasks && tasks.total > 0 ? (
              <div className={styles.ringRow}>
                <ProgressRing
                  size={152}
                  segments={[
                    { value: tasks.completed, from: "#2fd48a", to: "#7ef0b6" },
                    { value: tasks.open - tasks.overdue, from: "#35d9f2", to: "#4d8dff" },
                    { value: tasks.overdue, from: "#ff5470", to: "#ff8ea3" },
                    { value: tasks.cancelled, from: "#3d4a67", to: "#55648a" },
                  ]}
                  centerValue={String(tasks.total)}
                  centerLabel={t("dashboard.v2.tasksOverview.center")}
                />
                <Legend
                  rows={[
                    {
                      color: "#2fd48a",
                      label: t("dashboard.v2.tasksOverview.completed"),
                      value: String(tasks.completed),
                      share: `${percent(tasks.completed, tasks.total)}%`,
                    },
                    {
                      color: "#4d8dff",
                      label: t("dashboard.v2.tasksOverview.inProgress"),
                      value: String(tasks.open - tasks.overdue),
                      share: `${percent(tasks.open - tasks.overdue, tasks.total)}%`,
                    },
                    {
                      color: "#ff5470",
                      label: t("dashboard.v2.tasksOverview.overdue"),
                      value: String(tasks.overdue),
                      share: `${percent(tasks.overdue, tasks.total)}%`,
                    },
                  ]}
                />
              </div>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.topTasks.empty")}</p>
            )}
          </Panel>

          {/* C. Performance Summary */}
          <Panel
            className={styles.spanFour}
            kicker={t("dashboard.v2.performance.kicker")}
            title={t("dashboard.v2.performance.title")}
          >
            <ul className={styles.perfList}>
              <li>
                <div className={styles.perfHead}>
                  <span>{t("dashboard.v2.performance.onTime")}</span>
                  <strong>{tasks && tasks.onTimeRate !== null ? `${tasks.onTimeRate}%` : EM_DASH}</strong>
                </div>
                {tasks && tasks.onTimeRate !== null ? (
                  <>
                    <Meter value={tasks.onTimeRate ?? 0} from="#2fd48a" to="#7ef0b6" />
                    <span className={styles.perfNote}>
                      {t("dashboard.v2.performance.sample", { count: tasks.onTimeSample })}
                    </span>
                  </>
                ) : (
                  <span className={styles.perfNote}>{t("dashboard.v2.noSource")}</span>
                )}
              </li>
              <li>
                <div className={styles.perfHead}>
                  <span>{t("dashboard.v2.performance.responseTime")}</span>
                  <strong>
                    {response
                      ? response.hours >= 48
                        ? t("dashboard.v2.performance.days", { value: Math.round(response.hours / 24) })
                        : t("dashboard.v2.performance.hours", { value: response.hours })
                      : EM_DASH}
                  </strong>
                </div>
                {response ? (
                  <span className={styles.perfNote}>
                    {t("dashboard.v2.performance.sample", { count: response.sample })}
                  </span>
                ) : (
                  <span className={styles.perfNote}>{t("dashboard.v2.noSource")}</span>
                )}
              </li>
              <li>
                <div className={styles.perfHead}>
                  <span>{t("dashboard.v2.performance.quality")}</span>
                  <strong>{EM_DASH}</strong>
                </div>
                <span className={styles.perfNote}>{t("dashboard.v2.noSource")}</span>
              </li>
              <li>
                <div className={styles.perfHead}>
                  <span>{t("dashboard.v2.performance.satisfaction")}</span>
                  <strong>{EM_DASH}</strong>
                </div>
                <span className={styles.perfNote}>{t("dashboard.v2.noSource")}</span>
              </li>
            </ul>
            {tasks && tasks.completedSeries.some((point) => point > 0) ? (
              <div className={styles.perfTrend}>
                <Sparkline values={tasks.completedSeries} from="#35d9f2" to="#8b6bff" height={34} />
              </div>
            ) : null}
          </Panel>

          {/* Performance Analytics */}
          <Panel
            className={styles.spanEight}
            kicker={t("dashboard.v2.analytics.kicker")}
            title={t("dashboard.v2.analytics.title")}
            action={
              <div className={styles.chartLegendRow}>
                <span data-series="created">
                  <i />
                  {t("dashboard.v2.analytics.created")}
                </span>
                <span data-series="completed">
                  <i />
                  {t("dashboard.v2.analytics.completed")}
                </span>
              </div>
            }
          >
            {tasks && (tasks.createdSeries.some((p) => p > 0) || tasks.completedSeries.some((p) => p > 0)) ? (
              <AreaChart
                labels={dayLabels}
                series={[
                  {
                    values: tasks.createdSeries,
                    from: "#35d9f2",
                    to: "#8b6bff",
                    label: t("dashboard.v2.analytics.created"),
                  },
                  {
                    values: tasks.completedSeries,
                    from: "#2fd48a",
                    to: "#7ef0b6",
                    label: t("dashboard.v2.analytics.completed"),
                  },
                ]}
              />
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.analytics.empty")}</p>
            )}
          </Panel>

          {/* Projects by Status */}
          <Panel
            className={styles.spanFour}
            kicker={t("dashboard.v2.projectsByStatus.kicker")}
            title={t("dashboard.v2.projectsByStatus.title")}
            action={<Link href="/projects" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
          >
            {projectCounts && totalProjects > 0 ? (
              <ul className={styles.statusList}>
                {(Object.keys(STATUS_COLOR) as ProjectStatus[])
                  .filter((status) => (projectCounts[status] ?? 0) > 0)
                  .map((status) => {
                    const count = projectCounts[status] ?? 0;
                    const [from, to] = STATUS_COLOR[status];
                    return (
                      <li key={status}>
                        <div className={styles.statusHead}>
                          <span>
                            <i style={{ background: from }} />
                            {t(PROJECT_STATUS_KEYS[status])}
                          </span>
                          <strong>
                            {count}
                            <em>{percent(count, totalProjects)}%</em>
                          </strong>
                        </div>
                        <Meter value={percent(count, totalProjects)} from={from} to={to} />
                      </li>
                    );
                  })}
              </ul>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.projectsByStatus.empty")}</p>
            )}
          </Panel>

          {/* Top Priority Tasks */}
          <Panel
            className={styles.spanSix}
            kicker={t("dashboard.v2.topTasks.kicker")}
            title={t("dashboard.v2.topTasks.title")}
            action={<Link href="/tasks" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
          >
            {tasks && tasks.topPriority.length > 0 ? (
              <ul className={styles.taskList}>
                {tasks.topPriority.map((task) => (
                  <li key={task.id}>
                    <Link href={`/tasks/${task.id}`}>
                      <span className={styles.taskDot} style={{ background: PRIORITY_COLOR[task.priority] }} />
                      <span className={styles.taskBody}>
                        <strong>{task.title}</strong>
                        <span>
                          {task.assignee_name || t("dashboard.v2.topTasks.unassigned")}
                          {task.project_name ? ` · ${task.project_name}` : ""}
                        </span>
                      </span>
                      <span className={styles.taskMeta}>
                        <em data-priority={task.priority}>{t(TASK_PRIORITY_KEYS[task.priority])}</em>
                        <b data-overdue={isOverdue(task) ? "true" : undefined}>{dueLabel(task, locale, t)}</b>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.topTasks.empty")}</p>
            )}
          </Panel>

          {/* Workload Distribution */}
          <Panel
            className={styles.spanSix}
            kicker={t("dashboard.v2.workload.kicker")}
            title={t("dashboard.v2.workload.title")}
            action={<Link href="/tasks/team" className={styles.panelLink}>{t("dashboard.exec.viewAll")}</Link>}
          >
            {tasks && tasks.byAssignee.length > 0 ? (
              <ul className={styles.statusList}>
                {tasks.byAssignee.slice(0, 6).map((row, index) => {
                  const max = tasks.byAssignee[0].count || 1;
                  const palette: [string, string][] = [
                    ["#35d9f2", "#4d8dff"],
                    ["#8b6bff", "#e05ad0"],
                    ["#2fd48a", "#7ef0b6"],
                    ["#ffa43d", "#ffcb7d"],
                    ["#ff5470", "#ff8ea3"],
                    ["#4d8dff", "#8b6bff"],
                  ];
                  const [from, to] = palette[index % palette.length];
                  return (
                    <li key={row.name ?? "unassigned"}>
                      <div className={styles.statusHead}>
                        <span>
                          <i style={{ background: from }} />
                          {row.name || t("dashboard.v2.workload.unassigned")}
                        </span>
                        <strong>{t("dashboard.v2.workload.openTasks", { count: row.count })}</strong>
                      </div>
                      <Meter value={percent(row.count, max)} from={from} to={to} />
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.workload.empty")}</p>
            )}
          </Panel>

          {/* Quick Actions */}
          <Panel
            className={styles.spanSeven}
            kicker={t("dashboard.v2.actions.kicker")}
            title={t("dashboard.v2.actions.title")}
          >
            <div className={styles.actionGrid}>
              <Link href="/projects" data-accent="magenta">
                <span className={styles.actionIcon}><ProjectsIcon /></span>
                {t("dashboard.v2.actions.newProject")}
              </Link>
              <Link href="/documents" data-accent="blue">
                <span className={styles.actionIcon}><UploadIcon /></span>
                {t("dashboard.uploadDocument")}
              </Link>
              <Link href="/tasks" data-accent="green">
                <span className={styles.actionIcon}><TasksIcon /></span>
                {t("dashboard.v2.actions.assignTask")}
              </Link>
              <Link href="/reports" data-accent="orange">
                <span className={styles.actionIcon}><ReportsIcon /></span>
                {t("dashboard.v2.actions.generateReport")}
              </Link>
              <Link href="/ask" data-accent="cyan">
                <span className={styles.actionIcon}><AskIcon /></span>
                {t("nav.ask")}
              </Link>
              <Link href="/brief" data-accent="violet">
                <span className={styles.actionIcon}><BriefIcon /></span>
                {t("nav.brief")}
              </Link>
            </div>
          </Panel>

          {/* Business Growth */}
          <Panel
            className={styles.spanFive}
            kicker={t("dashboard.v2.growth.kicker")}
            title={t("dashboard.v2.growth.title")}
            icon={<GrowthIcon />}
          >
            {summary || tasks ? (
              <ul className={styles.statusList}>
                <li>
                  <div className={styles.statusHead}>
                    <span>
                      <i style={{ background: "#35d9f2" }} />
                      {t("dashboard.v2.growth.documents")}
                    </span>
                    <strong>{documentRate !== null ? `${documentRate}%` : EM_DASH}</strong>
                  </div>
                  <Meter value={documentRate ?? 0} from="#35d9f2" to="#4d8dff" />
                </li>
                <li>
                  <div className={styles.statusHead}>
                    <span>
                      <i style={{ background: "#2fd48a" }} />
                      {t("dashboard.v2.growth.projectsDelivered")}
                    </span>
                    <strong>{totalProjects > 0 ? `${projectProgress}%` : EM_DASH}</strong>
                  </div>
                  <Meter value={totalProjects > 0 ? projectProgress : 0} from="#2fd48a" to="#7ef0b6" />
                </li>
                <li>
                  <div className={styles.statusHead}>
                    <span>
                      <i style={{ background: "#8b6bff" }} />
                      {t("dashboard.v2.growth.tasksDelivered")}
                    </span>
                    <strong>{taskCompletionRate !== null ? `${taskCompletionRate}%` : EM_DASH}</strong>
                  </div>
                  <Meter value={taskCompletionRate ?? 0} from="#8b6bff" to="#e05ad0" />
                </li>
              </ul>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.growth.empty")}</p>
            )}
          </Panel>
        </div>

        {/* Right intelligence column */}
        <aside className={styles.intel}>
          <section className={`${styles.panel} ${styles.scorePanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="violet"><InsightIcon /></span>
              <div className={styles.panelTitles}>
                <span className={styles.kicker}>{t("dashboard.v2.intel.kicker")}</span>
                <h2>{t("dashboard.v2.intel.insights")}</h2>
              </div>
            </header>
            {health ? (
              <>
                <div className={styles.scoreRow}>
                  <ProgressRing
                    size={132}
                    segments={[
                      { value: health.score, from: "#35d9f2", to: "#8b6bff" },
                      { value: 100 - health.score, from: "rgba(126,166,236,0.16)", to: "rgba(126,166,236,0.16)" },
                    ]}
                    centerValue={String(health.score)}
                    centerLabel={t("dashboard.v2.intel.score")}
                  />
                </div>
                <span className={styles.scoreCaption}>{t("dashboard.v2.intel.factors")}</span>
                <ul className={styles.factorList}>
                  {health.factors.map((factor) => (
                    <li key={factor.key}>
                      <span>{factorLabel(factor.key, t)}</span>
                      <strong>{Math.round(factor.value)}%</strong>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.intel.scoreEmpty")}</p>
            )}
          </section>

          <section className={`${styles.panel} ${styles.recPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="cyan"><PulseIcon /></span>
              <div className={styles.panelTitles}>
                <span className={styles.kicker}>{t("dashboard.v2.intel.kicker")}</span>
                <h2>{t("dashboard.v2.intel.recommendation")}</h2>
              </div>
            </header>
            {recommendation ? (
              <Link href={recommendation.href} className={styles.recCard} data-tone={recommendation.tone}>
                <span>{recommendation.text}</span>
                <em>{t("dashboard.exec.viewAll")}</em>
              </Link>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.intel.recommendationEmpty")}</p>
            )}
          </section>

          <section className={`${styles.panel} ${styles.activityPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="blue"><AuditIcon /></span>
              <div className={styles.panelTitles}>
                <span className={styles.kicker}>{t("dashboard.v2.intel.kicker")}</span>
                <h2>{t("dashboard.v2.intel.activity")}</h2>
              </div>
            </header>
            {activity && activity.length > 0 ? (
              <ul className={styles.timeline}>
                {activity.slice(0, 5).map((entry, index) => (
                  <li key={`${entry.created_at}-${index}`}>
                    <span className={styles.timelineIcon}>
                      {entry.resource_type === "document" ? <DocumentsIcon /> : <TasksIcon />}
                    </span>
                    <div>
                      <strong>{entry.action}</strong>
                      <span>
                        {entry.actor} · {formatDateTime(locale, entry.created_at)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : notifications && notifications.length > 0 ? (
              <ul className={styles.timeline}>
                {notifications.slice(0, 5).map((entry) => (
                  <li key={entry.id}>
                    <span className={styles.timelineIcon} data-unread={entry.read_at ? undefined : "true"}>
                      <AskIcon />
                    </span>
                    <div>
                      <strong>{entry.title}</strong>
                      <span>{formatDateTime(locale, entry.created_at)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.empty}>{t("dashboard.v2.intel.activityEmpty")}</p>
            )}
            <Link href="/settings/audit-log" className={styles.ghostLink}>
              {t("dashboard.exec.viewAll")}
            </Link>
          </section>

          <section className={`${styles.panel} ${styles.systemPanel}`}>
            <header className={styles.panelHead}>
              <span className={styles.panelIcon} data-accent="green"><ShieldIcon /></span>
              <div className={styles.panelTitles}>
                <span className={styles.kicker}>{t("dashboard.v2.intel.kicker")}</span>
                <h2>{t("dashboard.v2.intel.status")}</h2>
              </div>
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
                detail={
                  summary?.latest_brief
                    ? briefFreshness(summary.latest_brief.brief_date, t)
                    : t("dashboard.v2.intel.never")
                }
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
        </aside>
      </div>
    </div>
  );
}

// --- helpers -------------------------------------------------------------

function buildDayLabels(locale: string): string[] {
  const format = new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" });
  const now = Date.now();
  const day = 86_400_000;
  return [
    format.format(new Date(now - (TREND_DAYS - 1) * day)),
    format.format(new Date(now - Math.floor(TREND_DAYS / 2) * day)),
    format.format(new Date(now)),
  ];
}

type Translate = (key: TranslationKey, params?: Record<string, string | number>) => string;

function dueLabel(task: TaskPublic, locale: string, t: Translate): string {
  if (!task.due_date) return t("dashboard.v2.topTasks.noDue");
  if (isOverdue(task)) return t("dashboard.v2.topTasks.overdue");
  return new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" }).format(new Date(task.due_date));
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

function briefFreshness(briefDate: string, t: Translate): string {
  const parsed = new Date(briefDate);
  if (Number.isNaN(parsed.getTime())) return t("dashboard.v2.intel.upToDate");
  const days = Math.floor((Date.now() - parsed.getTime()) / 86_400_000);
  return days <= 1 ? t("dashboard.v2.intel.upToDate") : t("dashboard.v2.intel.attention");
}
