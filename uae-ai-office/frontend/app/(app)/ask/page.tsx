"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAskConversations } from "@/components/ask/AskConversationsContext";
import { documentsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, type TranslationKey } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  ChipRow,
  ChipLink,
  Disclosure,
  InfoList,
  InfoRow,
  LaunchBox,
  PointList,
  PromptCard,
  PromptGrid,
  SectionLabel,
  SkeletonRows,
  StatusLegend,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePanel,
  WorkspaceScroller,
  WorkspaceSplit,
  ZeroState,
  type LegendItem,
} from "@/components/ui/Workspace";
import {
  AskIcon,
  BoltIcon,
  BrainIcon,
  DocumentsIcon,
  InsightIcon,
  ShieldIcon,
  SparkIcon,
  TargetIcon,
  TasksIcon,
  UploadIcon,
} from "@/components/layout/icons";
import type { DocumentPublic } from "@/lib/types";

const CONTEXT_SCAN_LIMIT = 100;

/** Suggested openers. Deliberately generic prompts -- they ask ABOUT the
 *  user's documents, they never assert anything about their contents. */
const PROMPTS: { key: string; tagKey: TranslationKey; textKey: TranslationKey; accent: "violet" | "blue" | "cyan" | "magenta" | "green" | "amber" }[] = [
  { key: "contracts", tagKey: "workspace.ask.prompts.contractsTag", textKey: "workspace.ask.prompts.contracts", accent: "violet" },
  { key: "boq", tagKey: "workspace.ask.prompts.boqTag", textKey: "workspace.ask.prompts.boq", accent: "blue" },
  { key: "invoices", tagKey: "workspace.ask.prompts.invoicesTag", textKey: "workspace.ask.prompts.invoices", accent: "cyan" },
  { key: "obligations", tagKey: "workspace.ask.prompts.obligationsTag", textKey: "workspace.ask.prompts.obligations", accent: "magenta" },
  { key: "risks", tagKey: "workspace.ask.prompts.risksTag", textKey: "workspace.ask.prompts.risks", accent: "amber" },
  { key: "scope", tagKey: "workspace.ask.prompts.scopeTag", textKey: "workspace.ask.prompts.scope", accent: "green" },
];

interface ContextCounts {
  total: number;
  ready: number;
  processed: number;
  processing: number;
  uploaded: number;
}

/** Folds the two backend lifecycles (status + indexing_status) into the same
 *  four buckets the Documents page shows. Nothing is estimated. */
function countContext(documents: DocumentPublic[]): ContextCounts {
  const counts: ContextCounts = { total: documents.length, ready: 0, processed: 0, processing: 0, uploaded: 0 };
  for (const doc of documents) {
    if (doc.status === "processed" && doc.indexing_status === "indexed") counts.ready += 1;
    else if (doc.status === "processing" || doc.indexing_status === "indexing") counts.processing += 1;
    else if (doc.status === "processed") counts.processed += 1;
    else counts.uploaded += 1;
  }
  return counts;
}

