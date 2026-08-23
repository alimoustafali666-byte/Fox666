"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { ApiError, briefsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock, Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { BriefContent } from "@/components/brief/BriefContent";
import { BriefTasksPanel } from "@/components/tasks/BriefTasksPanel";
import clsx from "@/components/ui/clsx";
import type { DailyBriefPublic, DailyBriefSummary } from "@/lib/types";
import styles from "./Brief.module.css";

export default function BriefPage() {
  const { role } = useAuth();
  const { t, locale } = useTranslation();
  const canRegenerate = role === "owner" || role === "admin" || role === "manager";

  const formatLongDate = useCallback(
    (dateStr: string) => formatDate(locale, dateStr, { weekday: "long", year: "numeric", month: "long", day: "numeric" }),
    [locale]
  );

  const [viewDate, setViewDate] = useState<string>("latest");
  const [brief, setBrief] = useState<DailyBriefPublic | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(true);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const [history, setHistory] = useState<DailyBriefSummary[]>([]);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false);

  const loadBrief = useCallback(
    async (date: string) => {
      setLoadingBrief(true);
      setBriefError(null);
      try {
        const result = date === "latest" ? await briefsApi.getLatest() : await briefsApi.getByDate(date);
        setBrief(result);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setBrief(null);
        } else {
          setBriefError(errorMessage(err, t("brief.genericLoadError")));
        }
      } finally {
        setLoadingBrief(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const page = await briefsApi.list({ limit: 15 });
      setHistory(page.items);
      setHistoryCursor(page.next_cursor);
    } catch {
      // History is a secondary panel -- a failure here shouldn't block
      // the primary brief view, so it fails silently into an empty list.
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    loadBrief("latest");
    loadHistory();
  }, [loadBrief, loadHistory]);

  async function loadMoreHistory() {
    if (!historyCursor) return;
    setLoadingMoreHistory(true);
    try {
      const page = await briefsApi.list({ limit: 15, cursor: historyCursor });
      setHistory((prev) => [...prev, ...page.items]);
      setHistoryCursor(page.next_cursor);
    } finally {
      setLoadingMoreHistory(false);
    }
  }

  function handleSelectDate(date: string) {
    setViewDate(date);
    loadBrief(date);
  }

  async function handleRegenerate() {
    setRegenerating(true);
    setBriefError(null);
    try {
      const updated = await briefsApi.regenerate();
      setBrief(updated);
      setViewDate("latest");
      loadHistory();
    } catch (err) {
      setBriefError(errorMessage(err, t("brief.genericGenerateError")));
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title={t("brief.title")}
        description={t("brief.description")}
        actions={
          canRegenerate ? (
            <Button onClick={handleRegenerate} loading={regenerating}>
              {regenerating
                ? t("brief.generating")
                : viewDate === "latest" && !brief
                  ? t("brief.generateButton")
                  : t("brief.regenerateButton")}
            </Button>
          ) : undefined
        }
      />

      <div className={styles.layout}>
        <Card>
          <CardHeader
            title={
              viewDate === "latest"
                ? brief
                  ? formatLongDate(brief.brief_date)
                  : t("brief.latestBriefFallbackTitle")
                : formatLongDate(viewDate)
            }
          />
          <CardBody>
            {briefError ? <ErrorBanner message={briefError} /> : null}
            {loadingBrief ? (
              <LoadingBlock label={t("brief.loadingBrief")} />
            ) : brief ? (
              <BriefContent brief={brief} />
            ) : !briefError ? (
              <EmptyState
                title={t("brief.noBriefTitle")}
                description={canRegenerate ? t("brief.noBriefManager") : t("brief.noBriefMember")}
              />
            ) : null}
          </CardBody>
        </Card>

        <div className={styles.sidebar}>
          <BriefTasksPanel />

          <Card>
            <CardHeader title={t("brief.historyTitle")} subtitle={t("brief.historySubtitle")} />
            <CardBody tight>
              {loadingHistory ? (
                <LoadingBlock label={t("brief.loadingHistory")} />
              ) : history.length === 0 ? (
                <div style={{ padding: "var(--space-5)" }}>
                  <EmptyState title={t("brief.noHistoryTitle")} description={t("brief.noHistoryDescription")} />
                </div>
              ) : (
                <div style={{ padding: "var(--space-2)" }}>
                  {history.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleSelectDate(item.brief_date)}
                      className={clsx(styles.historyItem, viewDate === item.brief_date && styles.historyItemActive)}
                      style={{ width: "100%", textAlign: "start", background: "transparent", cursor: "pointer" }}
                    >
                      <div className={styles.historyDate}>{formatLongDate(item.brief_date)}</div>
                      <div className={styles.historySummary}>{item.summary}</div>
                    </button>
                  ))}
                  {historyCursor ? (
                    <div style={{ padding: "var(--space-3)", textAlign: "center" }}>
                      <Button size="sm" variant="ghost" onClick={loadMoreHistory} loading={loadingMoreHistory}>
                        {loadingMoreHistory ? <Spinner size="sm" /> : t("common.loadMore")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

