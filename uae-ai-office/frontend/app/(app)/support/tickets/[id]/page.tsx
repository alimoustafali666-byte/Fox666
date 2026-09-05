"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, formatDateTime } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  InfoList,
  InfoRow,
  SkeletonRows,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
import {
  BrainIcon,
  ClockIcon,
  DocumentsIcon,
  GaugeIcon,
  HelpIcon,
  MessagesIcon,
  ShieldIcon,
  TicketIcon,
} from "@/components/layout/icons";
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

  if (loading) {
    return (
      <WorkspacePage module="support">
        <Link href="/support/tickets" className={styles.backLink}>
          {backArrow} {t("support.ticketDetail.backLink")}
        </Link>
        <WorkspacePanel accent="magenta" icon={<TicketIcon />} title={t("support.tickets.title")}>
          <SkeletonRows count={6} />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  if (!ticket) {
    return (
      <WorkspacePage module="support">
        <Link href="/support/tickets" className={styles.backLink}>
          {backArrow} {t("support.ticketDetail.backLink")}
        </Link>
        <ErrorBanner message={error ?? t("support.ticketDetail.notFound")} />
      </WorkspacePage>
    );
  }

  const isClosed = ticket.status === "closed";

  return (
    <WorkspacePage module="support">
      <Link href="/support/tickets" className={styles.backLink}>
        {backArrow} {t("support.ticketDetail.backLink")}
      </Link>

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="green"
        badge={t("workspace.ticketDetail.badge")}
        icon={<TicketIcon />}
        title={ticket.subject}
        description={`${t("support.ticketDetail.referenceLabel")}: ${ticket.reference_code}`}
        actions={
          <>
            <Badge tone={PRIORITY_TONE[ticket.priority]}>{t(PRIORITY_LABEL_KEYS[ticket.priority])}</Badge>
            <Badge tone={STATUS_TONE[ticket.status]} dot>
              {t(STATUS_LABEL_KEYS[ticket.status])}
            </Badge>
            {!isClosed ? (
              <Button size="md" variant="secondary" onClick={handleClose} loading={closing}>
                {closing ? t("support.ticketDetail.closing") : t("support.ticketDetail.closeButton")}
              </Button>
            ) : null}
          </>
        }
        metrics={[
          {
            label: t("workspace.ticketDetail.metrics.statusLabel"),
            value: <span style={{ fontSize: 15 }}>{t(STATUS_LABEL_KEYS[ticket.status])}</span>,
            hint: t("workspace.ticketDetail.metrics.statusHint"),
            icon: <ShieldIcon />,
          },
          {
            label: t("workspace.ticketDetail.metrics.priorityLabel"),
            value: <span style={{ fontSize: 15 }}>{t(PRIORITY_LABEL_KEYS[ticket.priority])}</span>,
            hint: t("workspace.ticketDetail.metrics.priorityHint"),
            icon: <GaugeIcon />,
          },
          {
            label: t("workspace.ticketDetail.metrics.repliesLabel"),
            value: ticket.comments.length,
            hint: t("workspace.ticketDetail.metrics.repliesHint"),
            icon: <MessagesIcon />,
          },
          {
            label: t("workspace.ticketDetail.metrics.createdLabel"),
            value: <span style={{ fontSize: 15 }}>{formatDate(locale, ticket.created_at)}</span>,
            hint: t("workspace.ticketDetail.metrics.createdHint"),
            icon: <ClockIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="magenta"
            icon={<TicketIcon />}
            title={t("support.ticketDetail.descriptionTitle")}
            subtitle={t(CATEGORY_LABEL_KEYS[ticket.category])}
          >
            <p className={styles.articleBody}>{ticket.description}</p>
            <div style={{ marginTop: "var(--space-4)", fontSize: "var(--font-size-xs)", color: "var(--ai-muted)" }}>
              {t("support.ticketDetail.createdLabel")}: {formatDateTime(locale, ticket.created_at)}
            </div>
          </WorkspacePanel>

          <WorkspacePanel accent="cyan" icon={<MessagesIcon />} title={t("support.ticketDetail.commentsTitle")}>
            {ticket.comments.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<MessagesIcon />}
                title={t("support.ticketDetail.noCommentsYet")}
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {ticket.comments.map((comment) => (
                  <div
                    key={comment.id}
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      borderRadius: "var(--ai-r-md)",
                      border: "1px solid var(--ai-line)",
                      background: "var(--ai-inset)",
                    }}
                  >
                    <p className={styles.articleBody}>{comment.body}</p>
                    <div style={{ marginTop: 6, fontSize: "var(--font-size-xs)", color: "var(--ai-muted)" }}>
                      {formatDate(locale, comment.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {isClosed ? (
              <p style={{ marginTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--ai-muted)" }}>
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
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel accent="violet" icon={<HelpIcon />} title={t("workspace.tickets.beforeTitle")} tight>
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

          <WorkspacePanel accent="blue" icon={<TicketIcon />} title={t("support.tickets.title")} tight>
            <div style={{ padding: "var(--space-3)" }}>
              <Link href="/support/tickets" className={buttonClassName("secondary", "sm", true)}>
                {t("support.tickets.title")}
              </Link>
            </div>
          </WorkspacePanel>

          <WorkspaceNote accent="magenta" icon={<ShieldIcon />}>
            {t("workspace.ticketDetail.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
