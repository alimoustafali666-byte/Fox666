"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { tasksApi } from "@/lib/api-client";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import type { TaskDashboardSummary } from "@/lib/types";
import styles from "./TaskSummaryTiles.module.css";

const TILES: { key: keyof TaskDashboardSummary; href: string; tone: "primary" | "warning" | "danger" | "info"; labelKey: TranslationKey }[] = [
  { key: "my_open_tasks", href: "/tasks", tone: "primary", labelKey: "tasks.summaryTiles.my_open_tasks" },
  { key: "due_today", href: "/tasks?due=due_today", tone: "info", labelKey: "tasks.summaryTiles.due_today" },
  { key: "overdue", href: "/tasks?due=overdue", tone: "danger", labelKey: "tasks.summaryTiles.overdue" },
  { key: "high_priority_open", href: "/tasks?priority=high", tone: "warning", labelKey: "tasks.summaryTiles.high_priority_open" },
];

// Purely derived from GET /tasks/summary -- real counts scoped to the
// caller's own tasks, no fabricated metrics and no scheduler involved.
export function TaskSummaryTiles() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<TaskDashboardSummary | null>(null);

  useEffect(() => {
    tasksApi
      .summary()
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  if (!summary) return null;

  return (
    <div className={styles.row}>
      {TILES.map(({ key, href, tone, labelKey }) => (
        <Link key={key} href={href} className={styles.stat} data-tone={tone}>
          <span className={styles.statBar} />
          <span className={styles.statCount}>{summary[key]}</span>
          <span className={styles.statLabel}>{t(labelKey)}</span>
        </Link>
      ))}
    </div>
  );
}

