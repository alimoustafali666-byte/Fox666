"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { AskIcon, DocumentsIcon, TicketIcon } from "@/components/layout/icons";
import { CATEGORY_LABEL_KEYS } from "@/components/support/labels";
import { SUPPORT_TICKET_CATEGORIES, type SupportArticlePublic, type SupportTicketCategory } from "@/lib/types";
import clsx from "@/components/ui/clsx";
import styles from "./Support.module.css";

export default function SupportCenterPage() {
  const { company } = useAuth();
  const { t, locale } = useTranslation();
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SupportArticlePublic[] | null>(null);
  const [articles, setArticles] = useState<SupportArticlePublic[]>([]);
  const [activeCategory, setActiveCategory] = useState<SupportTicketCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    supportApi
      .listArticles({ locale, category: activeCategory ?? undefined })
      .then((page) => setArticles(page.items))
      .catch((err) => setError(errorMessage(err, t("support.genericLoadError"))))
      .finally(() => setLoading(false));
  }, [locale, t, activeCategory]);

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

  return (
    <div>
      <PageHeader title={t("support.title")} description={t("support.description")} />

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
          />
        </div>
        <Button type="submit" loading={searching}>
          {t("support.searchButton")}
        </Button>
      </form>

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      {searchResults !== null ? (
        <div style={{ marginBottom: "var(--space-8)" }}>
          <Card>
            <CardHeader title={t("support.searchResultsTitle")} />
            <CardBody tight>
              {searchResults.length === 0 ? (
                <div style={{ padding: "var(--space-5)" }}>
                  <EmptyState
                    title={t("support.searchNoResultsTitle")}
                    description={t("support.searchNoResultsDescription")}
                    action={
                      <Button size="sm" onClick={() => router.push("/support/assistant")}>
                        {t("support.assistantCardAction")}
                      </Button>
                    }
                  />
                </div>
              ) : (
                <div className={styles.articleList} style={{ padding: "var(--space-2)" }}>
                  {searchResults.map((article) => (
                    <Link
                      key={article.slug}
                      href={`/support/articles/${article.slug}`}
                      className={styles.articleItem}
                    >
                      <div className={styles.articleItemTitle}>{article.title}</div>
                      <div className={styles.articleItemCategory}>
                        {t(CATEGORY_LABEL_KEYS[article.category])}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}

      <div className={styles.actionGrid}>
        <Link href="/support/assistant" className={styles.actionCard}>
          <span className={styles.actionIcon}>
            <AskIcon />
          </span>
          <span>
            <div className={styles.actionTitle}>{t("support.assistantCardTitle")}</div>
            <div className={styles.actionDescription}>{t("support.assistantCardDescription")}</div>
          </span>
        </Link>
        <Link href="/support/tickets/new" className={styles.actionCard}>
          <span className={styles.actionIcon}>
            <DocumentsIcon />
          </span>
          <span>
            <div className={styles.actionTitle}>{t("support.reportProblemCardTitle")}</div>
            <div className={styles.actionDescription}>{t("support.reportProblemCardDescription")}</div>
          </span>
        </Link>
        <Link href="/support/tickets" className={styles.actionCard}>
          <span className={styles.actionIcon}>
            <TicketIcon />
          </span>
          <span>
            <div className={styles.actionTitle}>{t("support.myTicketsCardTitle")}</div>
            <div className={styles.actionDescription}>{t("support.myTicketsCardDescription")}</div>
          </span>
        </Link>
      </div>

      <div className={styles.sectionLabel}>{t("support.browseByTopicTitle")}</div>
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

      <Card>
        <CardHeader
          title={t("support.articlesCardTitle")}
          subtitle={activeCategory ? t(CATEGORY_LABEL_KEYS[activeCategory]) : t("support.articlesCardDescription")}
        />
        <CardBody tight>
          {loading ? (
            <LoadingBlock label={t("support.tickets.loadingList")} />
          ) : (
            <div className={styles.articleList} style={{ padding: "var(--space-2)" }}>
              {articles.map((article) => (
                <Link
                  key={article.slug}
                  href={`/support/articles/${article.slug}`}
                  className={styles.articleItem}
                >
                  <div className={styles.articleItemTitle}>{article.title}</div>
                  <div className={styles.articleItemCategory}>
                    {t(CATEGORY_LABEL_KEYS[article.category])}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {company ? (
        <div style={{ marginTop: "var(--space-6)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
          {company.name} · {company.country}
        </div>
      ) : null}
    </div>
  );
}

