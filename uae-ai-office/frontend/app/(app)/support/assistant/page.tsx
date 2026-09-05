"use client";

import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import { collectDiagnostics } from "@/lib/support-diagnostics";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import clsx from "@/components/ui/clsx";
import {
  Disclosure,
  InfoList,
  InfoRow,
  PointList,
  PromptCard,
  PromptGrid,
  SectionLabel,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
  type Accent,
} from "@/components/ui/Workspace";
import {
  BoltIcon,
  BrainIcon,
  DocumentsIcon,
  HelpIcon,
  InsightIcon,
  ShieldIcon,
  SparkIcon,
  TargetIcon,
  TicketIcon,
} from "@/components/layout/icons";
import type { SupportAssistantAskResponse } from "@/lib/types";
import styles from "../Support.module.css";

interface Exchange {
  question: string;
  response: SupportAssistantAskResponse;
}

/** Openers about using the product. They are fixed copy -- none of them
 *  asserts anything about this company's data. */
const PROMPTS: { key: string; tagKey: TranslationKey; textKey: TranslationKey; accent: Accent }[] = [
  { key: "upload", tagKey: "workspace.assistant.prompts.uploadTag", textKey: "workspace.assistant.prompts.upload", accent: "cyan" },
  { key: "index", tagKey: "workspace.assistant.prompts.indexTag", textKey: "workspace.assistant.prompts.index", accent: "violet" },
  { key: "roles", tagKey: "workspace.assistant.prompts.rolesTag", textKey: "workspace.assistant.prompts.roles", accent: "magenta" },
  { key: "brief", tagKey: "workspace.assistant.prompts.briefTag", textKey: "workspace.assistant.prompts.brief", accent: "blue" },
  { key: "export", tagKey: "workspace.assistant.prompts.exportTag", textKey: "workspace.assistant.prompts.export", accent: "green" },
  { key: "invite", tagKey: "workspace.assistant.prompts.inviteTag", textKey: "workspace.assistant.prompts.invite", accent: "amber" },
];

export default function SupportAssistantPage() {
  const { t, locale } = useTranslation();
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Counted from what this session actually returned -- never estimated.
  const citedCount = useMemo(
    () => new Set(exchanges.flatMap((e) => e.response.citations.map((c) => c.article_slug))).size,
    [exchanges]
  );

  async function ask(text: string) {
    const trimmed = text.trim();
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

  function handleAsk(event: FormEvent) {
    event.preventDefault();
    ask(question);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      ask(question);
    }
  }

  return (
    <WorkspacePage module="support">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="cyan"
        badge={t("workspace.assistant.badge")}
        icon={<BrainIcon />}
        title={t("support.assistant.title")}
        description={t("workspace.assistant.description")}
        actions={
          <>
            <Link href="/support" className={buttonClassName("secondary", "md")}>
              {t("workspace.assistant.resources.articlesTitle")}
            </Link>
            <Link href="/support/tickets/new" className={buttonClassName("ghost", "md")}>
              {t("workspace.assistant.resources.ticketTitle")}
            </Link>
          </>
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="violet" icon={<BrainIcon />} title={t("support.assistant.title")}>
            {exchanges.length === 0 ? (
              <ZeroState
                accent="violet"
                icon={<SparkIcon />}
                title={t("workspace.assistant.emptyTitle")}
                text={t("workspace.assistant.emptyText")}
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
          </WorkspacePanel>

          {exchanges.length === 0 ? (
            <>
              <SectionLabel
                title={t("workspace.assistant.suggestionsTitle")}
                aside={t("workspace.assistant.suggestionsAside")}
              />
              <PromptGrid>
                {PROMPTS.map((prompt) => {
                  const text = t(prompt.textKey);
                  return (
                    <PromptCard
                      key={prompt.key}
                      accent={prompt.accent}
                      tag={t(prompt.tagKey)}
                      text={text}
                      go={t("workspace.assistant.promptGo")}
                      disabled={asking}
                      onClick={() => ask(text)}
                    />
                  );
                })}
              </PromptGrid>
            </>
          ) : null}

          <Disclosure accent="cyan" icon={<InsightIcon />} label={t("workspace.assistant.capabilitiesTitle")}>
            <PointList
              accent="cyan"
              items={[
                { icon: <ShieldIcon />, title: t("workspace.assistant.capabilities.groundedTitle"), text: t("workspace.assistant.capabilities.groundedDescription") },
                { icon: <TargetIcon />, title: t("workspace.assistant.capabilities.citationsTitle"), text: t("workspace.assistant.capabilities.citationsDescription") },
                { icon: <TicketIcon />, title: t("workspace.assistant.capabilities.escalateTitle"), text: t("workspace.assistant.capabilities.escalateDescription") },
                { icon: <BoltIcon />, title: t("workspace.assistant.capabilities.privacyTitle"), text: t("workspace.assistant.capabilities.privacyDescription") },
              ]}
            />
          </Disclosure>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel accent="blue" icon={<HelpIcon />} title={t("workspace.assistant.resourcesTitle")} tight>
            <InfoList>
              <InfoRow
                accent="blue"
                icon={<DocumentsIcon />}
                href="/support"
                label={t("workspace.assistant.resources.articlesTitle")}
                meta={t("workspace.assistant.resources.articlesDescription")}
              />
              <InfoRow
                accent="magenta"
                icon={<TicketIcon />}
                href="/support/tickets/new"
                label={t("workspace.assistant.resources.ticketTitle")}
                meta={t("workspace.assistant.resources.ticketDescription")}
              />
              <InfoRow
                accent="cyan"
                icon={<HelpIcon />}
                href="/support/tickets"
                label={t("workspace.assistant.resources.ticketsTitle")}
                meta={t("workspace.assistant.resources.ticketsDescription")}
              />
            </InfoList>
          </WorkspacePanel>

          {exchanges.length > 0 ? (
            <WorkspacePanel accent="green" icon={<TargetIcon />} title={t("workspace.assistant.capabilitiesTitle")} tight>
              <div style={{ padding: "var(--space-3)", display: "grid", gap: "var(--space-2)" }}>
                <div style={{ fontSize: "var(--font-size-sm)", color: "var(--ai-text-2)" }}>
                  {t("workspace.assistant.capabilities.citationsMeta")} · {citedCount}
                </div>
              </div>
            </WorkspacePanel>
          ) : null}

          <WorkspaceNote accent="violet" icon={<ShieldIcon />}>
            {t("workspace.assistant.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
