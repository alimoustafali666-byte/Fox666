"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useParams } from "next/navigation";
import { conversationsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { MessageBubble } from "@/components/ask/MessageBubble";
import type { ConversationPublic, MessagePublic } from "@/lib/types";
import styles from "@/components/ask/Thread.module.css";

export default function ConversationThreadPage() {
  const params = useParams<{ conversationId: string }>();
  const { t } = useTranslation();
  const [conversation, setConversation] = useState<ConversationPublic | null>(null);
  const [messages, setMessages] = useState<MessagePublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [conversationDetail, messagePage] = await Promise.all([
        conversationsApi.get(params.conversationId),
        conversationsApi.listMessages(params.conversationId, { limit: 100 }),
      ]);
      setConversation(conversationDetail);
      // Oldest-first for a natural reading order in the thread.
      setMessages([...messagePage.items].reverse());
    } catch (err) {
      setError(errorMessage(err, t("ask.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.conversationId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;

    setError(null);
    setAsking(true);
    const optimisticUser: MessagePublic = {
      id: `pending-${Date.now()}`,
      conversation_id: params.conversationId,
      role: "user",
      content: trimmed,
      is_sufficient: null,
      model_identifier: null,
      created_at: new Date().toISOString(),
      citations: [],
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setQuestion("");

    try {
      const answer = await conversationsApi.ask(params.conversationId, trimmed);
      setMessages((prev) => [...prev, answer]);
    } catch (err) {
      setError(errorMessage(err, t("ask.genericAskError")));
      // Uncertain whether the question was persisted server-side before
      // the failure -- reload from the source of truth rather than guess.
      await load();
    } finally {
      setAsking(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleAsk(event as unknown as FormEvent);
    }
  }

  if (loading) return <LoadingBlock label={t("ask.loadingConversation")} />;

  return (
    <>
      <div className={styles.threadHeader}>{conversation?.title || t("ask.untitledConversation")}</div>

      <div className={styles.messages} ref={scrollRef}>
        {error ? <ErrorBanner message={error} /> : null}
        {messages.length === 0 ? (
          <div style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{t("ask.threadEmpty")}</div>
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
        {asking ? (
          <div className={styles.row}>
            <div className={styles.thinking}>
              <span className={styles.thinkingDots} aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              {t("ask.thinking")}
            </div>
          </div>
        ) : null}
      </div>

      <div className={styles.composer}>
        <form className={styles.composerRow} onSubmit={handleAsk}>
          <div className={styles.composerInput}>
            <Textarea
              placeholder={t("ask.placeholder")}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              disabled={asking}
            />
          </div>
          <Button type="submit" loading={asking} disabled={!question.trim()}>
            {asking ? t("ask.asking") : t("ask.askButton")}
          </Button>
        </form>
        <div className={styles.meta}>{t("ask.hint")}</div>
      </div>
    </>
  );
}

