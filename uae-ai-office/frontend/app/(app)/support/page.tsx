"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Input } from "@/components/ui/Field";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import {
  AskIcon,
  DocumentsIcon,
  HelpIcon,
  InsightIcon,
  SearchIcon,
  ShieldIcon,
  TicketIcon,
} from "@/components/layout/icons";
import {
  ChipLink,
  ChipRow,
  Disclosure,
  InfoList,
  InfoRow,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
} from "@/components/ui/Workspace";
import { CATEGORY_LABEL_KEYS, STATUS_LABEL_KEYS, STATUS_TONE } from "@/components/support/labels";
import {
  SUPPORT_TICKET_CATEGORIES,
  type SupportArticlePublic,
  type SupportTicketCategory,
  type SupportTicketPublic,
} from "@/lib/types";
import clsx from "@/components/ui/clsx";
import styles from "./Support.module.css";

const TICKET_SCAN_LIMIT = 20;
const OPEN_STATUSES = new Set(["open", "in_progress", "waiting_for_user"]);

export default function SupportCenterPage() {
  const { t, locale } = useTranslation();
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SupportArticlePublic[] | null>(null);
  const [articles, setArticles] = useState<SupportArticlePublic[]>([]);
  const [activeCategory, setActiveCategory] = useState<SupportTicketCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tickets, setTickets] = useState<SupportTicketPublic[] | null>(null);
  const [loadingTickets, setLoadingTickets] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    supportApi
      .listArticles({ locale, category: activeCategory ?? undefined })
      .then((page) => setArticles(page.items))
      .catch((err) => setError(errorMessage(err, t("support.genericLoadError"))))
      .finally(() => setLoading(false));
  }, [locale, t, activeCategory]);

  // Ticket status is a separate read-only endpoint and settles on its own, so
  // a failure here leaves that panel neutral rather than blanking the page.
  useEffect(() => {
    let cancelled = false;
    supportApi
      .listTickets({ limit: TICKET_SCAN_LIMIT })
      .then((page) => {
        if (!cancelled) setTickets(page.items);
      })
      .catch(() => {
        if (!cancelled) setTickets(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingTickets(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openTickets = useMemo(
    () => (tickets ? tickets.filter((ticket) => OPEN_STATUSES.has(ticket.status)).length : null),
    [tickets]
  );

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    const query = search.trim();
    if (!query) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const page = await supportApi.searchArticles(query, locale);
      setSearchResults(page.items);
    } catch (err) {
      setError(errorMessage(err, t("support.genericLoadError")));
    } finally {
      setSearching(false);
    }
  }

  const listedArticles = searchResults ?? articles;

  return (
    <WorkspacePage module="support">
      <WorkspaceHero
        accent="cyan"
        compact
        badge={t("workspace.support.badge")}
        icon={<HelpIcon />}
        title={t("support.title")}
        description={t("workspace.support.description")}
        actions={
          <>
            <form className={styles.searchForm} onSubmit={handleSearch}>
              <div className={styles.searchInput}>
                <Input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    if (!e.target.value.trim()) setSearchResults(null);
                  }}
                  placeholder={t("support.searchPlaceholder")}
                  maxLength={300}
                  aria-label={t("support.searchPlaceholder")}
                />
              </div>
              <Button type="submit" loading={searching}>
                {t("support.searchButton")}
              </Button>
            </form>
            <ChipRow>
              <ChipLink accent="violet" href="/support/assistant" icon={<AskIcon />}>
                {t("support.assistantCardAction")}
              </ChipLink>
              <ChipLink accent="amber" href="/support/tickets/new" icon={<DocumentsIcon />}>
                {t("support.reportProblemCardAction")}
              </ChipLink>
              <ChipLink accent="green" href="/support/tickets" icon={<TicketIcon />}>
                {t("support.myTicketsCardAction")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.support.metrics.articlesLabel"),
            value: loading ? "—" : articles.length,
            hint: t("workspace.support.metrics.articlesHint"),
            icon: <HelpIcon />,
          },
          {
            label: t("workspace.support.metrics.categoriesLabel"),
            value: SUPPORT_TICKET_CATEGORIES.length,
            hint: t("workspace.support.metrics.categoriesHint"),
            icon: <SearchIcon />,
          },
          {
            label: t("workspace.support.metrics.ticketsLabel"),
            value: loadingTickets ? "—" : tickets ? tickets.length : "—",
            hint: t("workspace.support.metrics.ticketsHint"),
            icon: <TicketIcon />,
          },
          {
            label: t("workspace.support.metrics.openLabel"),
            value: openTickets === null ? "—" : openTickets,
            hint: t("workspace.support.metrics.openHint"),
            icon: <ShieldIcon />,
          },
        ]}
      />

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <div className={styles.categoryBar}>
            <div className={styles.categoryLabel}>{t("support.browseByTopicTitle")}</div>
            <div className={styles.categoryGrid}>
              {SUPPORT_TICKET_CATEGORIES.map((category) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => setActiveCategory((prev) => (prev === category ? null : category))}
                  className={clsx(styles.categoryChip, activeCategory === category && styles.categoryChipActive)}
                >
                  {t(CATEGORY_LABEL_KEYS[category])}
                </button>
              ))}
            </div>
          </div>

          <WorkspacePanel
            accent="cyan"
            icon={<HelpIcon />}
            title={searchResults !== null ? t("support.searchResultsTitle") : t("support.articlesCardTitle")}
            subtitle={
              searchResults !== null
                ? undefined
                : activeCategory
                  ? t(CATEGORY_LABEL_KEYS[activeCategory])
                  : t("support.articlesCardDescription")
            }
            action={
              searchResults !== null ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setSearch("");
                    setSearchResults(null);
                  }}
                >
                  {t("common.close")}
                </Button>
              ) : activeCategory ? (
                <Button size="sm" variant="ghost" onClick={() => setActiveCategory(null)}>
                  {t("workspace.documents.clearFilters")}
                </Button>
              ) : undefined
            }
            tight
          >
            {loading && searchResults === null ? (
              <LoadingBlock label={t("support.tickets.loadingList")} />
            ) : listedArticles.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<HelpIcon />}
                title={searchResults !== null ? t("support.searchNoResultsTitle") : t("workspace.support.articlesEmptyTitle")}
                text={
                  searchResults !== null
                    ? t("support.searchNoResultsDescription")
                    : t("workspace.support.articlesEmptyText")
                }
                actions={
                  <Button size="sm" onClick={() => router.push("/support/assistant")}>
                    {t("support.assistantCardAction")}
                  </Button>
                }
              />
            ) : (
              <div className={styles.articleList} style={{ padding: "var(--space-2)" }}>
                {listedArticles.map((article) => (
                  <Link key={article.slug} href={`/support/articles/${article.slug}`} className={styles.articleItem}>
                    <div className={styles.articleItemTitle}>{article.title}</div>
                    <div className={styles.articleItemCategory}>{t(CATEGORY_LABEL_KEYS[article.category])}</div>
                  </Link>
                ))}
              </div>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="green"
            icon={<TicketIcon />}
            title={t("support.myTicketsCardTitle")}
            subtitle={t("support.myTicketsCardDescription")}
            tight
            action={
              <Link href="/support/tickets" className={buttonClassName("ghost", "sm")}>
                {t("support.myTicketsCardAction")}
              </Link>
            }
          >
            {loadingTickets ? (
              <LoadingBlock label={t("support.tickets.loadingList")} />
            ) : tickets === null || tickets.length === 0 ? (
              <ZeroState
                accent="green"
                icon={<TicketIcon />}
                title={t("support.tickets.noTicketsTitle")}
                text={t("support.tickets.noTicketsDescription")}
                actions={
                  <Link href="/support/tickets/new" className={buttonClassName("primary", "sm")}>
                    {t("support.reportProblemCardAction")}
                  </Link>
                }
              />
            ) : (
              <InfoList>
                {tickets.slice(0, 6).map((ticket) => (
                  <InfoRow
                    key={ticket.id}
                    accent="green"
                    icon={<TicketIcon />}
                    href={`/support/tickets/${ticket.id}`}
                    label={ticket.subject}
                    meta={`${ticket.reference_code} · ${formatDate(locale, ticket.updated_at, { month: "short", day: "numeric" })}`}
                    value={<Badge tone={STATUS_TONE[ticket.status]}>{t(STATUS_LABEL_KEYS[ticket.status])}</Badge>}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>

          <WorkspacePanel accent="amber" icon={<ShieldIcon />} title={t("workspace.support.escalateTitle")} tight>
            <div style={{ padding: "var(--space-3) var(--space-4) var(--space-4)" }}>
              <p style={{ fontSize: "12.5px", lineHeight: 1.55, color: "var(--ai-muted)", marginBottom: "var(--space-3)" }}>
                {t("workspace.support.escalateText")}
              </p>
              <Link href="/support/tickets/new" className={buttonClassName("secondary", "sm", true)}>
                {t("workspace.support.escalateCta")}
              </Link>
            </div>
          </WorkspacePanel>

          <Disclosure accent="cyan" icon={<InsightIcon />} label={t("workspace.support.responseTitle")}>
            <StepList
              accent="green"
              steps={[
                { title: t("workspace.support.response.oneTitle"), description: t("workspace.support.response.oneDescription") },
                { title: t("workspace.support.response.twoTitle"), description: t("workspace.support.response.twoDescription") },
                { title: t("workspace.support.response.threeTitle"), description: t("workspace.support.response.threeDescription") },
                { title: t("workspace.support.response.fourTitle"), description: t("workspace.support.response.fourDescription") },
              ]}
            />
          </Disclosure>

          <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
            {t("workspace.support.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
