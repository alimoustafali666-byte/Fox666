"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth, errorMessage } from "@/lib/auth-context";
import { ApiError, briefsApi, reportsApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import type { DailyBriefPublic, DashboardSummaryResponse } from "@/lib/types";

export default function DashboardPage() {
  const { role } = useAuth();
  const { t } = useTranslation();
  const canRegenerate = role === "owner" || role === "admin" || role === "manager";
  const [brief, setBrief] = useState<DailyBriefPublic | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setBrief(await briefsApi.getLatest());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setBrief(null);
      else setError(errorMessage(err, t("dashboard.genericLoadError")));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    reportsApi.dashboardSummary().then(setSummary).catch(() => setSummary(null)).finally(() => setSummaryLoading(false));
  }, []);

  async function handleRegenerate() {
    setRegenerating(true);
    setError(null);
    try { setBrief(await briefsApi.regenerate()); }
    catch (err) { setError(errorMessage(err, t("dashboard.genericGenerateError"))); }
    finally { setRegenerating(false); }
  }

  return <div>
    {error ? <div style={{ marginBottom: "var(--space-4)" }}><ErrorBanner message={error} /></div> : null}
    <DashboardOverview summary={summary} brief={brief} summaryLoading={summaryLoading} canRegenerate={canRegenerate} regenerating={regenerating} onRegenerate={handleRegenerate} />
  </div>;
}
