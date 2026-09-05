"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { documentsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, type TranslationKey } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock, Spinner } from "@/components/ui/Spinner";
import { UploadPanel } from "@/components/documents/UploadPanel";
import { LifecycleBadge } from "@/components/documents/LifecycleBadge";
import { DOCUMENT_TYPE_KEYS, formatFileSize, getLifecycleInfo } from "@/components/documents/lifecycle";
import { AskIcon, DocumentsIcon, GaugeIcon, InsightIcon, ShieldIcon, SparkIcon, UploadIcon } from "@/components/layout/icons";
import {
  ChipLink,
  ChipRow,
  Disclosure,
  Segmented,
  StatusLegend,
  StepList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
  type LegendItem,
  type SegmentOption,
} from "@/components/ui/Workspace";
import { DOCUMENT_TYPES, type DocumentPublic, type DocumentStatus } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

const STATUS_FILTER_VALUES: { value: DocumentStatus | ""; labelKey: TranslationKey }[] = [
  { value: "", labelKey: "documents.statusFilters.all" },
  { value: "uploaded", labelKey: "documents.statusFilters.uploaded" },
  { value: "processing", labelKey: "documents.statusFilters.processing" },
  { value: "processed", labelKey: "documents.statusFilters.processed" },
  { value: "failed", labelKey: "documents.statusFilters.failed" },
];

/** Folds the two backend lifecycles (status + indexing_status) into the five
 *  states the library actually shows. Every figure is a count of loaded rows. */
function countLifecycle(documents: DocumentPublic[]) {
  const counts = { ready: 0, processed: 0, processing: 0, uploaded: 0, failed: 0 };
  for (const doc of documents) {
    if (doc.status === "failed" || doc.indexing_status === "failed") counts.failed += 1;
    else if (doc.status === "processed" && doc.indexing_status === "indexed") counts.ready += 1;
    else if (doc.status === "processing" || doc.indexing_status === "indexing") counts.processing += 1;
    else if (doc.status === "processed") counts.processed += 1;
    else counts.uploaded += 1;
  }
  return counts;
}

