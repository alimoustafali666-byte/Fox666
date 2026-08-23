"use client";

import Link from "next/link";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProjectsIcon, DocumentsIcon, TasksIcon, TicketIcon, AuditIcon } from "@/components/layout/icons";
import { PROJECT_STATUS_KEYS, PROJECT_STATUS_TONE } from "@/components/projects/statusLabels";
import type { DashboardSummaryResponse, ProjectStatus } from "@/lib/types";
import styles from "./ExecutiveSummary.module.css";

const DOCUMENT_STATUS_TONE: Record<string, BadgeTone> = {
  uploaded: "neutral", processing: "info", processed: "success", failed: "danger",
};

const TICKET_STATUS_TONE: Record<string, BadgeTone> = {
  open: "info", in_progress: "info", waiting_for_user: "warning", resolved: "success", closed: "neutral",
};

const TONE_BAR_COLOR: Record<BadgeTone, string> = {
  neutral: "var(--color-neutral-text)",
  info: "var(--color-info)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  primary: "var(--color-primary)",
};

function CountChips({ counts, toneMap, labelFor }: { counts: Record<string, number>; toneMap: Record<string, BadgeTone>; labelFor: (key: string) => string }) {
  const entries = Object.entries(counts).filter(([, n]) => n > 0);
  if (entries.length === 0) return null;
  return (
    <div className={styles.chipRow}>
      {entries.map(([key, count]) => (
        <Badge key={key} tone={toneMap[key] ?? "neutral"}>
          {labelFor(key)}: {count}
        </Badge>
      ))}
    </div>
  );
}

// A restrained, pure-CSS segmented proportion bar -- a lightweight
// visualization of an existing status breakdown (no new backend, no chart
// library). Segment order follows `counts`' own key order.
function ProportionBar({ counts, toneMap, total }: { counts: Record<string, number>; toneMap: Record<string, BadgeTone>; total: number }) {
  if (total === 0) return null;
  return (
    <div className={styles.proportionBar} role="presentation">
      {Object.entries(counts)
        .filter(([, n]) => n > 0)
        .map(([key, count]) => (
          <span
            key={key}
            className={styles.proportionSegment}
            style={{ width: `${(count / total) * 100}%`, background: TONE_BAR_COLOR[toneMap[key] ?? "neutral"] }}
          />
        ))}
    </div>
  );
}

export function ExecutiveSummary({ summary }: { summary: DashboardSummaryResponse }) {
  const { t, locale } = useTranslation();

  const totalProjects = Object.values(summary.project_status_counts).reduce((a, b) => a + b, 0);
  const totalDocuments = Object.values(summary.document_status_counts).reduce((a, b) => a + b, 0);
  const totalTickets = Object.values(summary.my_ticket_status_counts).reduce((a, b) => a + b, 0);

  return (
    <div className={styles.grid}>
      <Card interactive>
        <CardHeader
          icon={<ProjectsIcon />}
          title={t("dashboard.exec.projectsTitle")}
          actions={<Link href="/projects">{t("dashboard.exec.viewAll")}</Link>}
        />
        <CardBody>
          {totalProjects === 0 ? (
            <p className={styles.emptyText}>{t("dashboard.exec.noProjects")}</p>
          ) : (
            <>
              <ProportionBar counts={summary.project_status_counts} toneMap={PROJECT_STATUS_TONE} total={totalProjects} />
              <CountChips
                counts={summary.project_status_counts}
                toneMap={PROJECT_STATUS_TONE}
                labelFor={(key) => t(PROJECT_STATUS_KEYS[key as ProjectStatus] ?? "dashboard.exec.noProjects")}
              />
            </>
          )}
        </CardBody>
      </Card>

      <Card interactive>
        <CardHeader
          icon={<DocumentsIcon />}
          title={t("dashboard.exec.documentsTitle")}
          actions={<Link href="/documents">{t("dashboard.exec.viewAll")}</Link>}
        />
        <CardBody>
          {totalDocuments === 0 ? (
            <p className={styles.emptyText}>{t("dashboard.exec.noDocuments")}</p>
          ) : (
            <>
              <ProportionBar counts={summary.document_status_counts} toneMap={DOCUMENT_STATUS_TONE} total={totalDocuments} />
              <CountChips
                counts={summary.document_status_counts}
                toneMap={DOCUMENT_STATUS_TONE}
                labelFor={(key) => t(`dashboard.exec.documentStatuses.${key}` as never)}
              />
            </>
          )}
        </CardBody>
      </Card>

      {summary.company_tasks ? (
        <Card interactive>
          <CardHeader
            icon={<TasksIcon />}
            title={t("dashboard.exec.companyTasksTitle")}
            actions={<Link href="/tasks/team">{t("dashboard.exec.viewAll")}</Link>}
          />
          <CardBody>
            <div className={styles.chipRow}>
              <Badge tone="primary">{t("dashboard.exec.open")}: {summary.company_tasks.open}</Badge>
              <Badge tone="danger">{t("dashboard.exec.overdue")}: {summary.company_tasks.overdue}</Badge>
              <Badge tone="warning">{t("dashboard.exec.blocked")}: {summary.company_tasks.blocked}</Badge>
            </div>
          </CardBody>
        </Card>
      ) : null}

      <Card interactive>
        <CardHeader
          icon={<TicketIcon />}
          title={t("dashboard.exec.ticketsTitle")}
          actions={<Link href="/support/tickets">{t("dashboard.exec.viewAll")}</Link>}
        />
        <CardBody>
          {totalTickets === 0 ? (
            <p className={styles.emptyText}>{t("dashboard.exec.noTickets")}</p>
          ) : (
            <CountChips
              counts={summary.my_ticket_status_counts}
              toneMap={TICKET_STATUS_TONE}
              labelFor={(key) => t(`support.tickets.statuses.${key}` as never)}
            />
          )}
        </CardBody>
      </Card>

      {summary.recent_activity ? (
        <Card className={styles.spanFull}>
          <CardHeader
            icon={<AuditIcon />}
            title={t("dashboard.exec.recentActivityTitle")}
            actions={<Link href="/settings/audit-log">{t("dashboard.exec.viewAll")}</Link>}
          />
          <CardBody>
            {summary.recent_activity.length === 0 ? (
              <EmptyState title={t("dashboard.exec.noActivityTitle")} description={t("dashboard.exec.noActivityDescription")} />
            ) : (
              <ul className={styles.activityList}>
                {summary.recent_activity.map((entry, i) => (
                  <li key={i} className={styles.activityItem}>
                    <span className={styles.activityMuted}>{formatDateTime(locale, entry.created_at)}</span>
                    <span>
                      <strong>{entry.actor}</strong> · {entry.action}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}

