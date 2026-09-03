"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth, errorMessage } from "@/lib/auth-context";
import {
  ApiError,
  briefsApi,
  collaborationApi,
  projectsApi,
  reportsApi,
  supportApi,
  tasksApi,
} from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import type { DashboardData } from "@/components/dashboard/metrics";
import type { DailyBriefPublic } from "@/lib/types";

const TASK_SCAN_LIMIT = 100;
const PROJECT_SCAN_LIMIT = 100;
const BRIEF_SCAN_LIMIT = 50;
const TICKET_SCAN_LIMIT = 50;
const NOTIFICATION_SCAN_LIMIT = 30;

const EMPTY: DashboardData = {
  summary: null,
  tasks: null,
  projects: null,
  notifications: null,
  briefs: null,
  briefsCapped: false,
  tickets: null,
};

export default function DashboardPage() {
  const { role } = useAuth();
  const { t } = useTranslation();
  const canRegenerate = role === "owner" || role === "admin" || role === "manager";
  const [brief, setBrief] = useState<DailyBriefPublic | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardData>(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setBrief(await briefsApi.getLatest());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setBrief(null);
      else setError(errorMessage(err, t("dashboard.genericLoadError")));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Every panel is fed from an existing read-only endpoint. Each request is
  // settled independently so one source being unavailable (role-scoped or
  // simply failing) leaves that panel in a neutral empty state instead of
  // blanking the dashboard -- and nothing is ever substituted with a sample.
  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      const [summary, tasks, projects, notifications, briefs, tickets] = await Promise.allSettled([
        reportsApi.dashboardSummary(),
        tasksApi.list({ limit: TASK_SCAN_LIMIT }),
        projectsApi.list({ limit: PROJECT_SCAN_LIMIT }),
        collaborationApi.listNotifications({ limit: NOTIFICATION_SCAN_LIMIT }),
        briefsApi.list({ limit: BRIEF_SCAN_LIMIT }),
        supportApi.listTickets({ limit: TICKET_SCAN_LIMIT }),
      ]);
      if (cancelled) return;

      const briefPage = briefs.status === "fulfilled" ? briefs.value : null;
      setData({
        summary: summary.status === "fulfilled" ? summary.value : null,
        tasks: tasks.status === "fulfilled" ? tasks.value.items : null,
        projects: projects.status === "fulfilled" ? projects.value.items : null,
        notifications: notifications.status === "fulfilled" ? notifications.value.items : null,
        briefs: briefPage ? briefPage.items : null,
        briefsCapped: Boolean(briefPage?.next_cursor),
        tickets: tickets.status === "fulfilled" ? tickets.value.items : null,
      });
      setLoading(false);
    }

    void loadAll();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRegenerate() {
    setRegenerating(true);
    setError(null);
    try {
      setBrief(await briefsApi.regenerate());
    } catch (err) {
      setError(errorMessage(err, t("dashboard.genericGenerateError")));
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div>
      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}
      <DashboardOverview
        data={data}
        brief={brief}
        loading={loading}
        canRegenerate={canRegenerate}
        regenerating={regenerating}
        onRegenerate={handleRegenerate}
      />
    </div>
  );
}
