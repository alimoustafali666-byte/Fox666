"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiError, supportApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
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

  return (
    <div>
      <Link href="/support" className={styles.backLink}>
        {backArrow} {t("support.article.backLink")}
      </Link>

      {loading ? (
        <LoadingBlock label={t("support.genericLoadError")} />
      ) : notFound ? (
        <ErrorBanner message={t("support.article.notFound")} />
      ) : error ? (
        <ErrorBanner message={error} />
      ) : article ? (
        <>
          <PageHeader
            title={article.title}
            actions={<Badge tone="primary">{t(CATEGORY_LABEL_KEYS[article.category])}</Badge>}
          />
          <Card>
            <CardBody>
              <p className={styles.articleBody}>{article.body}</p>
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}

