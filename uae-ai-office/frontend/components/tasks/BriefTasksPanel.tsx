"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { tasksApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import styles from "./BriefTasksPanel.module.css";

interface Counts {
  overdue: number;
  dueToday: number;
  blocked: number;
}

// Independent of AI-generated brief content -- these are plain, real
// counts of the caller's own tasks, computed on read from /tasks
// endpoints, never derived from or feeding into brief generation.
export function BriefTasksPanel() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [counts, setCounts] = useState<Counts | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([tasksApi.summary(), tasksApi.list({ assigned_to: user.id, status: "blocked", limit: 100 })])
      .then(([summary, blockedPage]) => {
        if (cancelled) return;
        setCounts({ overdue: summary.overdue, dueToday: summary.due_today, blocked: blockedPage.items.length });
      })
      .catch(() => {
        if (!cancelled) setCounts(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const rows: { key: keyof Counts; labelKey: "brief.tasksPanel.overdue" | "brief.tasksPanel.dueToday" | "brief.tasksPanel.blocked"; href: string }[] = [
    { key: "overdue", labelKey: "brief.tasksPanel.overdue", href: "/tasks?due=overdue" },
    { key: "dueToday", labelKey: "brief.tasksPanel.dueToday", href: "/tasks?due=due_today" },
    { key: "blocked", labelKey: "brief.tasksPanel.blocked", href: "/tasks?status=blocked" },
  ];

  const hasAny = counts && (counts.overdue > 0 || counts.dueToday > 0 || counts.blocked > 0);

  return (
    <Card>
      <CardHeader title={t("brief.tasksPanel.title")} />
      <CardBody tight>
        {!counts ? null : !hasAny ? (
          <div style={{ padding: "var(--space-5)" }}>
            <EmptyState title={t("brief.tasksPanel.emptyTitle")} description={t("brief.tasksPanel.emptyDescription")} />
          </div>
        ) : (
          <div className={styles.list}>
            {rows.map(({ key, labelKey, href }) =>
              counts[key] > 0 ? (
                <Link key={key} href={href} className={styles.row}>
                  <span className={styles.count}>{counts[key]}</span>
                  <span className={styles.label}>{t(labelKey)}</span>
                </Link>
              ) : null
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

