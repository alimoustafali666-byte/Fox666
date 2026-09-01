"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { errorMessage } from "@/lib/auth-context";
import { documentsApi } from "@/lib/api-client";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { LifecycleBadge } from "@/components/documents/LifecycleBadge";
import { LifecycleStepper } from "@/components/documents/LifecycleStepper";
import { DOCUMENT_TYPE_KEYS, formatFileSize, getLifecycleInfo } from "@/components/documents/lifecycle";
import type { DocumentPublic } from "@/lib/types";
import styles from "../DetailPage.module.css";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { role } = useAuth();
  const { t, dir, locale } = useTranslation();
  const canManage = role === "owner" || role === "admin" || role === "manager";
  const canDelete = role === "owner" || role === "admin";
  const backArrow = dir === "rtl" ? "→" : "←";

  const [doc, setDoc] = useState<DocumentPublic | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<"process" | "index" | "download" | "delete" | "refresh" | null>(null);

  const load = useCallback(async () => {
    if (!doc) setLoading(true);
    setError(null);
    try {
      const document = await documentsApi.get(params.id);
      setDoc(document);
    } catch (err) {
      setError(errorMessage(err, t("documents.detail.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!doc || (doc.status !== "processing" && doc.indexing_status !== "indexing")) return;
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [doc, load]);

  async function handleLifecycleAction(action: "process" | "index") {
    setActionBusy(action);
    setError(null);
    try {
      const updated = action === "process" ? await documentsApi.process(params.id) : await documentsApi.index(params.id);
      setDoc(updated);
    } catch (err) {
      setError(
        errorMessage(
          err,
          t(action === "process" ? "documents.detail.genericProcessError" : "documents.detail.genericIndexError")
        )
      );
    } finally {
      setActionBusy(null);
    }
  }

  async function handleDownload() {
    setActionBusy("download");
    setError(null);
    try {
      const { download_url } = await documentsApi.getDownloadUrl(params.id);
      window.open(download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(errorMessage(err, t("documents.detail.genericDownloadError")));
    } finally {
      setActionBusy(null);
    }
  }

  async function handlePreview() {
    if (!doc) return;
    setActionBusy("download");
    setError(null);
    try {
      const { download_url } = await documentsApi.getDownloadUrl(params.id);
      setPreviewUrl(download_url);
      const mime = (doc.file_type || "").toLowerCase();
      if (mime === "application/pdf" || mime.startsWith("image/") || mime.startsWith("text/") || mime.includes("json") || mime.includes("xml") || mime.includes("svg")) {
        return;
      }
      window.open(download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(errorMessage(err, t("documents.detail.genericDownloadError")));
    } finally {
      setActionBusy(null);
    }
  }

  async function handleRefresh() {
    setActionBusy("refresh");
    await load();
    setActionBusy(null);
  }

  async function handleDelete() {
    if (!window.confirm(t("documents.detail.confirmDelete"))) return;
    setActionBusy("delete");
    setError(null);
    try {
      await documentsApi.remove(params.id);
      router.push("/documents");
    } catch (err) {
      setError(errorMessage(err, t("documents.detail.genericDeleteError")));
      setActionBusy(null);
    }
  }

  if (loading) return <LoadingBlock label={t("documents.loadingList")} />;

  if (!doc) {
    return (
      <div>
        <Link href="/documents" className={styles.backLink}>
          {backArrow} {t("documents.detail.backLink")}
        </Link>
        <ErrorBanner message={error ?? t("documents.detail.notFound")} />
      </div>
    );
  }

  const info = getLifecycleInfo(doc);

  return (
    <div>
      <Link href="/documents" className={styles.backLink}>
        {backArrow} {t("documents.detail.backLink")}
      </Link>

      <PageHeader
        title={doc.file_name}
        description={`${t(DOCUMENT_TYPE_KEYS[doc.document_type])} · ${formatFileSize(doc.file_size_bytes)}`}
        actions={<LifecycleBadge document={doc} />}
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      {info.errorMessage ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={info.errorMessage} />
        </div>
      ) : null}

      <div style={{ marginBottom: "var(--space-4)" }}>
        <Card>
          <CardBody>
            <div className={styles.stepperLabel}>{t("documents.detail.lifecycleTitle")}</div>
            <LifecycleStepper document={doc} />
            <div className={styles.stepperNote}>{t("documents.detail.manualStepsNote")}</div>
          </CardBody>
        </Card>
      </div>

      {previewUrl ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <Card>
            <CardBody>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
                <strong>{t("documents.detail.preview")}</strong>
                <Button size="sm" variant="secondary" onClick={() => window.open(previewUrl, "_blank", "noopener,noreferrer")}>
                  {t("documents.detail.download")}
                </Button>
              </div>
              <iframe
                title={doc.file_name}
                src={previewUrl}
                style={{ width: "100%", minHeight: "720px", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)" }}
              />
            </CardBody>
          </Card>
        </div>
      ) : null}

      <Card>
        <CardBody>
          <div className={styles.grid}>
            <div>
              <div className={styles.metaLabel}>{t("documents.detail.uploadedLabel")}</div>
              <div className={styles.metaValue}>{formatDateTime(locale, doc.created_at)}</div>
            </div>
            <div>
              <div className={styles.metaLabel}>{t("documents.detail.lastUpdatedLabel")}</div>
              <div className={styles.metaValue}>{formatDateTime(locale, doc.updated_at)}</div>
            </div>
            <div>
              <div className={styles.metaLabel}>{t("documents.detail.fileTypeLabel")}</div>
              <div className={styles.metaValue}>{doc.file_type}</div>
            </div>
          </div>

          <div className={styles.actions}>
            <Button variant="secondary" onClick={handleRefresh} loading={actionBusy === "refresh"}>
              {actionBusy === "refresh" ? t("common.loading") : t("documents.detail.refresh")}
            </Button>
            <Button variant="secondary" onClick={handleDownload} loading={actionBusy === "download"}>
              {actionBusy === "download" ? t("documents.detail.preparing") : t("documents.detail.download")}
            </Button>
            {doc.file_type === "application/pdf" ? <Button variant="secondary" onClick={handlePreview}>{t("documents.detail.preview")}</Button> : null}
            {canManage && info.nextAction ? (
              <Button
                variant="secondary"
                onClick={() => handleLifecycleAction(info.nextAction as "process" | "index")}
                loading={actionBusy === info.nextAction}
              >
                {actionBusy === info.nextAction ? t("documents.detail.working") : t(info.nextActionLabelKey!)}
              </Button>
            ) : null}
            {canDelete ? (
              <Button variant="danger" onClick={handleDelete} loading={actionBusy === "delete"}>
                {actionBusy === "delete" ? t("common.deleting") : t("documents.detail.deleteButton")}
              </Button>
            ) : null}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

