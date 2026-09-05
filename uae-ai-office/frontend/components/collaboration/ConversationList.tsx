"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCollaboration } from "./CollaborationContext";
import { useTranslation, formatDate, type TranslationKey } from "@/lib/i18n";
import { buttonClassName } from "@/components/ui/Button";
import { BellIcon, ChevronRightIcon, MessagesIcon, SearchIcon } from "@/components/layout/icons";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import clsx from "@/components/ui/clsx";
import type { ChatConversationPublic, ConversationType } from "@/lib/types";
import styles from "@/app/(app)/messages/MessagesLayout.module.css";

function conversationTitle(
  conversation: ChatConversationPublic,
  directPeerNames: Record<string, string>,
  t: (key: TranslationKey) => string
): string {
  if (conversation.type === "direct") {
    return directPeerNames[conversation.id] || t("messages.untitledDirect");
  }
  return conversation.name || t("messages.untitledGroup");
}

const TYPE_KEY: Record<ConversationType, TranslationKey> = {
  direct: "messages.typeLabels.direct",
  group: "messages.typeLabels.group",
  project_channel: "messages.typeLabels.project_channel",
};

export function ConversationList() {
  const { conversations, loading, error, refresh, directPeerNames } = useCollaboration();
  const params = useParams<{ conversationId?: string }>();
  const { t, locale } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [filter, setFilter] = useState("");

  // Narrows the threads already loaded into the rail. Purely client-side, so
  // typing never issues a request and never changes what the rail is allowed
  // to show.
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return conversations;
    return conversations.filter((conversation) =>
      conversationTitle(conversation, directPeerNames, t).toLowerCase().includes(needle)
    );
  }, [conversations, directPeerNames, filter, t]);

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <div className={styles.sidebarTitle}>
          {t("messages.sidebarTitle")}
          {conversations.length > 0 ? <span className={styles.sidebarCount}>{conversations.length}</span> : null}
        </div>
        <div className={styles.newMenu}>
          <button
            type="button"
            className={buttonClassName("secondary", "sm")}
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            + {t("messages.newButton")}
          </button>
          {menuOpen ? (
            <div className={styles.newMenuList} role="menu">
              <Link href="/messages/new?type=direct" className={styles.newMenuItem} onClick={() => setMenuOpen(false)}>
                {t("messages.newDirect")}
              </Link>
              <Link href="/messages/new?type=group" className={styles.newMenuItem} onClick={() => setMenuOpen(false)}>
                {t("messages.newGroup")}
              </Link>
              <Link href="/messages/new?type=project_channel" className={styles.newMenuItem} onClick={() => setMenuOpen(false)}>
                {t("messages.newChannel")}
              </Link>
            </div>
          ) : null}
        </div>
      </div>

      <Link href="/messages/notifications" className={styles.notificationsLink}>
        <BellIcon />
        <span className={styles.notificationsLabel}>{t("messages.notificationsLink")}</span>
        <ChevronRightIcon />
      </Link>

      {conversations.length > 0 ? (
        <div className={styles.railSearch}>
          <SearchIcon />
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder={t("messages.filterPlaceholder")}
            aria-label={t("messages.filterPlaceholder")}
          />
        </div>
      ) : null}
      {error ? <div style={{ padding: "0 var(--space-3) var(--space-3)" }}><ErrorBanner message={error} /><button type="button" className={buttonClassName("ghost", "sm")} onClick={() => void refresh()}>{t("common.loadMore")}</button></div> : null}

      <div className={styles.list}>
        {loading ? (
          <div style={{ padding: 16 }}>
            <Spinner size="sm" />
          </div>
        ) : conversations.length === 0 ? (
          <div className={styles.railEmpty}>
            <span className={styles.railEmptyIcon} aria-hidden="true"><MessagesIcon /></span>
            {t("messages.noConversations")}
          </div>
        ) : visible.length === 0 ? (
          <div className={styles.railEmpty}>
            <span className={styles.railEmptyIcon} aria-hidden="true"><SearchIcon /></span>
            {t("messages.filterEmpty")}
          </div>
        ) : (
          visible.map((conversation) => {
            const active = params.conversationId === conversation.id;
            const title = conversationTitle(conversation, directPeerNames, t);
            return (
              <Link
                key={conversation.id}
                href={`/messages/${conversation.id}`}
                className={clsx(styles.item, active && styles.itemActive)}
              >
                <div className={styles.itemBody}>
                  <div className={styles.itemTitleRow}>
                    <span className={styles.itemTitle}>{title}</span>
                  </div>
                  <div className={styles.itemMeta}>
                    {t(TYPE_KEY[conversation.type])} · {formatDate(locale, conversation.updated_at, { month: "short", day: "numeric" })}
                  </div>
                </div>
                {conversation.unread_count > 0 ? (
                  <span className={styles.unreadBadge}>{conversation.unread_count > 99 ? "99+" : conversation.unread_count}</span>
                ) : null}
              </Link>
            );
          })
        )}
      </div>
    </aside>
  );
}

