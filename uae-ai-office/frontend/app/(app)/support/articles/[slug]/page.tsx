"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiError, supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import { buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  InfoList,
  InfoRow,
  SkeletonRows,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
} from "@/components/ui/Workspace";
import { BrainIcon, DocumentsIcon, HelpIcon, ShieldIcon, TicketIcon } from "@/components/layout/icons";
import { CATEGORY_LABEL_KEYS } from "@/components/support/labels";
import type { SupportArticlePublic } from "@/lib/types";
import styles from "../../Support.module.css";

export default function SupportArticlePage() {
  const params = useParams<{ slug: string }>();
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";

  const [article, setArticle] = useState<SupportArticlePublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const result = await supportApi.getArticle(params.slug, locale);
      setArticle(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setNotFound(true);
      } else {
        setError(errorMessage(err, t("support.article.genericLoadError")));
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.slug, locale]);

  useEffect(() => {
    load();
  }, [load]);

  /** The "still stuck?" column is the same whatever the article says, so it
   *  renders in every state -- the page is never one lonely card. */
  const helpColumn = (
    <WorkspaceColumn>
      <WorkspacePanel accent="cyan" icon={<HelpIcon />} title={t("workspace.article.helpfulTitle")} tight>
        <InfoList>
          <InfoRow
            accent="violet"
            icon={<BrainIcon />}
            href="/support/assistant"
            label={t("workspace.article.helpful.assistantTitle")}
            meta={t("workspace.article.helpful.assistantDescription")}
          />
          <InfoRow
            accent="magenta"
            icon={<TicketIcon />}
            href="/support/tickets/new"
            label={t("workspace.article.helpful.ticketTitle")}
            meta={t("workspace.article.helpful.ticketDescription")}
          />
          <InfoRow
            accent="blue"
            icon={<DocumentsIcon />}
            href="/support"
            label={t("workspace.article.helpful.centreTitle")}
            meta={t("workspace.article.helpful.centreDescription")}
          />
        </InfoList>
      </WorkspacePanel>

      <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
        {t("workspace.article.note")}
      </WorkspaceNote>
    </WorkspaceColumn>
  );

  return (
    <WorkspacePage module="support">
      <Link href="/support" className={styles.backLink}>
        {backArrow} {t("support.article.backLink")}
      </Link>

      <WorkspaceHero
        accent="cyan"
        badge={t("workspace.article.badge")}
        icon={<HelpIcon />}
        title={article ? article.title : t("nav.help")}
        actions={
          article ? (
            <>
              <Badge tone="primary">{t(CATEGORY_LABEL_KEYS[article.category])}</Badge>
              <Link href="/support/assistant" className={buttonClassName("secondary", "md")}>
                {t("workspace.article.helpful.assistantTitle")}
              </Link>
            </>
          ) : undefined
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="cyan"
            icon={<DocumentsIcon />}
            title={article ? article.title : t("nav.help")}
          >
            {loading ? (
              <SkeletonRows count={6} />
            ) : notFound ? (
              <ErrorBanner message={t("support.article.notFound")} />
            ) : error ? (
              <ErrorBanner message={error} />
            ) : article ? (
              <p className={styles.articleBody}>{article.body}</p>
            ) : null}
          </WorkspacePanel>
        </WorkspaceColumn>

        {helpColumn}
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
