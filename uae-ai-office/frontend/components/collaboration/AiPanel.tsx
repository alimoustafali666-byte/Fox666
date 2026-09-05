"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { collaborationApi, ApiError } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import type { AiAnswerResponse, AiInsightsResponse } from "@/lib/types";
import styles from "./AiPanel.module.css";
import { CloseIcon } from "@/components/layout/icons";

type ActionKey = "summarize" | "summarizeUnread" | "decisions" | "actionItems" | "ask" | null;

export function AiPanel({ conversationId, onClose, onJumpToMessage }: { conversationId: string; onClose: () => void; onJumpToMessage: (messageId: string) => void }) {
  const { t } = useTranslation();
  const [insights, setInsights] = useState<AiInsightsResponse | null>(null);
  const [answer, setAnswer] = useState<AiAnswerResponse | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState<ActionKey>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: Exclude<ActionKey, null | "ask">) {
    setBusy(action);
    setError(null);
    setAnswer(null);
    try {
      const result =
        action === "summarize"
          ? await collaborationApi.aiSummarize(conversationId)
          : action === "summarizeUnread"
            ? await collaborationApi.aiSummarizeUnread(conversationId)
            : action === "decisions"
              ? await collaborationApi.aiExtractDecisions(conversationId)
              : await collaborationApi.aiExtractActionItems(conversationId);
      setInsights(result);
    } catch (err) {
      const fallback = err instanceof ApiError && err.status === 429 ? t("messages.ai.rateLimitedError") : t("messages.ai.genericError");
      setError(errorMessage(err, fallback));
    } finally {
      setBusy(null);
    }
  }

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    setBusy("ask");
    setError(null);
    setInsights(null);
    try {
      const result = await collaborationApi.aiAsk(conversationId, trimmed);
      setAnswer(result);
    } catch (err) {
      const fallback = err instanceof ApiError && err.status === 429 ? t("messages.ai.rateLimitedError") : t("messages.ai.genericError");
      setError(errorMessage(err, fallback));
    } finally {
      setBusy(null);
    }
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.title}>{t("messages.ai.panelTitle")}</div>
        <button type="button" className={styles.closeButton} onClick={onClose}>
          <CloseIcon width={14} height={14} />
        </button>
      </div>
      <div className={styles.hint}>{t("messages.ai.panelHint")}</div>

      <div className={styles.buttonGrid}>
        <Button size="sm" variant="secondary" onClick={() => run("summarize")} loading={busy === "summarize"} disabled={busy !== null}>
          {t("messages.ai.summarizeButton")}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => run("summarizeUnread")} loading={busy === "summarizeUnread"} disabled={busy !== null}>
          {t("messages.ai.summarizeUnreadButton")}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => run("decisions")} loading={busy === "decisions"} disabled={busy !== null}>
          {t("messages.ai.decisionsButton")}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => run("actionItems")} loading={busy === "actionItems"} disabled={busy !== null}>
          {t("messages.ai.actionItemsButton")}
        </Button>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      {busy === "summarize" || busy === "summarizeUnread" || busy === "decisions" || busy === "actionItems" ? (
        <div className={styles.thinking}>{t("messages.ai.thinking")}</div>
      ) : null}

      {insights ? (
        <div className={styles.results}>
          {insights.summary ? (
            <div>
              <div className={styles.sectionTitle}>{t("messages.ai.summaryTitle")}</div>
              <p className={styles.summaryText}>{insights.summary}</p>
            </div>
          ) : null}

          <div>
            <div className={styles.sectionTitle}>{t("messages.ai.decisionsTitle")}</div>
            {insights.decisions.length === 0 ? (
              <p className={styles.emptyText}>{t("messages.ai.noDecisions")}</p>
            ) : (
              insights.decisions.map((d, i) => (
                <div key={i} className={styles.item}>
                  <span>{d.description}</span>
                  <span className={styles.badgeText}>{d.confirmed ? t("messages.ai.confirmed") : t("messages.ai.unconfirmed")}</span>
                  {d.source_message_id ? (
                    <button type="button" className={styles.sourceLink} onClick={() => onJumpToMessage(d.source_message_id as string)}>
                      {t("messages.ai.sourceLink")}
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>

          <div>
            <div className={styles.sectionTitle}>{t("messages.ai.actionItemsTitle")}</div>
            {insights.action_items.length === 0 ? (
              <p className={styles.emptyText}>{t("messages.ai.noActionItems")}</p>
            ) : (
              insights.action_items.map((a, i) => (
                <div key={i} className={styles.item}>
                  <span>{a.description}</span>
                  {a.possible_assignee ? <span className={styles.badgeText}>{t("messages.ai.assignee", { name: a.possible_assignee })}</span> : null}
                  {a.due_date ? <span className={styles.badgeText}>{t("messages.ai.dueDate", { date: a.due_date })}</span> : null}
                  {a.source_message_id ? (
                    <button type="button" className={styles.sourceLink} onClick={() => onJumpToMessage(a.source_message_id as string)}>
                      {t("messages.ai.sourceLink")}
                    </button>
                  ) : null}
                  <Link
                    href={`/tasks/new?title=${encodeURIComponent(a.description.slice(0, 200))}${a.due_date ? `&due_date=${a.due_date}` : ""}${a.source_message_id ? `&source_type=ai_suggestion&source_id=${a.source_message_id}` : ""}`}
                    className={styles.sourceLink}
                  >
                    {t("messages.ai.createTaskAction")}
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}

      {answer ? (
        <div className={styles.results}>
          <p className={styles.summaryText}>{answer.answer}</p>
          {!answer.sufficient ? <p className={styles.emptyText}>{t("messages.ai.insufficientAnswer")}</p> : null}
          {answer.citations.length > 0 ? (
            <div className={styles.citations}>
              {answer.citations.map((c) => (
                <button key={c.message_id} type="button" className={styles.sourceLink} onClick={() => onJumpToMessage(c.message_id)}>
                  {t("messages.ai.sourceLink")}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <form className={styles.askForm} onSubmit={handleAsk}>
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("messages.ai.askPlaceholder")}
          rows={2}
          disabled={busy !== null}
        />
        <Button type="submit" size="sm" loading={busy === "ask"} disabled={!question.trim() || busy !== null}>
          {busy === "ask" ? t("messages.ai.asking") : t("messages.ai.askButton")}
        </Button>
      </form>
    </aside>
  );
}

