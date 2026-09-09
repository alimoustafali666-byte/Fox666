"use client";

import { useState, type FormEvent } from "react";
import { collaborationApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { formatDateTime, useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { CloseIcon } from "@/components/layout/icons";
import type { ChatMessagePublic } from "@/lib/types";
import styles from "./ThreadToolPanel.module.css";

/** Full-text search inside one conversation. Results jump the thread to
 *  the matching message, which is why this takes onJumpToMessage rather
 *  than rendering a self-contained transcript: a result is only useful
 *  in the surrounding context of the conversation. */
export function SearchPanel({
  conversationId,
  onClose,
  onJumpToMessage,
}: {
  conversationId: string;
  onClose: () => void;
  onJumpToMessage: (messageId: string) => void;
}) {
  const { t, locale } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ChatMessagePublic[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const page = await collaborationApi.searchConversation(conversationId, trimmed);
      setResults(page.items);
    } catch (err) {
      setError(errorMessage(err, t("messages.search.genericError")));
      setResults(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.title}>{t("messages.search.panelTitle")}</div>
        <button type="button" className={styles.closeButton} onClick={onClose} aria-label={t("common.close")}>
          <CloseIcon width={14} height={14} />
        </button>
      </div>
      <div className={styles.hint}>{t("messages.search.panelHint")}</div>

      <form className={styles.searchForm} onSubmit={handleSearch}>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("messages.search.placeholder")}
          aria-label={t("messages.search.placeholder")}
        />
        <Button size="sm" type="submit" loading={busy} disabled={!query.trim()}>
          {t("messages.search.button")}
        </Button>
      </form>

      {error ? <ErrorBanner message={error} /> : null}

      {results === null ? null : results.length === 0 ? (
        <p className={styles.emptyText}>{t("messages.search.noResults")}</p>
      ) : (
        <div className={styles.resultList}>
          {results.map((message) => (
            <button
              key={message.id}
              type="button"
              className={styles.result}
              onClick={() => onJumpToMessage(message.id)}
            >
              <div className={styles.resultMeta}>
                <span>{message.sender_name || t("messages.message.unknownSender")}</span>
                <span>{formatDateTime(locale, message.created_at)}</span>
              </div>
              <div className={styles.resultText}>{message.content}</div>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
