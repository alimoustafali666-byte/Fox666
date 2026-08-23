"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, formatDateTime } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import {
  CATEGORY_LABEL_KEYS,
  PRIORITY_LABEL_KEYS,
  PRIORITY_TONE,
  STATUS_LABEL_KEYS,
  STATUS_TONE,
} from "@/components/support/labels";
import type { SupportTicketDetail } from "@/lib/types";
import styles from "../../Support.module.css";

export default function SupportTicketDetailPage() {
  const params = useParams<{ id: string }>();
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";

  const [ticket, setTicket] = useState<SupportTicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [replying, setReplying] = useState(false);
  const [closing, setClosing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await supportApi.getTicket(params.id);
      setTicket(result);
    } catch (err) {
      setError(errorMessage(err, t("support.ticketDetail.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleReply(event: FormEvent) {
    event.preventDefault();
    const trimmed = reply.trim();
    if (!trimmed || !ticket) return;
    setReplying(true);
    setError(null);
    try {
      await supportApi.addComment(ticket.id, trimmed);
      setReply("");
      await load();
    } catch (err) {
      setError(errorMessage(err, t("support.ticketDetail.genericReplyError")));
    } finally {
      setReplying(false);
    }
  }

  async function handleClose() {
    if (!ticket) return;
    if (!window.confirm(t("support.ticketDetail.confirmClose"))) return;
    setClosing(true);
    setError(null);
    try {
      const updated = await supportApi.updateTicketStatus(ticket.id, "closed");
      setTicket({ ...ticket, status: updated.status, resolved_at: updated.resolved_at });
    } catch (err) {
      setError(errorMessage(err, t("support.ticketDetail.genericCloseError")));
    } finally {
      setClosing(false);
    }
  }

  if (loading) return <LoadingBlock label={t("support.ticketDetail.genericLoadError")} />;

  if (!ticket) {
    return (
      <div>
        <Link href="/support/tickets" className={styles.backLink}>
          {backArrow} {t("support.ticketDetail.backLink")}
        </Link>
        <ErrorBanner message={error ?? t("support.ticketDetail.notFound")} />
      </div>
    );
  }

  const isClosed = ticket.status === "closed";

  return (
    <div>
      <Link href="/support/tickets" className={styles.backLink}>
        {backArrow} {t("support.ticketDetail.backLink")}
      </Link>

      <PageHeader
        title={ticket.subject}
        description={`${t("support.ticketDetail.referenceLabel")}: ${ticket.reference_code}`}
        actions={
          <>
            <Badge tone={PRIORITY_TONE[ticket.priority]}>{t(PRIORITY_LABEL_KEYS[ticket.priority])}</Badge>
            <Badge tone={STATUS_TONE[ticket.status]} dot>
              {t(STATUS_LABEL_KEYS[ticket.status])}
            </Badge>
          </>
        }
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div style={{ marginBottom: "var(--space-4)" }}>
        <Card>
          <CardHeader title={t("support.ticketDetail.descriptionTitle")} subtitle={t(CATEGORY_LABEL_KEYS[ticket.category])} />
          <CardBody>
            <p className={styles.articleBody}>{ticket.description}</p>
            <div style={{ marginTop: "var(--space-4)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
              {t("support.ticketDetail.createdLabel")}: {formatDateTime(locale, ticket.created_at)}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title={t("support.ticketDetail.commentsTitle")}
          actions={
            !isClosed ? (
              <Button size="sm" variant="secondary" onClick={handleClose} loading={closing}>
                {closing ? t("support.ticketDetail.closing") : t("support.ticketDetail.closeButton")}
              </Button>
            ) : undefined
          }
        />
        <CardBody>
          {ticket.comments.length === 0 ? (
            <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              {t("support.ticketDetail.noCommentsYet")}
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {ticket.comments.map((comment) => (
                <div
                  key={comment.id}
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    background: "var(--color-surface-subtle)",
                  }}
                >
                  <p className={styles.articleBody}>{comment.body}</p>
                  <div style={{ marginTop: 6, fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                    {formatDate(locale, comment.created_at)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {isClosed ? (
            <p style={{ marginTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              {t("support.ticketDetail.closedNote")}
            </p>
          ) : (
            <form onSubmit={handleReply} style={{ marginTop: "var(--space-4)" }}>
              <div className={styles.assistantComposerRow}>
                <div className={styles.assistantComposerInput}>
                  <Textarea
                    placeholder={t("support.ticketDetail.replyPlaceholder")}
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    rows={2}
                    disabled={replying}
                    maxLength={5000}
                  />
                </div>
                <Button type="submit" loading={replying} disabled={!reply.trim()}>
                  {replying ? t("support.ticketDetail.replying") : t("support.ticketDetail.replyButton")}
                </Button>
              </div>
            </form>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

