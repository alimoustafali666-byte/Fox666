"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import type { DailyBriefPublic, DashboardSummaryResponse } from "@/lib/types";
import { AskIcon, DocumentsIcon, ProjectsIcon, ReportsIcon, TasksIcon } from "@/components/layout/icons";
import styles from "./DashboardOverview.module.css";

type Tone = "blue" | "green" | "magenta" | "orange";

function total(counts: Record<string, number>) {
  return Object.values(counts).reduce((sum, value) => sum + value, 0);
}

function Donut({ values, colors }: { values: number[]; colors: string[] }) {
  const sum = values.reduce((a, b) => a + b, 0) || 1;
  let offset = 0;
  const stops = values.map((value, index) => {
    const start = offset;
    offset += (value / sum) * 100;
    return `${colors[index]} ${start}% ${offset}%`;
  });
  return <div className={styles.donut} style={{ background: `conic-gradient(${stops.join(", ")})` }}><span>{values.reduce((a, b) => a + b, 0)}</span></div>;
}

function Sparkline({ tone }: { tone: Tone }) {
  return <svg className={styles.sparkline} viewBox="0 0 110 34" preserveAspectRatio="none" aria-hidden="true"><path className={styles[`spark-${tone}`]} d="M2 29 C13 27, 15 18, 25 22 S38 28, 47 17 S61 21, 70 14 S83 16, 91 7 S101 11, 108 3" /></svg>;
}

function KpiCard({ tone, icon, label, value, change }: { tone: Tone; icon: ReactNode; label: string; value: number; change: string }) {
  return <div className={styles.kpi} data-tone={tone}><div className={styles.kpiTop}><span className={styles.kpiIcon}>{icon}</span><span className={styles.kpiChange}>{change}</span></div><strong>{value}</strong><span className={styles.kpiLabel}>{label}</span><Sparkline tone={tone} /></div>;
}

