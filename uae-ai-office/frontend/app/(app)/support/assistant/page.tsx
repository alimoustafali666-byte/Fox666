"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { collectDiagnostics } from "@/lib/support-diagnostics";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import clsx from "@/components/ui/clsx";
import type { SupportAssistantAskResponse } from "@/lib/types";
import styles from "../Support.module.css";

interface Exchange {
  question: string;
  response: SupportAssistantAskResponse;
}

export default function SupportAssistantPage() {
  const { t, locale } = useTranslation();
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;

    setError(null);
    setAsking(true);
    try {
      const response = await supportApi.askAssistant(trimmed, collectDiagnostics(), locale);
      setExchanges((prev) => [...prev, { question: trimmed, response }]);
      setQuestion("");
    } catch (err) {
      setError(errorMessage(err, t("support.assistant.genericAskError")));
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

  return (
    <div>
      <PageHeader title={t("support.assistant.title")} description={t("support.assistant.description")} />

      <Card>
        <CardBody>
          {exchanges.length === 0 ? (
            <EmptyState
              title={t("support.assistant.emptyTitle")}
              description={t("support.assistant.emptyDescription")}
            />
          ) : (
            <div className={styles.assistantExchanges}>
              {exchanges.map((exchange, index) => (
                <div key={index}>
                  <div className={styles.assistantQuestion}>{exchange.question}</div>
                  <div className={styles.assistantAnswerWrap} style={{ marginTop: "var(--space-3)" }}>
                    <div
                      className={clsx(
                        styles.assistantAnswer,
                        !exchange.response.sufficient && styles.assistantAnswerInsufficient
                      )}
                    >
                      {exchange.response.answer}
                    </div>
                    {exchange.response.citations.length > 0 ? (
                      <div className={styles.assistantCitations}>
                        {exchange.response.citations.map((citation) => (
                          <Link
                            key={citation.article_slug}
                            href={`/support/articles/${citation.article_slug}`}
                            className={styles.assistantCitationChip}
                          >
                            {citation.title}
                          </Link>
                        ))}
                      </div>
                    ) : null}
                    {exchange.response.used_diagnostics ? (
                      <span className={styles.assistantNote}>{t("support.assistant.usedDiagnosticsNote")}</span>
                    ) : null}
                    {!exchange.response.sufficient ? (
                      <div className={styles.assistantEscalation}>
                        <span className={styles.assistantNote}>{t("support.assistant.insufficientHint")}</span>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            router.push(`/support/tickets/new?subject=${encodeURIComponent(exchange.question)}`)
                          }
                        >
                          {t("support.assistant.createTicketButton")}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}

          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <form className={styles.assistantComposer} onSubmit={handleAsk}>
            <div className={styles.assistantComposerRow}>
              <div className={styles.assistantComposerInput}>
                <Textarea
                  placeholder={t("support.assistant.placeholder")}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  disabled={asking}
                  maxLength={1000}
                />
              </div>
              <Button type="submit" loading={asking} disabled={!question.trim()}>
                {asking ? t("support.assistant.asking") : t("support.assistant.askButton")}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}

