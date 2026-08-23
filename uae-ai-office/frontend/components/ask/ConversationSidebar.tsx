"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAskConversations } from "./AskConversationsContext";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import clsx from "@/components/ui/clsx";
import styles from "@/app/(app)/ask/AskLayout.module.css";

export function ConversationSidebar() {
  const { conversations, loading, createConversation } = useAskConversations();
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const { t, locale } = useTranslation();
  const [creating, setCreating] = useState(false);

  async function handleNew() {
    setCreating(true);
    try {
      const conversation = await createConversation();
      router.push(`/ask/${conversation.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <div className={styles.sidebarTitle}>{t("ask.sidebarTitle")}</div>
        <Button size="sm" block onClick={handleNew} loading={creating}>
          {creating ? t("ask.starting") : t("ask.newConversation")}
        </Button>
      </div>
      <div className={styles.list}>
        {loading ? (
          <div style={{ padding: 16 }}>
            <Spinner size="sm" />
          </div>
        ) : conversations.length === 0 ? (
          <div style={{ padding: 16, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
            {t("ask.noConversations")}
          </div>
        ) : (
          conversations.map((conversation) => {
            const active = params.conversationId === conversation.id;
            return (
              <Link
                key={conversation.id}
                href={`/ask/${conversation.id}`}
                className={clsx(styles.item, active && styles.itemActive)}
              >
                <div className={styles.itemTitle}>{conversation.title || t("ask.untitledConversation")}</div>
                <div className={styles.itemMeta}>{formatDate(locale, conversation.updated_at, { month: "short", day: "numeric" })}</div>
              </Link>
            );
          })
        )}
      </div>
    </aside>
  );
}