export function DashboardOverview({ summary, brief, summaryLoading, canRegenerate, regenerating, onRegenerate }: { summary: DashboardSummaryResponse | null; brief: DailyBriefPublic | null; summaryLoading: boolean; canRegenerate: boolean; regenerating: boolean; onRegenerate: () => void }) {
  const { user } = useAuth();
  const { t, locale } = useTranslation();
  const projects = summary ? total(summary.project_status_counts) : 0;
  const documents = summary ? total(summary.document_status_counts) : 0;
  const openTasks = summary?.my_tasks.my_open_tasks ?? 0;
  const completedTasks = summary ? Math.max(0, projects - openTasks) : 0;
  const messages = summary?.unread_notifications ?? 0;
  const reports = summary?.latest_brief?.item_count ?? 0;
  const projectValues = summary ? [summary.project_status_counts.completed ?? 0, summary.project_status_counts.active ?? 0, (summary.project_status_counts.planning ?? 0) + (summary.project_status_counts.on_hold ?? 0)] : [0, 0, 0];
  const taskValues = summary ? [completedTasks, openTasks, summary.my_tasks.overdue] : [0, 0, 0];
  const firstName = user?.full_name?.split(" ")[0] || user?.email || "there";

  return <div className={styles.overview}>
    <div className={styles.greeting}><div><span className={styles.eyebrow}>Workspace pulse</span><h1>Good morning, {firstName}!</h1><p>{t("dashboard.subtitle")}</p></div><div className={styles.dateCard}><span>Today</span><strong>{new Intl.DateTimeFormat(locale, { weekday: "short", day: "2-digit", month: "short" }).format(new Date())}</strong></div></div>

    <div className={styles.kpiGrid}>
      <KpiCard tone="blue" icon={<ProjectsIcon />} label="Total Projects" value={projects} change="+12.5%" />
      <KpiCard tone="green" icon={<TasksIcon />} label="Tasks Completed" value={completedTasks} change="+8.4%" />
      <KpiCard tone="magenta" icon={<AskIcon />} label="Messages" value={messages} change="+18.2%" />
      <KpiCard tone="orange" icon={<ReportsIcon />} label="Reports Generated" value={reports} change="+6.8%" />
    </div>
    <div className={styles.briefBar}><span>{brief ? t("dashboard.todaysBrief") : summaryLoading ? t("dashboard.loadingBrief") : t("dashboard.noBriefMember")}</span>{canRegenerate ? <button type="button" onClick={onRegenerate} disabled={regenerating}>{regenerating ? t("dashboard.generating") : brief ? t("dashboard.regenerate") : t("dashboard.generateBrief")}</button> : null}</div>

    <div className={styles.mainGrid}>
      <section className={styles.panel}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Portfolio</span><h2>Project Progress Overview</h2></div><Link href="/projects">View all</Link></div><div className={styles.donutRow}><div className={styles.donutWrap}><Donut values={projectValues} colors={["#62e3a0", "#39d6e8", "#6d3fd6"]} /><div className={styles.donutCore}>Projects</div></div><div className={styles.legend}><div><i className={styles.dotGreen} /><span>Completed</span><strong>{projectValues[0]}</strong></div><div><i className={styles.dotCyan} /><span>In Progress</span><strong>{projectValues[1]}</strong></div><div><i className={styles.dotViolet} /><span>Pending</span><strong>{projectValues[2]}</strong></div></div></div></section>
      <section className={styles.panel}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Execution</span><h2>Tasks Overview</h2></div><Link href="/tasks">View all</Link></div><div className={styles.donutRow}><div className={styles.donutWrap}><Donut values={taskValues} colors={["#62e3a0", "#7090ff", "#ff7898"]} /><div className={styles.donutCore}>Tasks</div></div><div className={styles.legend}><div><i className={styles.dotGreen} /><span>Completed</span><strong>{taskValues[0]}</strong></div><div><i className={styles.dotBlue} /><span>In Progress</span><strong>{taskValues[1]}</strong></div><div><i className={styles.dotRose} /><span>Overdue</span><strong>{taskValues[2]}</strong></div></div></div></section>

      <section className={`${styles.panel} ${styles.analytics}`}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Signal tracking</span><h2>Performance Analytics</h2></div><span className={styles.target}>Target <b>88%</b></span></div><div className={styles.chart}><div className={styles.chartGrid} /><svg viewBox="0 0 700 190" preserveAspectRatio="none" aria-label="Performance trend chart"><defs><linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#39d6e8" stopOpacity="0.3" /><stop offset="1" stopColor="#39d6e8" stopOpacity="0" /></linearGradient></defs><path d="M0 153 C50 143 64 118 112 129 S171 91 215 108 S268 132 317 86 S364 75 410 94 S464 50 511 67 S566 90 607 43 S661 48 700 25 V190 H0Z" fill="url(#areaFill)" /><path d="M0 153 C50 143 64 118 112 129 S171 91 215 108 S268 132 317 86 S364 75 410 94 S464 50 511 67 S566 90 607 43 S661 48 700 25" fill="none" stroke="#39d6e8" strokeWidth="3" /></svg></div><div className={styles.chartLabels}><span>Jan</span><span>Mar</span><span>May</span><span>Jul</span><span>Sep</span><span>Nov</span></div></section>
      <section className={styles.panel}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Workload</span><h2>Tasks by Priority</h2></div></div><div className={styles.priority}><div className={styles.priorityRings}><span /><span /><span /><b>{openTasks}</b></div><div className={styles.legend}><div><i className={styles.dotRose} /><span>High Priority</span><strong>{summary?.my_tasks.high_priority_open ?? 0}</strong></div><div><i className={styles.dotOrange} /><span>Medium Priority</span><strong>{Math.max(0, openTasks - (summary?.my_tasks.high_priority_open ?? 0))}</strong></div><div><i className={styles.dotBlue} /><span>Low Priority</span><strong>0</strong></div></div></div></section>

      <section className={`${styles.panel} ${styles.activity}`}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Recent signals</span><h2>Activity Timeline</h2></div><Link href="/settings/audit-log">View all activity</Link></div>{summary?.recent_activity?.length ? <div className={styles.timeline}>{summary.recent_activity.slice(0, 4).map((entry, index) => <div className={styles.timelineItem} key={`${entry.created_at}-${index}`}><span className={styles.activityIcon}>{index % 2 ? <DocumentsIcon /> : <TasksIcon />}</span><div><strong>{entry.action}</strong><span>{entry.actor} · {formatDateTime(locale, entry.created_at)}</span></div></div>)}</div> : <p className={styles.empty}>No recent activity yet.</p>}</section>
      <section className={`${styles.panel} ${styles.actions}`}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Shortcuts</span><h2>Quick Actions</h2></div></div><div className={styles.actionGrid}><Link href="/projects"><ProjectsIcon /><span>New Project</span></Link><Link href="/documents?upload=1"><DocumentsIcon /><span>Upload Document</span></Link><Link href="/tasks"><TasksIcon /><span>Assign Task</span></Link><Link href="/reports"><ReportsIcon /><span>Generate Report</span></Link></div></section>
      <section className={`${styles.panel} ${styles.growth}`}><div className={styles.panelHeader}><div><span className={styles.panelKicker}>Momentum</span><h2>Business Growth</h2></div><span className={styles.growthValue}>+24.8%</span></div><div className={styles.growthLine}><strong>{documents}</strong><span>active intelligence assets</span></div><Sparkline tone="green" /></section>
    </div>
  </div>;
}
