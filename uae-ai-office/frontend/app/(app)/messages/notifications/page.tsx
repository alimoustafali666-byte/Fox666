"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { collaborationApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDateTime, type TranslationKey } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import clsx from "@/components/ui/clsx";
import { BellIcon, InsightIcon, MessagesIcon, PulseIcon, TasksIcon } from "@/components/layout/icons";
import {
  InfoList,
  InfoRow,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspacePanel,
  WorkspaceScroller,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
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

  // Counted off what is currently loaded -- the panel describes this view,
  // not the account's whole notification history.
  const unreadCount = useMemo(() => items.filter((n) => !n.read_at).length, [items]);

  const byType = useMemo(() => {
    const counts = new Map<CollaborationNotificationType, number>();
    for (const item of items) counts.set(item.type, (counts.get(item.type) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [items]);

  return (
    <WorkspaceScroller module="messages">
      <WorkspaceHero
        accent="violet"
        badge={t("workspace.notifications.badge")}
        icon={<BellIcon />}
        title={t("messages.notifications.title")}
        description={t("workspace.notifications.description")}
        actions={
          <>
            <Button size="sm" variant="secondary" onClick={handleMarkAllRead}>
              {t("messages.notifications.markAllRead")}
            </Button>
            <label className={styles.toggle}>
              <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
              {t("messages.notifications.unreadOnlyToggle")}
            </label>
          </>
        }
        metrics={[
          {
            label: t("workspace.notifications.metrics.loadedLabel"),
            value: loading ? "—" : items.length,
            hint: t("workspace.notifications.metrics.loadedHint"),
            icon: <BellIcon />,
          },
          {
            label: t("workspace.notifications.metrics.unreadLabel"),
            value: loading ? "—" : unreadCount,
            hint: t("workspace.notifications.metrics.unreadHint"),
            icon: <PulseIcon />,
          },
          {
            label: t("workspace.notifications.metrics.typesLabel"),
            value: loading ? "—" : byType.length,
            hint: t("workspace.notifications.metrics.typesHint"),
            icon: <InsightIcon />,
          },
        ]}
      />

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="magenta"
            icon={<BellIcon />}
            title={t("messages.notifications.title")}
            subtitle={unreadOnly ? t("messages.notifications.unreadOnlyToggle") : undefined}
            tight
          >
      {loading ? (
        <LoadingBlock />
      ) : items.length === 0 ? (
        <ZeroState
          accent="magenta"
          icon={<BellIcon />}
          title={unreadOnly ? t("workspace.notifications.emptyUnreadTitle") : t("workspace.notifications.emptyTitle")}
          text={unreadOnly ? t("workspace.notifications.emptyUnreadText") : t("workspace.notifications.emptyText")}
          actions={
            unreadOnly ? (
              <Button size="sm" variant="secondary" onClick={() => setUnreadOnly(false)}>
                {t("messages.notifications.unreadOnlyToggle")}
              </Button>
            ) : (
              <Link href="/messages" className={buttonClassName("primary", "sm")}>
                {t("messages.sidebarTitle")}
              </Link>
            )
          }
        />
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
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="violet"
            icon={<InsightIcon />}
            title={t("workspace.notifications.typesTitle")}
            subtitle={t("workspace.notifications.typesSubtitle")}
            tight
          >
            {loading ? (
              <LoadingBlock />
            ) : byType.length === 0 ? (
              <ZeroState accent="violet" icon={<InsightIcon />} title={t("workspace.notifications.emptyTitle")} />
            ) : (
              <InfoList>
                {byType.map(([type, count]) => (
                  <InfoRow
                    key={type}
                    accent="violet"
                    icon={type.startsWith("task") ? <TasksIcon /> : <MessagesIcon />}
                    label={t(TYPE_KEY[type])}
                    value={count}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspaceScroller>
  );
}

