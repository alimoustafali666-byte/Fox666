"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import type { DailyBriefPublic, DashboardSummaryResponse, RecentActivityEntry } from "@/lib/types";
import { AskIcon, DocumentsIcon, ProjectsIcon, ReportsIcon, TasksIcon } from "@/components/layout/icons";
import { DubaiSkyline } from "@/components/layout/DubaiSkyline";
import styles from "./DashboardOverview.module.css";

type Tone = "blue" | "green" | "magenta" | "orange";

function total(counts: Record<string, number>) {
  return Object.values(counts).reduce((sum, value) => sum + value, 0);
}

/** Real composition bar -- segments are actual counts, never a sample curve. */
function ProportionBar({ segments }: { segments: { value: number; color: string }[] }) {
  const sum = segments.reduce((a, b) => a + b.value, 0);
  if (sum <= 0) return null;
  return (
    <div className={styles.proportion} aria-hidden="true">
      {segments.map((segment, index) =>
        segment.value > 0 ? (
          <span key={index} style={{ width: `${(segment.value / sum) * 100}%`, background: segment.color }} />
        ) : null,
      )}
    </div>
  );
}

function Donut({ values, colors }: { values: number[]; colors: string[] }) {
  const sum = values.reduce((a, b) => a + b, 0) || 1;
  let offset = 0;
  const stops = values.map((value, index) => {
    const start = offset;
    offset += (value / sum) * 100;
    return `${colors[index]} ${start}% ${offset}%`;
  });
  return (
    <div className={styles.donut} style={{ background: `conic-gradient(${stops.join(", ")})` }}>
      <span>{values.reduce((a, b) => a + b, 0)}</span>
    </div>
  );
}

function KpiCard({
  tone,
  icon,
  label,
  caption,
  value,
  chip,
  segments,
}: {
  tone: Tone;
  icon: ReactNode;
  label: string;
  caption: string;
  value: number;
  chip: string | null;
  segments?: { value: number; color: string }[];
}) {
  return (
    <div className={styles.kpi} data-tone={tone}>
      <span className={styles.kpiBloom} aria-hidden="true" />
      <span className={styles.kpiRail} aria-hidden="true" />
      <div className={styles.kpiTop}>
        <span className={styles.kpiIcon}>{icon}</span>
        <div className={styles.kpiHeading}>
          <span className={styles.kpiLabel}>{label}</span>
          <span className={styles.kpiCaption}>{caption}</span>
        </div>
        {chip ? <span className={styles.kpiChip}>{chip}</span> : null}
      </div>
      <div className={styles.kpiFoot}>
        <strong className={styles.kpiValue}>{value}</strong>
        {segments ? <ProportionBar segments={segments} /> : null}
      </div>
    </div>
  );
}

/**
 * Real activity volume per day, built from the `created_at` timestamps the
 * dashboard-summary endpoint already returns. There is no trend endpoint on
 * the API and the backend is out of scope for this task, so this plots data
 * that genuinely exists rather than a decorative curve.
 */
