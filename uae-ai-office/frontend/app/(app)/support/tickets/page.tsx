"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { CATEGORY_LABEL_KEYS, PRIORITY_LABEL_KEYS, PRIORITY_TONE, STATUS_LABEL_KEYS, STATUS_TONE } from "@/components/support/labels";
import { SUPPORT_TICKET_STATUSES, type SupportTicketPublic } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

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
    <div>
      <PageHeader
        title={t("support.tickets.title")}
        description={t("support.tickets.description")}
        actions={
          <Button onClick={() => router.push("/support/tickets/new")}>
            {t("support.tickets.newTicketButton")}
          </Button>
        }
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

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
      </div>

      <Card>
        {loading ? (
          <LoadingBlock label={t("support.tickets.loadingList")} />
        ) : tickets.length === 0 ? (
          <EmptyState
            title={t("support.tickets.noTicketsTitle")}
            description={t("support.tickets.noTicketsDescription")}
            action={
              <Button size="sm" onClick={() => router.push("/support/tickets/new")}>
                {t("support.tickets.newTicketButton")}
              </Button>
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
                <span className={tableStyles.muted}>{t("support.tickets.showingCount", { count: tickets.length })}</span>
                <Button size="sm" variant="secondary" onClick={loadMore} loading={loadingMore}>
                  {loadingMore ? t("common.loading") : t("common.loadMore")}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Card>

      <div style={{ marginTop: "var(--space-4)" }}>
        <Link href="/support" style={{ fontSize: "var(--font-size-sm)", fontWeight: 600 }}>
          {t("support.article.backLink")}
        </Link>
      </div>
    </div>
  );
}

