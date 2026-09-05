"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { errorMessage } from "@/lib/auth-context";
import { documentsApi } from "@/lib/api-client";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
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
import {
  AskIcon,
  BoltIcon,
  ClockIcon,
  DocumentsIcon,
  GaugeIcon,
  ProjectsIcon,
  ReportsIcon,
  ShieldIcon,
} from "@/components/layout/icons";
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

  if (loading) {
    return (
      <WorkspacePage module="documents">
        <Link href="/documents" className={styles.backLink}>
          {backArrow} {t("documents.detail.backLink")}
        </Link>
        <WorkspacePanel accent="cyan" icon={<DocumentsIcon />} title={t("documents.loadingList")}>
          <SkeletonRows count={6} />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  if (!doc) {
    return (
      <WorkspacePage module="documents">
        <Link href="/documents" className={styles.backLink}>
          {backArrow} {t("documents.detail.backLink")}
        </Link>
        <ErrorBanner message={error ?? t("documents.detail.notFound")} />
      </WorkspacePage>
    );
  }

  const info = getLifecycleInfo(doc);

  return (
    <WorkspacePage module="documents">
      <Link href="/documents" className={styles.backLink}>
        {backArrow} {t("documents.detail.backLink")}
      </Link>

      {error ? <ErrorBanner message={error} /> : null}
      {info.errorMessage ? <ErrorBanner message={info.errorMessage} /> : null}

      <WorkspaceHero
        accent="cyan"
        badge={t("workspace.documentDetail.badge")}
        icon={<DocumentsIcon />}
        title={doc.file_name}
        description={`${t(DOCUMENT_TYPE_KEYS[doc.document_type])} \u00b7 ${formatFileSize(doc.file_size_bytes)}`}
        actions={
          <>
            <LifecycleBadge document={doc} />
            {canManage && info.nextAction ? (
              <Button
                size="md"
                onClick={() => handleLifecycleAction(info.nextAction as "process" | "index")}
                loading={actionBusy === info.nextAction}
              >
                {actionBusy === info.nextAction ? t("documents.detail.working") : t(info.nextActionLabelKey!)}
              </Button>
            ) : null}
            <Button size="md" variant="secondary" onClick={handleDownload} loading={actionBusy === "download"}>
              {actionBusy === "download" ? t("documents.detail.preparing") : t("documents.detail.download")}
            </Button>
          </>
        }
        metrics={[
          {
            label: t("workspace.documentDetail.metrics.statusLabel"),
            value: <span style={{ fontSize: 15 }}>{t(info.labelKey)}</span>,
            hint: t("workspace.documentDetail.metrics.statusHint"),
            icon: <GaugeIcon />,
          },
          {
            label: t("workspace.documentDetail.metrics.typeLabel"),
            value: <span style={{ fontSize: 15 }}>{t(DOCUMENT_TYPE_KEYS[doc.document_type])}</span>,
            hint: t("workspace.documentDetail.metrics.typeHint"),
            icon: <DocumentsIcon />,
          },
          {
            label: t("workspace.documentDetail.metrics.sizeLabel"),
            value: <span style={{ fontSize: 15 }}>{formatFileSize(doc.file_size_bytes)}</span>,
            hint: t("workspace.documentDetail.metrics.sizeHint"),
            icon: <BoltIcon />,
          },
          {
            label: t("workspace.documentDetail.metrics.uploadedLabel"),
            value: <span style={{ fontSize: 15 }}>{formatDateTime(locale, doc.created_at)}</span>,
            hint: t("workspace.documentDetail.metrics.uploadedHint"),
            icon: <ClockIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="cyan" icon={<GaugeIcon />} title={t("documents.detail.lifecycleTitle")}>
            <LifecycleStepper document={doc} />
            <div className={styles.stepperNote}>{t("documents.detail.manualStepsNote")}</div>
          </WorkspacePanel>

          {previewUrl ? (
            <WorkspacePanel
              accent="blue"
              icon={<DocumentsIcon />}
              title={t("documents.detail.preview")}
              action={
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => window.open(previewUrl, "_blank", "noopener,noreferrer")}
                >
                  {t("documents.detail.download")}
                </Button>
              }
            >
              <iframe
                title={doc.file_name}
                src={previewUrl}
                style={{
                  width: "100%",
                  minHeight: "720px",
                  border: "1px solid var(--ai-line)",
                  borderRadius: "var(--ai-r-md)",
                }}
              />
            </WorkspacePanel>
          ) : null}

          <WorkspacePanel accent="violet" icon={<AskIcon />} title={t("workspace.documentDetail.useTitle")} tight>
            <InfoList>
              <InfoRow
                accent="violet"
                icon={<AskIcon />}
                href="/ask"
                label={t("workspace.documentDetail.use.askTitle")}
                meta={t("workspace.documentDetail.use.askDescription")}
              />
              <InfoRow
                accent="green"
                icon={<ReportsIcon />}
                href="/reports"
                label={t("workspace.documentDetail.use.reportsTitle")}
                meta={t("workspace.documentDetail.use.reportsDescription")}
              />
              <InfoRow
                accent="blue"
                icon={<ProjectsIcon />}
                href="/projects"
                label={t("workspace.documentDetail.use.projectTitle")}
                meta={t("workspace.documentDetail.use.projectDescription")}
              />
            </InfoList>
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel accent="blue" icon={<DocumentsIcon />} title={t("documents.detail.lifecycleTitle")}>
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
              {doc.file_type === "application/pdf" ? (
                <Button variant="secondary" onClick={handlePreview}>
                  {t("documents.detail.preview")}
                </Button>
              ) : null}
              {canDelete ? (
                <Button variant="danger" onClick={handleDelete} loading={actionBusy === "delete"}>
                  {actionBusy === "delete" ? t("common.deleting") : t("documents.detail.deleteButton")}
                </Button>
              ) : null}
            </div>
          </WorkspacePanel>

          <WorkspacePanel accent="green" icon={<DocumentsIcon />} title={t("nav.documents")} tight>
            <div style={{ padding: "var(--space-3)" }}>
              <Link href="/documents" className={buttonClassName("secondary", "sm", true)}>
                {t("nav.documents")}
              </Link>
            </div>
          </WorkspacePanel>

          <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
            {t("workspace.documentDetail.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