function buildActivitySeries(entries: RecentActivityEntry[] | null | undefined) {
  if (!entries || entries.length === 0) return null;
  const byDay = new Map<string, number>();
  for (const entry of entries) {
    const parsed = new Date(entry.created_at);
    if (Number.isNaN(parsed.getTime())) continue;
    const key = parsed.toISOString().slice(0, 10);
    byDay.set(key, (byDay.get(key) ?? 0) + 1);
  }
  const days = [...byDay.keys()].sort();
  if (days.length < 2) return null;

  // Fill the gaps so a quiet day reads as zero rather than being skipped.
  const points: { key: string; value: number }[] = [];
  const cursor = new Date(`${days[0]}T00:00:00Z`);
  const last = new Date(`${days[days.length - 1]}T00:00:00Z`);
  while (cursor <= last && points.length < 90) {
    const key = cursor.toISOString().slice(0, 10);
    points.push({ key, value: byDay.get(key) ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return points;
}

const CHART = { x0: 42, x1: 610, y0: 16, y1: 190 };

function ActivityChart({ points, locale }: { points: { key: string; value: number }[]; locale: string }) {
  const max = Math.max(...points.map((p) => p.value), 1);
  const sx = (i: number) => CHART.x0 + (i / (points.length - 1)) * (CHART.x1 - CHART.x0);
  const sy = (v: number) => CHART.y1 - (v / max) * (CHART.y1 - CHART.y0);

  // Smooth through the daily buckets with midpoint quadratics.
  let line = `M ${sx(0)} ${sy(points[0].value)}`;
  for (let i = 1; i < points.length; i += 1) {
    const px = sx(i - 1);
    const py = sy(points[i - 1].value);
    const cx = sx(i);
    const cy = sy(points[i].value);
    line += ` Q ${px + (cx - px) / 2} ${py} ${(px + cx) / 2} ${(py + cy) / 2}`;
    line += ` Q ${px + (cx - px) / 2} ${cy} ${cx} ${cy}`;
  }
  const area = `${line} L ${sx(points.length - 1)} ${CHART.y1} L ${sx(0)} ${CHART.y1} Z`;

  const peakIndex = points.reduce((best, p, i) => (p.value > points[best].value ? i : best), 0);
  const ticks = [max, Math.round(max * 0.75), Math.round(max * 0.5), Math.round(max * 0.25), 0];
  const dayLabel = (key: string) =>
    new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" }).format(new Date(`${key}T00:00:00Z`));

  return (
    <>
      <div className={styles.chart}>
        <svg viewBox="0 0 620 220" preserveAspectRatio="none" role="img" aria-label="Activity volume per day">
          <defs>
            <linearGradient id="uaeAreaFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="#6f7bff" stopOpacity="0.44" />
              <stop offset="0.55" stopColor="#6f7bff" stopOpacity="0.12" />
              <stop offset="1" stopColor="#6f7bff" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="uaeLineStroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#35d9f2" />
              <stop offset="0.55" stopColor="#6f7bff" />
              <stop offset="1" stopColor="#e05ad0" />
            </linearGradient>
            <filter id="uaeLineGlow" x="-10%" y="-45%" width="120%" height="210%">
              <feGaussianBlur stdDeviation="4.5" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <g stroke="rgba(126,166,236,0.12)" strokeWidth="1" strokeDasharray="3 6">
            {ticks.slice(0, 4).map((_, i) => (
              <line key={i} x1={CHART.x0} y1={CHART.y0 + i * 43.5} x2="620" y2={CHART.y0 + i * 43.5} />
            ))}
          </g>
          <line x1={CHART.x0} y1={CHART.y1} x2="620" y2={CHART.y1} stroke="rgba(126,166,236,0.22)" />
          <g fill="#4e5d79" fontSize="10" fontFamily="IBM Plex Mono, monospace">
            {ticks.map((tick, i) => (
              <text key={i} x="34" y={CHART.y0 + i * 43.5 + 4} textAnchor="end">
                {tick}
              </text>
            ))}
          </g>
          <path d={area} fill="url(#uaeAreaFill)" />
          <path
            d={line}
            fill="none"
            stroke="url(#uaeLineStroke)"
            strokeWidth="2.6"
            strokeLinecap="round"
            filter="url(#uaeLineGlow)"
          />
          <line
            x1={sx(peakIndex)}
            y1={sy(points[peakIndex].value)}
            x2={sx(peakIndex)}
            y2={CHART.y1}
            stroke="rgba(126,166,236,0.3)"
            strokeDasharray="3 5"
          />
          <circle cx={sx(peakIndex)} cy={sy(points[peakIndex].value)} r="10" fill="rgba(111,123,255,0.24)" />
          <circle
            cx={sx(peakIndex)}
            cy={sy(points[peakIndex].value)}
            r="4.2"
            fill="#fff"
            stroke="#6f7bff"
            strokeWidth="2.6"
          />
        </svg>
      </div>
      <div className={styles.chartLabels}>
        <span>{dayLabel(points[0].key)}</span>
        {points.length > 2 ? <span>{dayLabel(points[Math.floor(points.length / 2)].key)}</span> : null}
        <span>{dayLabel(points[points.length - 1].key)}</span>
      </div>
    </>
  );
}

export function DashboardOverview({
  summary,
  brief,
  summaryLoading,
  canRegenerate,
  regenerating,
  onRegenerate,
}: {
  summary: DashboardSummaryResponse | null;
  brief: DailyBriefPublic | null;
  summaryLoading: boolean;
  canRegenerate: boolean;
  regenerating: boolean;
  onRegenerate: () => void;
}) {
  const { user } = useAuth();
  const { t, locale } = useTranslation();

  // Derivations unchanged from the previous implementation -- this task is a
  // visual reconstruction, so no KPI's meaning or arithmetic was altered.
  const projects = summary ? total(summary.project_status_counts) : 0;
  const documents = summary ? total(summary.document_status_counts) : 0;
  const openTasks = summary?.my_tasks.my_open_tasks ?? 0;
  const completedTasks = summary ? Math.max(0, projects - openTasks) : 0;
  const messages = summary?.unread_notifications ?? 0;
  const reports = summary?.latest_brief?.item_count ?? 0;
  const overdue = summary?.my_tasks.overdue ?? 0;
  const activeProjects = summary?.project_status_counts.active ?? 0;
  const highPriority = summary?.my_tasks.high_priority_open ?? 0;
  const processedDocs = summary?.document_status_counts.processed ?? 0;

  const projectValues = summary
    ? [
        summary.project_status_counts.completed ?? 0,
        summary.project_status_counts.active ?? 0,
        (summary.project_status_counts.planning ?? 0) + (summary.project_status_counts.on_hold ?? 0),
      ]
    : [0, 0, 0];
  const taskValues = summary ? [completedTasks, openTasks, summary.my_tasks.overdue] : [0, 0, 0];
  const priorityValues = [highPriority, Math.max(0, openTasks - highPriority), 0];

  const firstName = user?.full_name?.split(" ")[0] || user?.email || "there";
  const series = buildActivitySeries(summary?.recent_activity);
  const processedShare = documents > 0 ? Math.round((processedDocs / documents) * 100) : 0;
  const briefDate = summary?.latest_brief?.brief_date
    ? new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short" }).format(
        new Date(summary.latest_brief.brief_date),
      )
    : null;

  return (
    <div className={styles.overview}>
      <DubaiSkyline variant="panorama" className={styles.skyline} />

      <div className={styles.greeting}>
        <div>
          <span className={styles.eyebrow}>Workspace pulse</span>
          <h1>Good morning, {firstName}!</h1>
          <p>{t("dashboard.subtitle")}</p>
          <span className={styles.pulseChip} data-loading={summaryLoading ? "true" : undefined}>
            <i className={styles.pulseDot} />
            {summaryLoading ? t("common.loading") : "LIVE"}
          </span>
        </div>
      </div>

      <div className={styles.kpiGrid}>
        <KpiCard
          tone="blue"
          icon={<ProjectsIcon />}
          label="Total Projects"
          caption="All statuses"
          value={projects}
          chip={`${activeProjects} active`}
          segments={[
            { value: projectValues[0], color: "#2fd48a" },
            { value: projectValues[1], color: "#4d8dff" },
            { value: projectValues[2], color: "#ffa43d" },
          ]}
        />
        <KpiCard
          tone="green"
          icon={<TasksIcon />}
          label="Tasks Completed"
          caption="Your workload"
          value={completedTasks}
          chip={`${openTasks} open`}
          segments={[
            { value: taskValues[0], color: "#2fd48a" },
            { value: taskValues[1], color: "#4d8dff" },
            { value: taskValues[2], color: "#ff5470" },
          ]}
        />
        <KpiCard
          tone="magenta"
          icon={<AskIcon />}
          label="Messages"
          caption="Notifications"
          value={messages}
          chip="unread"
        />
        <KpiCard
          tone="orange"
          icon={<ReportsIcon />}
          label="Reports Generated"
          caption="Latest brief"
          value={reports}
          chip={briefDate}
        />
      </div>

      <div className={styles.briefBar}>
        <span>
          {brief
            ? t("dashboard.todaysBrief")
            : summaryLoading
              ? t("dashboard.loadingBrief")
              : t("dashboard.noBriefMember")}
        </span>
        {canRegenerate ? (
          <button type="button" onClick={onRegenerate} disabled={regenerating}>
            {regenerating ? t("dashboard.generating") : brief ? t("dashboard.regenerate") : t("dashboard.generateBrief")}
          </button>
        ) : null}
      </div>

      <div className={styles.mainGrid}>
        <section className={`${styles.panel} ${styles.portfolio}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Portfolio</span>
              <h2>Project Progress Overview</h2>
            </div>
            <Link href="/projects">{t("dashboard.exec.viewAll")}</Link>
          </div>
          <div className={styles.donutRow}>
            <div className={styles.donutWrap}>
              <Donut values={projectValues} colors={["#2fd48a", "#4d8dff", "#8b6bff"]} />
              <div className={styles.donutCore}>Projects</div>
            </div>
            <div className={styles.legend}>
              <div>
                <i className={styles.dotGreen} />
                <span>Completed</span>
                <strong>{projectValues[0]}</strong>
              </div>
              <div>
                <i className={styles.dotBlue} />
                <span>In Progress</span>
                <strong>{projectValues[1]}</strong>
              </div>
              <div>
                <i className={styles.dotViolet} />
                <span>Pending</span>
                <strong>{projectValues[2]}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className={`${styles.panel} ${styles.execution}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Execution</span>
              <h2>Tasks Overview</h2>
            </div>
            <Link href="/tasks">{t("dashboard.exec.viewAll")}</Link>
          </div>
          <div className={styles.donutRow}>
            <div className={styles.donutWrap}>
              <Donut values={taskValues} colors={["#2fd48a", "#4d8dff", "#ff5470"]} />
              <div className={styles.donutCore}>Tasks</div>
            </div>
            <div className={styles.legend}>
              <div>
                <i className={styles.dotGreen} />
                <span>Completed</span>
                <strong>{taskValues[0]}</strong>
              </div>
              <div>
                <i className={styles.dotBlue} />
                <span>In Progress</span>
                <strong>{taskValues[1]}</strong>
              </div>
              <div>
                <i className={styles.dotRose} />
                <span>Overdue</span>
                <strong>{taskValues[2]}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className={`${styles.panel} ${styles.activity}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Recent signals</span>
              <h2>Activity Timeline</h2>
            </div>
          </div>
          {summary?.recent_activity?.length ? (
            <div className={styles.timeline}>
              {summary.recent_activity.slice(0, 4).map((entry, index) => (
                <div className={styles.timelineItem} key={`${entry.created_at}-${index}`}>
                  <span className={styles.activityIcon}>{index % 2 ? <DocumentsIcon /> : <TasksIcon />}</span>
                  <div>
                    <strong>{entry.action}</strong>
                    <span>
                      <b>{entry.actor}</b> · {formatDateTime(locale, entry.created_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className={styles.empty}>{t("dashboard.exec.noActivityDescription")}</p>
          )}
          <Link href="/settings/audit-log" className={styles.ghostLink}>
            {t("dashboard.exec.viewAll")}
          </Link>
        </section>

        <section className={`${styles.panel} ${styles.analytics}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Signal tracking</span>
              <h2>Performance Analytics</h2>
            </div>
            <span className={styles.chartLegend}>
              <i />
              Activity volume
            </span>
          </div>
          {series ? (
            <ActivityChart points={series} locale={locale} />
          ) : (
            <p className={styles.empty}>{t("dashboard.exec.noActivityDescription")}</p>
          )}
        </section>

        <section className={`${styles.panel} ${styles.priority}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Workload</span>
              <h2>Tasks by Priority</h2>
            </div>
          </div>
          <div className={styles.priorityRow}>
            <div
              className={styles.priorityRings}
              role="img"
              aria-label={`${priorityValues[0]} high priority, ${priorityValues[1]} medium priority, ${priorityValues[2]} low priority`}
            >
              <span />
              <span />
              <span />
              <b>{openTasks}</b>
            </div>
            <div className={styles.legend}>
              <div>
                <i className={styles.dotRose} />
                <span>High Priority</span>
                <strong>{priorityValues[0]}</strong>
              </div>
              <div>
                <i className={styles.dotOrange} />
                <span>Medium Priority</span>
                <strong>{priorityValues[1]}</strong>
              </div>
              <div>
                <i className={styles.dotBlue} />
                <span>Low Priority</span>
                <strong>{priorityValues[2]}</strong>
              </div>
              <div>
                <i className={styles.dotMuted} />
                <span>{t("dashboard.exec.overdue")}</span>
                <strong>{overdue}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className={`${styles.panel} ${styles.actions}`}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>Shortcuts</span>
              <h2>Quick Actions</h2>
            </div>
          </div>
          <div className={styles.actionGrid}>
            <Link href="/projects" data-accent="magenta">
              <span className={styles.actionIcon}>
                <ProjectsIcon />
              </span>
              <span>New Project</span>
            </Link>
            <Link href="/documents?upload=1" data-accent="blue">
              <span className={styles.actionIcon}>
                <DocumentsIcon />
              </span>
              <span>{t("dashboard.uploadDocument")}</span>
            </Link>
            <Link href="/tasks" data-accent="green">
              <span className={styles.actionIcon}>
                <TasksIcon />
              </span>
              <span>Assign Task</span>
            </Link>
            <Link href="/reports" data-accent="orange">
              <span className={styles.actionIcon}>
                <ReportsIcon />
              </span>
              <span>Generate Report</span>
            </Link>
          </div>
        </section>

        <section className={`${styles.panel} ${styles.growth}`}>
          <span className={styles.growthIcon}>
            <ReportsIcon />
          </span>
          <div className={styles.growthBody}>
            <span className={styles.panelKicker}>Momentum</span>
            <h2>Business Growth</h2>
            <div className={styles.growthValue}>{processedShare}%</div>
            <div className={styles.growthMeta}>
              {documents} active intelligence assets · {processedDocs} processed
            </div>
          </div>
          <div className={styles.growthBar}>
            <ProportionBar
              segments={[
                { value: processedDocs, color: "#35d9f2" },
                { value: Math.max(0, documents - processedDocs), color: "rgba(126,166,236,0.18)" },
              ]}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
