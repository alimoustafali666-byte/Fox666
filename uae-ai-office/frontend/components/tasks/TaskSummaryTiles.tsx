"use client";

import { useEffect, useState } from "react";
import { tasksApi } from "@/lib/api-client";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import type { TaskDashboardSummary } from "@/lib/types";
import type { BadgeTone } from "@/components/ui/Badge";
import { StatTile, StatTileRow } from "@/components/ui/StatTile";

const TILES: { key: keyof TaskDashboardSummary; href: string; tone: BadgeTone; labelKey: TranslationKey }[] = [
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
    <StatTileRow>
      {TILES.map(({ key, href, tone, labelKey }) => (
        <StatTile key={key} href={href} tone={tone} count={summary[key]} label={t(labelKey)} />
      ))}
    </StatTileRow>
  );
}
