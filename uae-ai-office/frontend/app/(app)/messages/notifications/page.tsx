"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { collaborationApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDateTime, type TranslationKey } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import clsx from "@/components/ui/clsx";
import type { CollaborationNotificationPublic, CollaborationNotificationType } from "@/lib/types";
import styles from "./Notifications.module.css";

const TYPE_KEY: Record<CollaborationNotificationType, TranslationKey> = {
  new_message: "messages.notifications.types.new_message",
  mention: "messages.notifications.types.mention",
  reply: "messages.notifications.types.reply",
  group_added: "messages.notifications.types.group_added",
  group_removed: "messages.notifications.types.group_removed",
  project_channel_activity: "messages.notifications.types.project_channel_activity",
  support_ticket_update: "messages.notifications.types.support_ticket_update",
  task_assigned: "messages.notifications.types.task_assigned",
  task_reassigned: "messages.notifications.types.task_reassigned",
  task_comment: "messages.notifications.types.task_comment",
};

export default function NotificationsPage() {
  const { t, locale } = useTranslation();
  const [items, setItems] = useState<CollaborationNotificationPublic[]>([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await collaborationApi.listNotifications({ unread_only: unreadOnly, limit: 50 });
      setItems(page.items);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadOnly]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleMarkRead(id: string) {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
    try {
      await collaborationApi.markNotificationRead(id);
    } catch {
      await load();
    }
  }

  async function handleMarkAllRead() {
    const previous = items;
    setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    try {
      await collaborationApi.markAllNotificationsRead();
    } catch {
      setItems(previous);
    }
  }

  return (
    <div style={{ padding: "var(--space-6)", overflowY: "auto", height: "100%" }}>
      <div className={styles.header}>
        <h2 className={styles.title}>{t("messages.notifications.title")}</h2>
        <div className={styles.actions}>
          <label className={styles.toggle}>
            <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
            {t("messages.notifications.unreadOnlyToggle")}
          </label>
          <Button size="sm" variant="secondary" onClick={handleMarkAllRead}>
            {t("messages.notifications.markAllRead")}
          </Button>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      {loading ? (
        <LoadingBlock />
      ) : items.length === 0 ? (
        <EmptyState title={t("messages.notifications.empty")} />
      ) : (
        <div className={styles.list}>
          {items.map((n) => {
            const content = (
              <div className={clsx(styles.item, !n.read_at && styles.itemUnread)}>
                <div className={styles.itemTop}>
                  <span className={styles.itemType}>{t(TYPE_KEY[n.type])}</span>
                  <span className={styles.itemDate}>{formatDateTime(locale, n.created_at)}</span>
                </div>
                <div className={styles.itemTitle}>{n.title}</div>
                {n.body ? <div className={styles.itemBody}>{n.body}</div> : null}
              </div>
            );
            const href = n.task_id ? `/tasks/${n.task_id}` : n.conversation_id ? `/messages/${n.conversation_id}` : null;
            return (
              <div key={n.id} className={styles.row} onClick={() => !n.read_at && handleMarkRead(n.id)}>
                {href ? <Link href={href}>{content}</Link> : content}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