export default function DocumentsPage() {
  const { role } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, locale } = useTranslation();
  const canManage = role === "owner" || role === "admin" || role === "manager";

  const [documents, setDocuments] = useState<DocumentPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [busyDocId, setBusyDocId] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "">("");
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await documentsApi.list({
        status: statusFilter || undefined,
        document_type: typeFilter || undefined,
        filename: search || undefined,
        limit: 20,
      });
      setDocuments(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("documents.errors.loadFailed")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, typeFilter, search]);

  useEffect(() => {
    const timeout = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, typeFilter, search]);

  useEffect(() => {
    if (searchParams.get("upload") === "1" && canManage) {
      setShowUpload(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await documentsApi.list({
        status: statusFilter || undefined,
        document_type: typeFilter || undefined,
        filename: search || undefined,
        limit: 20,
        cursor: nextCursor,
      });
      setDocuments((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("documents.errors.loadMoreFailed")));
    } finally {
      setLoadingMore(false);
    }
  }

  function replaceDocument(updated: DocumentPublic) {
    setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
  }

  async function handleAction(doc: DocumentPublic, action: "process" | "index") {
    setBusyDocId(doc.id);
    setError(null);
    try {
      const updated = action === "process" ? await documentsApi.process(doc.id) : await documentsApi.index(doc.id);
      replaceDocument(updated);
    } catch (err) {
      setError(
        errorMessage(
          err,
          t(action === "process" ? "documents.errors.processFailed" : "documents.errors.indexFailed", {
            name: doc.file_name,
          })
        )
      );
    } finally {
      setBusyDocId(null);
    }
  }

  const counts = useMemo(() => countLifecycle(documents), [documents]);
  const filtered = Boolean(statusFilter || typeFilter || search);

  function clearFilters() {
    setStatusFilter("");
    setTypeFilter("");
    setSearch("");
  }

  const statusOptions: SegmentOption<DocumentStatus | "">[] = STATUS_FILTER_VALUES.map((option) => ({
    value: option.value,
    label: t(option.labelKey),
  }));

  const lifecycleLegend: LegendItem[] = [
    {
      label: t("documents.lifecycle.ready"),
      description: t("workspace.documents.pipeline.readyDescription"),
      color: "#2fd48a",
      count: loading ? undefined : counts.ready,
    },
    {
      label: t("documents.lifecycle.processed"),
      description: t("workspace.documents.pipeline.indexDescription"),
      color: "#4d8dff",
      count: loading ? undefined : counts.processed,
    },
    {
      label: t("documents.lifecycle.processing"),
      description: t("workspace.documents.pipeline.processDescription"),
      color: "#8b6bff",
      count: loading ? undefined : counts.processing,
    },
    {
      label: t("documents.lifecycle.uploaded"),
      description: t("workspace.documents.pipeline.uploadDescription"),
      color: "#ffa43d",
      count: loading ? undefined : counts.uploaded,
    },
    // A stalled file is the one state somebody has to act on, so it belongs in
    // the pipeline breakdown rather than only on the row itself.
    {
      label: t("documents.statusFilters.failed"),
      description: t("workspace.documents.pipeline.failedDescription"),
      color: "#ff5470",
      count: loading ? undefined : counts.failed,
    },
  ];

  return (
    <WorkspacePage module="documents">
      <WorkspaceHero
        accent="cyan"
        compact
        badge={t("workspace.documents.badge")}
        icon={<DocumentsIcon />}
        title={t("documents.title")}
        description={t("workspace.documents.description")}
        actions={
          <>
            {canManage ? (
              <Button onClick={() => setShowUpload((v) => !v)}>
                {showUpload ? t("common.close") : t("documents.uploadDocument")}
              </Button>
            ) : null}
            <ChipRow>
              <ChipLink accent="violet" href="/ask" icon={<AskIcon />}>
                {t("workspace.documents.askCta")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.documents.metrics.libraryLabel"),
            value: loading ? "—" : documents.length,
            hint: t("workspace.documents.metrics.libraryHint"),
            icon: <DocumentsIcon />,
          },
          {
            label: t("workspace.documents.metrics.readyLabel"),
            value: loading ? "—" : counts.ready,
            hint: t("workspace.documents.metrics.readyHint"),
            icon: <ShieldIcon />,
          },
          {
            label: t("workspace.documents.metrics.pendingLabel"),
            value: loading ? "—" : counts.processed + counts.processing + counts.uploaded,
            hint: t("workspace.documents.metrics.pendingHint"),
            icon: <SparkIcon />,
          },
          {
            label: t("workspace.documents.metrics.failedLabel"),
            value: loading ? "—" : counts.failed,
            hint: t("workspace.documents.metrics.failedHint"),
            icon: <GaugeIcon />,
          },
        ]}
      />

      {showUpload ? (
        <UploadPanel
          onCancel={() => setShowUpload(false)}
          onUploaded={(doc) => {
            setDocuments((prev) => [doc, ...prev]);
            setShowUpload(false);
          }}
        />
      ) : null}

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <div className={toolbarStyles.toolbar} style={{ marginBottom: 0 }}>
            <div className={toolbarStyles.grow}>
              <Input
                placeholder={t("documents.searchPlaceholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className={toolbarStyles.field}>
              <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                <option value="">{t("documents.allTypes")}</option>
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(DOCUMENT_TYPE_KEYS[type])}
                  </option>
                ))}
              </Select>
            </div>
            <Segmented
              accent="cyan"
              ariaLabel={t("documents.statusFilters.all")}
              options={statusOptions}
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
            />
          </div>

          <WorkspacePanel
            accent="cyan"
            icon={<DocumentsIcon />}
            title={t("documents.title")}
            subtitle={loading ? undefined : t("documents.showingCount", { count: documents.length })}
            tight
          >
            {loading ? (
              <LoadingBlock label={t("documents.loadingList")} />
            ) : documents.length === 0 ? (
              filtered ? (
                <ZeroState
                  accent="blue"
                  icon={<DocumentsIcon />}
                  title={t("workspace.documents.emptyFilteredTitle")}
                  text={t("workspace.documents.emptyFilteredText")}
                  actions={
                    <Button size="sm" variant="secondary" onClick={clearFilters}>
                      {t("workspace.documents.clearFilters")}
                    </Button>
                  }
                />
              ) : (
                <ZeroState
                  accent="cyan"
                  icon={<UploadIcon />}
                  title={t("workspace.documents.emptyTitle")}
                  text={canManage ? t("workspace.documents.emptyManagerText") : t("workspace.documents.emptyMemberText")}
                  actions={
                    canManage ? (
                      <Button size="sm" onClick={() => setShowUpload(true)}>
                        {t("documents.uploadDocument")}
                      </Button>
                    ) : undefined
                  }
                />
              )
            ) : (
              <>
                <div className={tableStyles.wrap}>
                  <table className={tableStyles.table}>
                    <thead>
                      <tr>
                        <th>{t("documents.columns.file")}</th>
                        <th>{t("documents.columns.type")}</th>
                        <th>{t("documents.columns.status")}</th>
                        <th>{t("documents.columns.uploaded")}</th>
                        <th>{t("documents.columns.size")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => {
                        const info = getLifecycleInfo(doc);
                        const isBusy = busyDocId === doc.id;
                        return (
                          <tr
                            key={doc.id}
                            className={tableStyles.clickableRow}
                            onClick={() => router.push(`/documents/${doc.id}`)}
                          >
                            <td>{doc.file_name}</td>
                            <td className={tableStyles.muted}>{t(DOCUMENT_TYPE_KEYS[doc.document_type])}</td>
                            <td>
                              <LifecycleBadge document={doc} />
                            </td>
                            <td className={tableStyles.muted}>{formatDate(locale, doc.created_at)}</td>
                            <td className={tableStyles.muted}>{formatFileSize(doc.file_size_bytes)}</td>
                            <td onClick={(e) => e.stopPropagation()}>
                              {canManage && info.nextAction ? (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  disabled={isBusy}
                                  onClick={() => handleAction(doc, info.nextAction as "process" | "index")}
                                >
                                  {isBusy ? <Spinner size="sm" /> : t(info.nextActionLabelKey as TranslationKey)}
                                </Button>
                              ) : null}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {nextCursor ? (
                  <div className={tableStyles.footer}>
                    <span className={tableStyles.muted}>{t("documents.showingCount", { count: documents.length })}</span>
                    <Button size="sm" variant="secondary" onClick={loadMore} loading={loadingMore}>
                      {loadingMore ? t("common.loading") : t("common.loadMore")}
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="blue"
            icon={<GaugeIcon />}
            title={t("workspace.documents.pipelineTitle")}
            subtitle={t("workspace.documents.pipelineSubtitle")}
            tight
          >
            <StatusLegend items={lifecycleLegend} total={documents.length} />
            <div style={{ padding: "var(--space-2) var(--space-3) var(--space-3)" }}>
              <Link href="/ask" className={buttonClassName("secondary", "sm", true)}>
                {t("workspace.documents.askCta")}
              </Link>
            </div>
          </WorkspacePanel>

          <Disclosure accent="cyan" icon={<InsightIcon />} label={t("workspace.documents.usageTitle")}>
            <StepList
              accent="cyan"
              steps={[
                { title: t("workspace.documents.usage.retrievalTitle"), description: t("workspace.documents.usage.retrievalDescription") },
                { title: t("workspace.documents.usage.citationsTitle"), description: t("workspace.documents.usage.citationsDescription") },
                { title: t("workspace.documents.usage.scopeTitle"), description: t("workspace.documents.usage.scopeDescription") },
                { title: t("workspace.documents.usage.projectTitle"), description: t("workspace.documents.usage.projectDescription") },
              ]}
            />
          </Disclosure>

          <WorkspaceNote accent="cyan" icon={<ShieldIcon />}>
            {t("workspace.documents.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
