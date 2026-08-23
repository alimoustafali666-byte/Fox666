"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError, briefsApi, reportsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { BriefContent } from "@/components/brief/BriefContent";
import { BriefStatsRow } from "@/components/brief/BriefStatsRow";
import { TaskSummaryTiles } from "@/components/tasks/TaskSummaryTiles";
import { ExecutiveSummary } from "@/components/dashboard/ExecutiveSummary";
import { CompanyLogo } from "@/components/layout/CompanyLogo";
import { AskIcon, DocumentsIcon } from "@/components/layout/icons";
import type { DailyBriefPublic, DashboardSummaryResponse } from "@/lib/types";
import styles from "./Dashboard.module.css";

export default function DashboardPage() {
  const { user, role, company } = useAuth();
  const { t, dir, locale } = useTranslation();
  const canRegenerate = role === "owner" || role === "admin" || role === "manager";
  const forwardArrow = dir === "rtl" ? "←" : "→";

  const [brief, setBrief] = useState<DailyBriefPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const latest = await briefsApi.getLatest();
      setBrief(latest);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setBrief(null);
      } else {
        setError(errorMessage(err, t("dashboard.genericLoadError")));
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    reportsApi
      .dashboardSummary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));
  }, []);

  async function handleRegenerate() {
    setRegenerating(true);
    setError(null);
    try {
      const updated = await briefsApi.regenerate();
      setBrief(updated);
    } catch (err) {
      setError(errorMessage(err, t("dashboard.genericGenerateError")));
    } finally {
      setRegenerating(false);
    }
  }

  const firstName = user?.full_name?.split(" ")[0] || user?.email;

  return (
    <div>
      <PageHeader title={t("dashboard.welcomeBack", { name: firstName ?? "" })} description={t("dashboard.subtitle")} />

      {company ? (
        <div className={styles.companyBanner}>
          <CompanyLogo hasLogo={company.has_logo} size={40} />
          <div>
            <div className={styles.companyBannerName}>{company.name}</div>
            <div className={styles.companyBannerMeta}>
              {company.country} · {company.timezone}
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className={styles.sectionLabel}>{t("dashboard.myTasksSummary")}</div>
      <TaskSummaryTiles />

      {summaryLoading ? (
        <>
          <div className={styles.sectionLabel}>{t("dashboard.exec.sectionLabel")}</div>
          <div className={styles.summarySkeletonGrid}>
            {[0, 1, 2, 3].map((i) => (
              <Card key={i}>
                <CardBody>
                  <SkeletonRows rows={2} />
                </CardBody>
              </Card>
            ))}
          </div>
        </>
      ) : summary ? (
        <>
          <div className={styles.sectionLabel}>{t("dashboard.exec.sectionLabel")}</div>
          <ExecutiveSummary summary={summary} />
        </>
      ) : null}

      {brief ? (
        <>
          <div className={styles.sectionLabel}>{t("dashboard.attentionSummary")}</div>
          <BriefStatsRow brief={brief} />
        </>
      ) : null}

      <div className={styles.grid}>
        <Card>
          <CardHeader
            title={t("dashboard.todaysBrief")}
            subtitle={brief ? formatDate(locale, brief.brief_date, { weekday: "long", year: "numeric", month: "long", day: "numeric" }) : undefined}
            actions={
              canRegenerate ? (
                <Button size="sm" variant="secondary" onClick={handleRegenerate} loading={regenerating}>
                  {regenerating ? t("dashboard.generating") : brief ? t("dashboard.regenerate") : t("dashboard.generateBrief")}
                </Button>
              ) : undefined
            }
          />
          <CardBody>
            {loading ? (
              <LoadingBlock label={t("dashboard.loadingBrief")} />
            ) : brief ? (
              <BriefContent brief={brief} />
            ) : (
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                {canRegenerate ? t("dashboard.noBriefManager") : t("dashboard.noBriefMember")}
              </p>
            )}
            {brief ? (
              <div style={{ marginTop: "var(--space-5)" }}>
                <Link href="/brief" style={{ fontSize: "var(--font-size-sm)", fontWeight: 600 }}>
                  {t("dashboard.viewFullHistory")} {forwardArrow}
                </Link>
              </div>
            ) : null}
          </CardBody>
        </Card>

        <div className={styles.quickActions}>
          <Card>
            <CardBody>
              <Link href="/ask" className={styles.quickAction}>
                <span className={styles.quickActionIcon}>
                  <AskIcon />
                </span>
                <span>
                  <div className={styles.quickActionTitle}>{t("dashboard.askYourBusiness")}</div>
                  <div className={styles.quickActionDescription}>{t("dashboard.askDescription")}</div>
                </span>
              </Link>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Link href="/documents?upload=1" className={styles.quickAction}>
                <span className={styles.quickActionIcon}>
                  <DocumentsIcon />
                </span>
                <span>
                  <div className={styles.quickActionTitle}>{t("dashboard.uploadDocument")}</div>
                  <div className={styles.quickActionDescription}>{t("dashboard.uploadDescription")}</div>
                </span>
              </Link>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

