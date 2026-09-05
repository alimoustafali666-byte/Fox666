"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { projectsApi, reportsApi, type ReportFilters } from "@/lib/api-client";
import type { ProjectPublic } from "@/lib/types";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDateTime, type TranslationKey } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import clsx from "@/components/ui/clsx";
import { DocumentsIcon, GaugeIcon, InsightIcon, ReportsIcon, ShieldIcon, SparkIcon, TargetIcon } from "@/components/layout/icons";
import {
  Disclosure,
  PointList,
  StepList,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  ZeroState,
} from "@/components/ui/Workspace";
import { PROJECT_STATUS_KEYS } from "@/components/projects/statusLabels";
import { TASK_PRIORITY_KEYS, TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import { DOCUMENT_TYPE_KEYS } from "@/components/documents/lifecycle";
import { STATUS_LABEL_KEYS as TICKET_STATUS_KEYS } from "@/components/support/labels";
import {
  DOCUMENT_TYPES,
  PROJECT_STATUSES,
  SUPPORT_TICKET_STATUSES,
  TASK_DUE_FILTERS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  type ReportExportFormat,
  type ReportPreviewResponse,
  type ReportType,
  type ReportTypeInfo,
} from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";
import styles from "./Reports.module.css";

const DOCUMENT_STATUSES = ["uploaded", "processing", "processed", "failed"] as const;
const EXPORT_FORMATS: ReportExportFormat[] = ["csv", "xlsx", "docx", "pdf"];

const DOCUMENT_STATUS_KEYS: Record<(typeof DOCUMENT_STATUSES)[number], TranslationKey> = {
  uploaded: "documents.statusFilters.uploaded",
  processing: "documents.statusFilters.processing",
  processed: "documents.statusFilters.processed",
  failed: "documents.statusFilters.failed",
};

const DUE_FILTER_KEYS: Record<(typeof TASK_DUE_FILTERS)[number], TranslationKey> = {
  overdue: "tasks.dueFilters.overdue",
  due_today: "tasks.dueFilters.due_today",
  upcoming: "tasks.dueFilters.upcoming",
};

type FilterKey =
  | "status" | "priority" | "project_id" | "document_type" | "due_filter"
  | "search" | "date" | "date_from" | "date_to" | "action" | "resource_type";

const TYPE_FILTERS: Record<ReportType, FilterKey[]> = {
  projects: ["status", "project_id", "search"],
  documents: ["status", "project_id", "document_type", "search"],
  tasks: ["status", "project_id", "priority", "due_filter", "search"],
  daily_brief: ["date"],
  audit_log: ["action", "resource_type", "date_from", "date_to"],
  support_tickets: ["status"],
  collaboration: [],
};

export default function ReportsPage() {
  const { t, locale } = useTranslation();

  const [types, setTypes] = useState<ReportTypeInfo[]>([]);
  const [selectedType, setSelectedType] = useState<ReportType | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<ReportPreviewResponse | null>(null);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [exporting, setExporting] = useState<ReportExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectPublic[]>([]);

  useEffect(() => {
    projectsApi.list({ limit: 100 }).then((page) => setProjects(page.items)).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    reportsApi
      .listTypes()
      .then((list) => {
        setTypes(list);
        if (list.length > 0) setSelectedType(list[0].type);
      })
      .catch((err) => setError(errorMessage(err, t("reports.genericLoadError"))))
      .finally(() => setLoadingTypes(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeFilterKeys = useMemo(() => (selectedType ? TYPE_FILTERS[selectedType] : []), [selectedType]);

  const requestFilters: ReportFilters = useMemo(
    () => ({ ...filters, locale }),
    [filters, locale]
  );

  const loadPreview = useCallback(async () => {
    if (!selectedType) return;
    setLoadingPreview(true);
    setError(null);
    try {
      const result = await reportsApi.preview(selectedType, requestFilters);
      setPreview(result);
    } catch (err) {
      setError(errorMessage(err, t("reports.genericLoadError")));
      setPreview(null);
    } finally {
      setLoadingPreview(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedType, requestFilters]);

  useEffect(() => {
    const timeout = setTimeout(loadPreview, filters.search ? 300 : 0);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedType, filters, locale]);

  function selectType(type: ReportType) {
    setSelectedType(type);
    setFilters({});
    setPreview(null);
  }

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  async function handleExport(format: ReportExportFormat) {
    if (!selectedType) return;
    setExporting(format);
    setError(null);
    try {
      const { blob, filename } = await reportsApi.download(selectedType, format, requestFilters);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename || `report.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errorMessage(err, t("reports.genericExportError")));
    } finally {
      setExporting(null);
    }
  }

  function handlePrint() {
    window.print();
  }

  const typeTitle = (info: ReportTypeInfo) => (locale === "ar" ? info.title_ar : info.title_en);
  const selectedInfo = types.find((info) => info.type === selectedType) ?? null;
  const hasFilters = Object.keys(filters).length > 0;

  return (
    <WorkspacePage module="reports">
      <div className={styles.noPrint}>
        <WorkspaceHero
          accent="magenta"
          compact
          badge={t("workspace.reports.badge")}
          icon={<ReportsIcon />}
          title={t("reports.title")}
          description={t("workspace.reports.description")}
          metrics={[
            {
              label: t("workspace.reports.metrics.typesLabel"),
              value: loadingTypes ? "—" : types.length,
              hint: t("workspace.reports.metrics.typesHint"),
              icon: <ReportsIcon />,
            },
            {
              label: t("workspace.reports.metrics.rowsLabel"),
              value: loadingPreview ? "—" : preview ? preview.meta.row_count : t("workspace.reports.metrics.noneValue"),
              hint: t("workspace.reports.metrics.rowsHint"),
              icon: <GaugeIcon />,
            },
            {
              label: t("workspace.reports.metrics.formatsLabel"),
              value: EXPORT_FORMATS.length,
              hint: t("workspace.reports.metrics.formatsHint"),
              icon: <SparkIcon />,
            },
            {
              label: t("workspace.reports.metrics.referenceLabel"),
              value: (
                <span style={{ fontSize: 14, fontFamily: "var(--font-mono)" }}>
                  {preview ? preview.meta.reference_number : t("workspace.reports.metrics.noneValue")}
                </span>
              ),
              hint: t("workspace.reports.metrics.referenceHint"),
              icon: <ShieldIcon />,
            },
          ]}
        />
      </div>

      {error ? (
        <div className={styles.noPrint}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      {loadingTypes ? (
        <LoadingBlock label={t("reports.loadingTypes")} />
      ) : types.length === 0 ? (
        <WorkspacePanel accent="magenta" icon={<ReportsIcon />} title={t("reports.title")} tight>
          <ZeroState
            accent="magenta"
            icon={<ReportsIcon />}
            title={t("reports.noTypesTitle")}
            text={t("reports.noTypesDescription")}
          />
        </WorkspacePanel>
      ) : (
        <>
          <div className={clsx(styles.pickerBar, styles.noPrint)}>
            <div className={styles.pickerLabel}>{t("workspace.reports.catalogueTitle")}</div>
            <div className={styles.typeRow}>
              {types.map((info) => (
                <button
                  key={info.type}
                  type="button"
                  className={clsx(styles.typeChip, selectedType === info.type && styles.typeChipActive)}
                  onClick={() => selectType(info.type)}
                >
                  {typeTitle(info)}
                </button>
              ))}
            </div>
          </div>

          {activeFilterKeys.length > 0 ? (
            <div className={clsx(toolbarStyles.toolbar, styles.noPrint)} style={{ marginBottom: 0 }}>
              {activeFilterKeys.includes("search") ? (
                <div className={toolbarStyles.grow}>
                  <Input
                    placeholder={t("reports.searchPlaceholder")}
                    value={filters.search ?? ""}
                    onChange={(e) => setFilter("search", e.target.value)}
                  />
                </div>
              ) : null}
              {activeFilterKeys.includes("project_id") ? (
                <div className={toolbarStyles.field}>
                  <Select value={filters.project_id ?? ""} onChange={(e) => setFilter("project_id", e.target.value)}>
                    <option value="">{t("reports.allProjects")}</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null}
              {activeFilterKeys.includes("status") ? (
                <div className={toolbarStyles.field}>
                  <Select value={filters.status ?? ""} onChange={(e) => setFilter("status", e.target.value)}>
                    <option value="">{t("reports.allStatuses")}</option>
                    {selectedType === "documents"
                      ? DOCUMENT_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {t(DOCUMENT_STATUS_KEYS[s])}
                          </option>
                        ))
                      : selectedType === "tasks"
                        ? TASK_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {t(TASK_STATUS_KEYS[s])}
                            </option>
                          ))
                        : selectedType === "support_tickets"
                          ? SUPPORT_TICKET_STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {t(TICKET_STATUS_KEYS[s])}
                              </option>
                            ))
                          : PROJECT_STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {t(PROJECT_STATUS_KEYS[s])}
                              </option>
                            ))}
                  </Select>
                </div>
              ) : null}
              {activeFilterKeys.includes("priority") ? (
                <div className={toolbarStyles.field}>
                  <Select value={filters.priority ?? ""} onChange={(e) => setFilter("priority", e.target.value)}>
                    <option value="">{t("reports.allPriorities")}</option>
                    {TASK_PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {t(TASK_PRIORITY_KEYS[p])}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null}
              {activeFilterKeys.includes("due_filter") ? (
                <div className={toolbarStyles.field}>
                  <Select value={filters.due_filter ?? ""} onChange={(e) => setFilter("due_filter", e.target.value)}>
                    <option value="">{t("reports.allDueDates")}</option>
                    {TASK_DUE_FILTERS.map((d) => (
                      <option key={d} value={d}>
                        {t(DUE_FILTER_KEYS[d])}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null}
              {activeFilterKeys.includes("document_type") ? (
                <div className={toolbarStyles.field}>
                  <Select value={filters.document_type ?? ""} onChange={(e) => setFilter("document_type", e.target.value)}>
                    <option value="">{t("reports.allTypes")}</option>
                    {DOCUMENT_TYPES.map((dt) => (
                      <option key={dt} value={dt}>
                        {t(DOCUMENT_TYPE_KEYS[dt])}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null}
              {activeFilterKeys.includes("date") ? (
                <div className={toolbarStyles.field}>
                  <Input type="date" value={filters.date ?? ""} onChange={(e) => setFilter("date", e.target.value)} />
                </div>
              ) : null}
              {activeFilterKeys.includes("date_from") ? (
                <div className={toolbarStyles.field}>
                  <Input
                    type="date"
                    placeholder={t("reports.dateFrom")}
                    value={filters.date_from ?? ""}
                    onChange={(e) => setFilter("date_from", e.target.value)}
                  />
                </div>
              ) : null}
              {activeFilterKeys.includes("date_to") ? (
                <div className={toolbarStyles.field}>
                  <Input
                    type="date"
                    placeholder={t("reports.dateTo")}
                    value={filters.date_to ?? ""}
                    onChange={(e) => setFilter("date_to", e.target.value)}
                  />
                </div>
              ) : null}
              {activeFilterKeys.includes("action") ? (
                <div className={toolbarStyles.field}>
                  <Input
                    placeholder={t("reports.actionPlaceholder")}
                    value={filters.action ?? ""}
                    onChange={(e) => setFilter("action", e.target.value)}
                  />
                </div>
              ) : null}
              {activeFilterKeys.includes("resource_type") ? (
                <div className={toolbarStyles.field}>
                  <Input
                    placeholder={t("reports.resourceTypePlaceholder")}
                    value={filters.resource_type ?? ""}
                    onChange={(e) => setFilter("resource_type", e.target.value)}
                  />
                </div>
              ) : null}
              {hasFilters ? (
                <Button size="sm" variant="ghost" onClick={() => setFilters({})}>
                  {t("workspace.documents.clearFilters")}
                </Button>
              ) : null}
            </div>
          ) : null}

          <WorkspacePanel
            accent="magenta"
            icon={<ReportsIcon />}
            className={styles.printCard}
            title={preview ? preview.meta.title : selectedInfo ? typeTitle(selectedInfo) : t("reports.title")}
            subtitle={
              preview
                ? `${preview.meta.company_name} · ${t("reports.referenceLabel")}: ${preview.meta.reference_number}`
                : undefined
            }
            action={
              <div className={clsx(styles.exportRow, styles.noPrint)}>
                {EXPORT_FORMATS.map((fmt) => (
                  <Button
                    key={fmt}
                    size="sm"
                    variant="secondary"
                    loading={exporting === fmt}
                    disabled={!preview || preview.meta.row_count === 0 || exporting !== null}
                    onClick={() => handleExport(fmt)}
                  >
                    {fmt.toUpperCase()}
                  </Button>
                ))}
                <button type="button" className={buttonClassName("secondary", "sm")} onClick={handlePrint} disabled={!preview}>
                  {t("reports.printButton")}
                </button>
              </div>
            }
          >
            {loadingPreview ? (
              <LoadingBlock label={t("reports.loadingPreview")} />
            ) : !selectedType ? (
              <ZeroState
                accent="magenta"
                icon={<ReportsIcon />}
                title={t("workspace.reports.emptyNoSelectionTitle")}
                text={t("workspace.reports.emptyNoSelectionText")}
              />
            ) : !preview || preview.rows.length === 0 ? (
              <ZeroState
                accent="violet"
                icon={<ReportsIcon />}
                title={t("workspace.reports.emptyTitle")}
                text={t("workspace.reports.emptyText")}
                actions={
                  hasFilters ? (
                    <Button size="sm" variant="secondary" onClick={() => setFilters({})}>
                      {t("workspace.documents.clearFilters")}
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <>
                <div className={styles.printMeta}>
                  <div className={styles.printTitle}>{preview.meta.title}</div>
                  <div>{preview.meta.company_name}</div>
                  <div>
                    {t("reports.generatedBy", { name: preview.meta.generated_by, date: formatDateTime(locale, preview.meta.generated_at) })}
                  </div>
                  <div>
                    {t("reports.referenceLabel")}: {preview.meta.reference_number}
                  </div>
                  {preview.meta.filters_summary ? <div>{preview.meta.filters_summary}</div> : null}
                </div>
                <div className={tableStyles.wrap}>
                  <table className={tableStyles.table}>
                    <thead>
                      <tr>
                        {preview.columns.map((col) => (
                          <th key={col.key}>{col.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((row, i) => (
                        <tr key={i}>
                          {preview.columns.map((col) => (
                            <td key={col.key}>{row[col.key] || t("common.emptyValue")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={clsx(tableStyles.footer, styles.noPrint)}>
                  <span className={tableStyles.muted}>{t("reports.showingCount", { count: preview.meta.row_count })}</span>
                </div>
              </>
            )}
          </WorkspacePanel>

          <div className={clsx(styles.guidance, styles.noPrint)}>
            <Disclosure accent="magenta" icon={<InsightIcon />} label={t("workspace.reports.howTitle")}>
              <StepList
                accent="violet"
                steps={[
                  { title: t("workspace.reports.steps.chooseTitle"), description: t("workspace.reports.steps.chooseDescription") },
                  { title: t("workspace.reports.steps.filterTitle"), description: t("workspace.reports.steps.filterDescription") },
                  { title: t("workspace.reports.steps.previewTitle"), description: t("workspace.reports.steps.previewDescription") },
                  { title: t("workspace.reports.steps.exportTitle"), description: t("workspace.reports.steps.exportDescription") },
                ]}
              />
            </Disclosure>
            <Disclosure accent="amber" icon={<TargetIcon />} label={t("workspace.reports.exportTitle")}>
              <PointList
                accent="amber"
                items={[
                  { icon: <ReportsIcon />, title: t("workspace.reports.exports.pdfTitle"), text: t("workspace.reports.exports.pdfDescription") },
                  { icon: <DocumentsIcon />, title: t("workspace.reports.exports.docxTitle"), text: t("workspace.reports.exports.docxDescription") },
                  { icon: <GaugeIcon />, title: t("workspace.reports.exports.xlsxTitle"), text: t("workspace.reports.exports.xlsxDescription") },
                  { icon: <SparkIcon />, title: t("workspace.reports.exports.csvTitle"), text: t("workspace.reports.exports.csvDescription") },
                ]}
              />
            </Disclosure>
          </div>

          <div className={styles.noPrint}>
            <WorkspaceNote accent="magenta" icon={<ShieldIcon />}>
              {t("workspace.reports.note")}
            </WorkspaceNote>
          </div>
        </>
      )}
    </WorkspacePage>
  );
}
