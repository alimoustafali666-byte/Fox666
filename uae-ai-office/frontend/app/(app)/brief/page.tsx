"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError, briefsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock, Spinner } from "@/components/ui/Spinner";
import { BriefContent } from "@/components/brief/BriefContent";
import { BriefStatsRow } from "@/components/brief/BriefStatsRow";
import { BriefTasksPanel } from "@/components/tasks/BriefTasksPanel";
import {
  BriefIcon,
  CalendarIcon,
  ClockIcon,
  InsightIcon,
  SettingsIcon,
  ShieldIcon,
  TargetIcon,
} from "@/components/layout/icons";
import {
  ChipLink,
  ChipRow,
  Disclosure,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
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

  // Counted off the brief already loaded -- nothing is generated here.
  const attention = useMemo(() => {
    if (!brief) return null;
    return brief.items.filter((item) => item.category === "pending_action" || item.category === "potential_issue").length;
  }, [brief]);

  const panelTitle =
    viewDate === "latest"
      ? brief
        ? formatLongDate(brief.brief_date)
        : t("brief.latestBriefFallbackTitle")
      : formatLongDate(viewDate);

  return (
    <WorkspacePage module="brief">
      <WorkspaceHero
        accent="violet"
        compact
        badge={t("workspace.brief.badge")}
        icon={<BriefIcon />}
        title={t("brief.title")}
        description={t("workspace.brief.description")}
        actions={
          <>
            {canRegenerate ? (
              <Button onClick={handleRegenerate} loading={regenerating}>
                {regenerating
                  ? t("brief.generating")
                  : viewDate === "latest" && !brief
                    ? t("brief.generateButton")
                    : t("brief.regenerateButton")}
              </Button>
            ) : null}
            <ChipRow>
              <ChipLink accent="blue" href="/tasks" icon={<TargetIcon />}>
                {t("tasks.myTasksTitle")}
              </ChipLink>
              <ChipLink accent="magenta" href="/settings" icon={<SettingsIcon />}>
                {t("workspace.brief.scheduleCta")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.brief.metrics.latestLabel"),
            value: loadingBrief ? "—" : brief ? formatDate(locale, brief.brief_date, { month: "short", day: "numeric" }) : t("workspace.brief.metrics.noneValue"),
            hint: t("workspace.brief.metrics.latestHint"),
            icon: <CalendarIcon />,
          },
          {
            label: t("workspace.brief.contains.prioritiesTitle"),
            value: attention === null ? "—" : attention,
            hint: t("workspace.brief.metrics.prioritiesHint"),
            icon: <TargetIcon />,
          },
          {
            label: t("workspace.brief.metrics.historyLabel"),
            value: loadingHistory ? "—" : history.length,
            hint: t("workspace.brief.metrics.historyHint"),
            icon: <ClockIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="violet" icon={<BriefIcon />} title={panelTitle}>
            {briefError ? <ErrorBanner message={briefError} /> : null}
            {loadingBrief ? (
              <LoadingBlock label={t("brief.loadingBrief")} />
            ) : brief ? (
              <>
                <BriefStatsRow brief={brief} />
                <BriefContent brief={brief} />
              </>
            ) : !briefError ? (
              <ZeroState
                accent="violet"
                icon={<BriefIcon />}
                title={t("workspace.brief.emptyTitle")}
                text={canRegenerate ? t("workspace.brief.emptyManagerText") : t("workspace.brief.emptyMemberText")}
                actions={
                  canRegenerate ? (
                    <Button size="sm" onClick={handleRegenerate} loading={regenerating}>
                      {t("brief.generateButton")}
                    </Button>
                  ) : undefined
                }
              />
            ) : null}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <BriefTasksPanel />

          <WorkspacePanel
            accent="magenta"
            icon={<ClockIcon />}
            title={t("brief.historyTitle")}
            subtitle={t("brief.historySubtitle")}
            tight
          >
            {loadingHistory ? (
              <LoadingBlock label={t("brief.loadingHistory")} />
            ) : history.length === 0 ? (
              <ZeroState
                accent="magenta"
                icon={<ClockIcon />}
                title={t("workspace.brief.historyEmptyTitle")}
                text={t("workspace.brief.historyEmptyText")}
              />
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
          </WorkspacePanel>

          {/* The scheduling entry point is already a chip in the hero, so the
              panel that repeated it here has been dropped rather than shown
              twice; the explanation moves in beside the rest. */}
          <Disclosure accent="violet" icon={<InsightIcon />} label={t("workspace.brief.containsTitle")}>
            <StepList
              accent="magenta"
              steps={[
                { title: t("workspace.brief.contains.summaryTitle"), description: t("workspace.brief.contains.summaryDescription") },
                { title: t("workspace.brief.contains.prioritiesTitle"), description: t("workspace.brief.contains.prioritiesDescription") },
                { title: t("workspace.brief.contains.risksTitle"), description: t("workspace.brief.contains.risksDescription") },
                { title: t("workspace.brief.contains.activityTitle"), description: t("workspace.brief.contains.activityDescription") },
                { title: t("workspace.brief.scheduleTitle"), description: t("workspace.brief.scheduleText") },
              ]}
            />
          </Disclosure>

          <WorkspaceNote accent="violet" icon={<ShieldIcon />}>
            {t("workspace.brief.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