export default function AskLandingPage() {
  const { conversations, loading: loadingConversations, createConversation } = useAskConversations();
  const router = useRouter();
  const { t, locale } = useTranslation();

  const [draft, setDraft] = useState("");
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentPublic[] | null>(null);
  const [loadingContext, setLoadingContext] = useState(true);

  // The knowledge-context panel is fed from the same read-only endpoint the
  // Documents page uses. A failure leaves it in a neutral "unavailable"
  // state rather than blanking the workspace.
  useEffect(() => {
    let cancelled = false;
    documentsApi
      .list({ limit: CONTEXT_SCAN_LIMIT })
      .then((page) => {
        if (!cancelled) setDocuments(page.items);
      })
      .catch(() => {
        if (!cancelled) setDocuments(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingContext(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const context = useMemo(() => (documents ? countContext(documents) : null), [documents]);

  /** Opens a new thread. When a suggestion was clicked its text is handed to
   *  the thread as `?q=`, which prefills the composer -- the question is only
   *  ever sent when the user presses Ask. */
  async function startConversation(question?: string, key = "start") {
    if (creating) return;
    setCreating(key);
    setError(null);
    try {
      const conversation = await createConversation();
      const suffix = question ? `?q=${encodeURIComponent(question)}` : "";
      router.push(`/ask/${conversation.id}${suffix}`);
    } catch (err) {
      setError(errorMessage(err, t("ask.genericListError")));
      setCreating(null);
    }
  }

  const contextLegend: LegendItem[] = context
    ? [
        { label: t("workspace.ask.contextRows.ready"), description: t("documents.lifecycle.ready"), color: "#2fd48a", count: context.ready },
        { label: t("workspace.ask.contextRows.processed"), description: t("documents.lifecycle.processed"), color: "#4d8dff", count: context.processed },
        { label: t("workspace.ask.contextRows.processing"), description: t("documents.lifecycle.processing"), color: "#8b6bff", count: context.processing },
        { label: t("workspace.ask.contextRows.uploaded"), description: t("documents.lifecycle.uploaded"), color: "#ffa43d", count: context.uploaded },
      ]
    : [];

  // Onboarding gives way to operations: with threads on file the conversation
  // list is the page, and the openers shrink to a short strip beneath it.
  const hasConversations = conversations.length > 0;
  const recent = conversations.slice(0, 6);
  const prompts = hasConversations ? PROMPTS.slice(0, 3) : PROMPTS;

  return (
    <WorkspaceScroller module="ask">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="violet"
        compact
        badge={t("workspace.ask.badge")}
        icon={<BrainIcon />}
        title={t("workspace.ask.title")}
        description={t("workspace.ask.description")}
        actions={
          <>
            <div style={{ width: "min(100%, 620px)" }}>
              <LaunchBox
                accent="violet"
                icon={<SparkIcon />}
                value={draft}
                onChange={setDraft}
                onSubmit={() => startConversation(draft.trim() || undefined, "start")}
                placeholder={t("workspace.ask.launchPlaceholder")}
                disabled={creating !== null}
                action={
                  <Button onClick={() => startConversation(draft.trim() || undefined, "start")} loading={creating === "start"}>
                    {creating === "start" ? t("workspace.ask.starting") : t("workspace.ask.startCta")}
                  </Button>
                }
              />
            </div>
            <ChipRow>
              <ChipLink accent="blue" href="/documents" icon={<DocumentsIcon />}>
                {t("workspace.ask.contextManage")}
              </ChipLink>
              <ChipLink accent="cyan" href="/documents?upload=1" icon={<UploadIcon />}>
                {t("workspace.ask.contextUpload")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.ask.metrics.readyLabel"),
            value: context ? context.ready : "—",
            hint: t("workspace.ask.metrics.readyHint"),
            icon: <ShieldIcon />,
          },
          {
            label: t("workspace.ask.metrics.libraryLabel"),
            value: context ? context.total : "—",
            hint: t("workspace.ask.metrics.libraryHint"),
            icon: <DocumentsIcon />,
          },
          {
            label: t("workspace.ask.metrics.conversationsLabel"),
            value: loadingConversations ? "—" : conversations.length,
            hint: t("workspace.ask.metrics.conversationsHint"),
            icon: <AskIcon />,
          },
          {
            label: t("workspace.ask.metrics.groundingLabel"),
            value: <span style={{ fontSize: 15 }}>{t("workspace.ask.metrics.groundingValue")}</span>,
            hint: t("workspace.ask.metrics.groundingHint"),
            icon: <SparkIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          {hasConversations ? (
            <WorkspacePanel
              accent="violet"
              icon={<AskIcon />}
              title={t("workspace.ask.recentTitle")}
              subtitle={t("ask.showingCount", { count: conversations.length })}
              tight
            >
              <InfoList>
                {conversations.map((conversation) => (
                  <InfoRow
                    key={conversation.id}
                    accent="violet"
                    icon={<AskIcon />}
                    href={`/ask/${conversation.id}`}
                    label={conversation.title || t("ask.untitledConversation")}
                    meta={formatDate(locale, conversation.updated_at, { month: "short", day: "numeric" })}
                  />
                ))}
              </InfoList>
            </WorkspacePanel>
          ) : null}

          <SectionLabel title={t("workspace.ask.suggestionsTitle")} aside={t("workspace.ask.suggestionsAside")} />
          <PromptGrid>
            {prompts.map((prompt) => {
              const text = t(prompt.textKey);
              return (
                <PromptCard
                  key={prompt.key}
                  accent={prompt.accent}
                  tag={t(prompt.tagKey)}
                  text={text}
                  go={t("workspace.ask.promptGo")}
                  disabled={creating !== null}
                  onClick={() => startConversation(text, prompt.key)}
                />
              );
            })}
          </PromptGrid>

          <Disclosure
            accent="violet"
            icon={<InsightIcon />}
            label={t("workspace.ask.howLabel")}
          >
            <PointList
              accent="violet"
              items={[
                {
                  icon: <ShieldIcon />,
                  title: t("workspace.ask.capabilities.groundedTitle"),
                  text: t("workspace.ask.capabilities.groundedDescription"),
                },
                {
                  icon: <TargetIcon />,
                  title: t("workspace.ask.capabilities.citationsTitle"),
                  text: t("workspace.ask.capabilities.citationsDescription"),
                },
                {
                  icon: <SparkIcon />,
                  title: t("workspace.ask.capabilities.bilingualTitle"),
                  text: t("workspace.ask.capabilities.bilingualDescription"),
                },
                {
                  icon: <TasksIcon />,
                  title: t("workspace.ask.capabilities.actionsTitle"),
                  text: t("workspace.ask.capabilities.actionsDescription"),
                },
              ]}
            />
            <div style={{ marginTop: "var(--space-4)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--ai-hairline)" }}>
              <StepList
                accent="blue"
                steps={[
                  { title: t("workspace.ask.steps.uploadTitle"), description: t("workspace.ask.steps.uploadDescription") },
                  { title: t("workspace.ask.steps.indexTitle"), description: t("workspace.ask.steps.indexDescription") },
                  { title: t("workspace.ask.steps.askTitle"), description: t("workspace.ask.steps.askDescription") },
                  { title: t("workspace.ask.steps.verifyTitle"), description: t("workspace.ask.steps.verifyDescription") },
                ]}
              />
            </div>
          </Disclosure>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="green"
            icon={<DocumentsIcon />}
            title={t("workspace.ask.contextTitle")}
            subtitle={t("workspace.ask.contextSubtitle")}
            tight
          >
            {loadingContext ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={4} />
              </div>
            ) : !context ? (
              <ZeroState
                accent="amber"
                icon={<DocumentsIcon />}
                title={t("workspace.ask.contextUnavailable")}
              />
            ) : context.total === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<UploadIcon />}
                title={t("workspace.ask.contextEmptyTitle")}
                text={t("workspace.ask.contextEmptyText")}
                actions={
                  <Link href="/documents?upload=1" className={buttonClassName("primary", "sm")}>
                    {t("workspace.ask.contextUpload")}
                  </Link>
                }
              />
            ) : (
              <>
                <StatusLegend items={contextLegend} total={context.total} />
                <div style={{ padding: "var(--space-2) var(--space-3) var(--space-3)" }}>
                  <Link href="/documents" className={buttonClassName("secondary", "sm", true)}>
                    {t("workspace.ask.contextManage")}
                  </Link>
                </div>
              </>
            )}
          </WorkspacePanel>

          {hasConversations ? null : (
          <WorkspacePanel
            accent="violet"
            icon={<AskIcon />}
            title={t("workspace.ask.recentTitle")}
            subtitle={t("workspace.ask.recentSubtitle")}
            tight
          >
            {loadingConversations ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={3} />
              </div>
            ) : recent.length === 0 ? (
              <ZeroState
                accent="violet"
                icon={<AskIcon />}
                title={t("workspace.ask.recentEmptyTitle")}
                text={t("workspace.ask.recentEmptyText")}
              />
            ) : (
              <InfoList>
                {recent.map((conversation) => (
                  <InfoRow
                    key={conversation.id}
                    accent="violet"
                    icon={<AskIcon />}
                    href={`/ask/${conversation.id}`}
                    label={conversation.title || t("ask.untitledConversation")}
                    meta={formatDate(locale, conversation.updated_at, { month: "short", day: "numeric" })}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>
          )}

          <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
            {t("workspace.ask.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspaceScroller>
  );
}
