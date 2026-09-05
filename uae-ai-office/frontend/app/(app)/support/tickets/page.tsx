"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  InfoList,
  InfoRow,
  SkeletonRows,
  StatusLegend,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
  type LegendItem,
} from "@/components/ui/Workspace";
import { BrainIcon, DocumentsIcon, HelpIcon, ShieldIcon, TicketIcon } from "@/components/layout/icons";
import {
  CATEGORY_LABEL_KEYS,
  PRIORITY_LABEL_KEYS,
  PRIORITY_TONE,
  STATUS_LABEL_KEYS,
  STATUS_TONE,
} from "@/components/support/labels";
import { SUPPORT_TICKET_STATUSES, type SupportTicketPublic, type SupportTicketStatus } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

/** Status colours, matched to the accent palette used across the product. */
const STATUS_COLOR: Record<string, string> = {
  open: "#4d8dff",
  in_progress: "#8b6bff",
  waiting_for_user: "#ffa43d",
  resolved: "#2fd48a",
  closed: "#6d7e9d",
};

const OPEN_STATUSES = new Set(["open", "in_progress", "waiting_for_user"]);

export default function SupportTicketsPage() {
  const { t, locale } = useTranslation();
  const router = useRouter();

  const [tickets, setTickets] = useState<SupportTicketPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await supportApi.listTickets({ status: statusFilter || undefined, limit: 20 });
      setTickets(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("support.tickets.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Counted from the tickets actually loaded for the current filter.
  const openCount = useMemo(() => tickets.filter((ticket) => OPEN_STATUSES.has(ticket.status)).length, [tickets]);
  const closedCount = tickets.length - openCount;

  // Doubles as the status filter, so the breakdown is a control rather than
  // a caption. Selecting the active row again clears the filter.
  const statusLegend: LegendItem[] = SUPPORT_TICKET_STATUSES.map((status: SupportTicketStatus) => ({
    label: t(STATUS_LABEL_KEYS[status]),
    description: t(`workspace.tickets.statusDescriptions.${status}` as never),
    color: STATUS_COLOR[status] ?? "#6d7e9d",
    count: loading ? undefined : tickets.filter((ticket) => ticket.status === status).length,
    active: statusFilter === status,
    onSelect: () => setStatusFilter((current) => (current === status ? "" : status)),
  }));

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await supportApi.listTickets({
        status: statusFilter || undefined,
        limit: 20,
        cursor: nextCursor,
      });
      setTickets((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("support.tickets.genericLoadMoreError")));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <WorkspacePage module="support">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="green"
        badge={t("workspace.tickets.badge")}
        icon={<TicketIcon />}
        title={t("support.tickets.title")}
        description={t("workspace.tickets.description")}
        actions={
          <>
            <Link href="/support/tickets/new" className={buttonClassName("primary", "md")}>
              {t("support.tickets.newTicketButton")}
            </Link>
            <Link href="/support" className={buttonClassName("ghost", "md")}>
              {t("support.article.backLink")}
            </Link>
          </>
        }
        metrics={[
          {
            label: t("workspace.tickets.metrics.totalLabel"),
            value: loading ? "—" : tickets.length,
            hint: t("workspace.tickets.metrics.totalHint"),
            icon: <TicketIcon />,
          },
          {
            label: t("workspace.tickets.metrics.openLabel"),
            value: loading ? "—" : openCount,
            hint: t("workspace.tickets.metrics.openHint"),
            icon: <HelpIcon />,
          },
          {
            label: t("workspace.tickets.metrics.resolvedLabel"),
            value: loading ? "—" : closedCount,
            hint: t("workspace.tickets.metrics.resolvedHint"),
            icon: <ShieldIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="magenta" icon={<TicketIcon />} title={t("support.tickets.title")} tight>
            <div className={toolbarStyles.toolbar}>
              <div className={toolbarStyles.field}>
                <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="">{t("support.tickets.allStatuses")}</option>
                  {SUPPORT_TICKET_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {t(STATUS_LABEL_KEYS[status])}
                    </option>
                  ))}
                </Select>
              </div>
              {statusFilter ? (
                <Button size="sm" variant="ghost" onClick={() => setStatusFilter("")}>
                  {t("workspace.tickets.clearFilter")}
                </Button>
              ) : null}
            </div>

            {loading ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={5} />
              </div>
            ) : tickets.length === 0 ? (
              <ZeroState
                accent="magenta"
                icon={<TicketIcon />}
                title={statusFilter ? t("workspace.tickets.emptyFilteredTitle") : t("workspace.tickets.emptyTitle")}
                text={statusFilter ? t("workspace.tickets.emptyFilteredText") : t("workspace.tickets.emptyText")}
                actions={
                  statusFilter ? (
                    <Button size="sm" variant="secondary" onClick={() => setStatusFilter("")}>
                      {t("workspace.tickets.clearFilter")}
                    </Button>
                  ) : (
                    <Link href="/support/tickets/new" className={buttonClassName("primary", "sm")}>
                      {t("support.tickets.newTicketButton")}
                    </Link>
                  )
                }
              />
            ) : (
              <>
                <div className={tableStyles.wrap}>
                  <table className={tableStyles.table}>
                    <thead>
                      <tr>
                        <th>{t("support.tickets.columns.reference")}</th>
                        <th>{t("support.tickets.columns.subject")}</th>
                        <th>{t("support.tickets.columns.category")}</th>
                        <th>{t("support.tickets.columns.priority")}</th>
                        <th>{t("support.tickets.columns.status")}</th>
                        <th>{t("support.tickets.columns.updated")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tickets.map((ticket) => (
                        <tr
                          key={ticket.id}
                          className={tableStyles.clickableRow}
                          onClick={() => router.push(`/support/tickets/${ticket.id}`)}
                        >
                          <td className={tableStyles.muted} dir="ltr" style={{ textAlign: "start" }}>
                            {ticket.reference_code}
                          </td>
                          <td>{ticket.subject}</td>
                          <td className={tableStyles.muted}>{t(CATEGORY_LABEL_KEYS[ticket.category])}</td>
                          <td>
                            <Badge tone={PRIORITY_TONE[ticket.priority]}>{t(PRIORITY_LABEL_KEYS[ticket.priority])}</Badge>
                          </td>
                          <td>
                            <Badge tone={STATUS_TONE[ticket.status]} dot>
                              {t(STATUS_LABEL_KEYS[ticket.status])}
                            </Badge>
                          </td>
                          <td className={tableStyles.muted}>{formatDate(locale, ticket.updated_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {nextCursor ? (
                  <div className={tableStyles.footer}>
                    <span className={tableStyles.muted}>
                      {t("support.tickets.showingCount", { count: tickets.length })}
                    </span>
                    <Button size="sm" variant="secondary" onClick={loadMore} loading={loadingMore}>
                      {loadingMore ? t("common.loading") : t("common.loadMore")}
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="blue"
            icon={<ShieldIcon />}
            title={t("workspace.tickets.statusTitle")}
            subtitle={t("workspace.tickets.statusSubtitle")}
            tight
          >
            <StatusLegend items={statusLegend} total={tickets.length} />
          </WorkspacePanel>

          <WorkspacePanel accent="cyan" icon={<HelpIcon />} title={t("workspace.tickets.beforeTitle")} tight>
            <InfoList>
              <InfoRow
                accent="violet"
                icon={<BrainIcon />}
                href="/support/assistant"
                label={t("workspace.tickets.before.assistantTitle")}
                meta={t("workspace.tickets.before.assistantDescription")}
              />
              <InfoRow
                accent="cyan"
                icon={<DocumentsIcon />}
                href="/support"
                label={t("workspace.tickets.before.articlesTitle")}
                meta={t("workspace.tickets.before.articlesDescription")}
              />
            </InfoList>
          </WorkspacePanel>

          <WorkspaceNote accent="magenta" icon={<ShieldIcon />}>
            {t("workspace.tickets.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
