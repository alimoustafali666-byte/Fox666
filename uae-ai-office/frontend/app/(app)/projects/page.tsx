"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { projectsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, type TranslationKey } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ProjectFormPanel } from "@/components/projects/ProjectFormPanel";
import {
  DocumentsIcon,
  GaugeIcon,
  InsightIcon,
  ProjectsIcon,
  PulseIcon,
  ReportsIcon,
  ShieldIcon,
  TargetIcon,
  TasksIcon,
} from "@/components/layout/icons";
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
import { PROJECT_STATUS_KEYS, PROJECT_STATUS_TONE } from "@/components/projects/statusLabels";
import { PROJECT_STATUSES, type ProjectPublic, type ProjectStatus } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

const STATUS_COLOR: Record<ProjectStatus, string> = {
  planning: "#8b6bff",
  active: "#2fd48a",
  on_hold: "#ffa43d",
  completed: "#4d8dff",
  cancelled: "#6b7c96",
};

const STATUS_DESCRIPTION_KEYS: Record<ProjectStatus, TranslationKey> = {
  planning: "workspace.projects.statusDescriptions.planning",
  active: "workspace.projects.statusDescriptions.active",
  on_hold: "workspace.projects.statusDescriptions.on_hold",
  completed: "workspace.projects.statusDescriptions.completed",
  cancelled: "workspace.projects.statusDescriptions.cancelled",
};

export default function ProjectsPage() {
  const { role } = useAuth();
  const { t, locale } = useTranslation();
  const canManage = role === "owner" || role === "admin" || role === "manager";
  const canDelete = role === "owner" || role === "admin";

  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | "">("");
  const [search, setSearch] = useState("");

  const [panelMode, setPanelMode] = useState<"closed" | "create" | ProjectPublic>("closed");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await projectsApi.list({
        status: statusFilter || undefined,
        name: search || undefined,
        limit: 20,
      });
      setProjects(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("projects.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, search]);

  useEffect(() => {
    const timeout = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, search]);

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await projectsApi.list({
        status: statusFilter || undefined,
        name: search || undefined,
        limit: 20,
        cursor: nextCursor,
      });
      setProjects((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("projects.genericLoadMoreError")));
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDelete(project: ProjectPublic) {
    if (!window.confirm(t("projects.confirmDelete", { name: project.name }))) return;
    setDeletingId(project.id);
    setError(null);
    try {
      const updated = await projectsApi.remove(project.id);
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (err) {
      setError(errorMessage(err, t("projects.genericDeleteError")));
    } finally {
      setDeletingId(null);
    }
  }

  // Counted off the rows actually returned for the active filters. Nothing
  // here is projected onto the unfiltered total.
  const counts = useMemo(() => {
    const byStatus = {} as Record<ProjectStatus, number>;
    for (const status of PROJECT_STATUSES) byStatus[status] = 0;
    for (const project of projects) byStatus[project.status] += 1;
    return byStatus;
  }, [projects]);

  const filtered = Boolean(statusFilter || search);

  function clearFilters() {
    setStatusFilter("");
    setSearch("");
  }

  const statusOptions: SegmentOption<ProjectStatus | "">[] = [
    { value: "", label: t("projects.allStatuses") },
    ...PROJECT_STATUSES.map((status) => ({ value: status, label: t(PROJECT_STATUS_KEYS[status]) })),
  ];

  // Doubles as the status filter, so the breakdown is a control rather than
  // a caption. Selecting the active row again clears the filter.
  const statusLegend: LegendItem[] = PROJECT_STATUSES.map((status) => ({
    label: t(PROJECT_STATUS_KEYS[status]),
    description: t(STATUS_DESCRIPTION_KEYS[status]),
    color: STATUS_COLOR[status],
    count: loading ? undefined : counts[status],
    active: statusFilter === status,
    onSelect: () => setStatusFilter((current) => (current === status ? "" : status)),
  }));

  return (
    <WorkspacePage module="projects">
      <WorkspaceHero
        accent="blue"
        compact
        badge={t("workspace.projects.badge")}
        icon={<ProjectsIcon />}
        title={t("projects.title")}
        description={t("workspace.projects.description")}
        actions={
          <>
            {canManage ? (
              <Button onClick={() => setPanelMode(panelMode === "create" ? "closed" : "create")}>
                {panelMode === "create" ? t("common.close") : t("projects.newProject")}
              </Button>
            ) : null}
            <ChipRow>
              <ChipLink accent="cyan" href="/documents" icon={<DocumentsIcon />}>
                {t("workspace.projects.next.documentsMeta")}
              </ChipLink>
              <ChipLink accent="green" href="/tasks" icon={<TasksIcon />}>
                {t("workspace.projects.next.tasksMeta")}
              </ChipLink>
              <ChipLink accent="magenta" href="/reports" icon={<ReportsIcon />}>
                {t("workspace.projects.next.reportMeta")}
              </ChipLink>
            </ChipRow>
          </>
        }
        metrics={[
          {
            label: t("workspace.projects.metrics.totalLabel"),
            value: loading ? "—" : projects.length,
            hint: t("workspace.projects.metrics.totalHint"),
            icon: <ProjectsIcon />,
          },
          {
            label: t("workspace.projects.metrics.activeLabel"),
            value: loading ? "—" : counts.active,
            hint: t("workspace.projects.metrics.activeHint"),
            icon: <PulseIcon />,
          },
          {
            label: t("workspace.projects.metrics.attentionLabel"),
            value: loading ? "—" : counts.on_hold,
            hint: t("workspace.projects.metrics.attentionHint"),
            icon: <GaugeIcon />,
          },
          {
            label: t("workspace.projects.metrics.completedLabel"),
            value: loading ? "—" : counts.completed,
            hint: t("workspace.projects.metrics.completedHint"),
            icon: <TargetIcon />,
          },
        ]}
      />

      {panelMode !== "closed" ? (
        <ProjectFormPanel
          project={panelMode === "create" ? undefined : panelMode}
          onCancel={() => setPanelMode("closed")}
          onSaved={(saved) => {
            setProjects((prev) => {
              const exists = prev.some((p) => p.id === saved.id);
              return exists ? prev.map((p) => (p.id === saved.id ? saved : p)) : [saved, ...prev];
            });
            setPanelMode("closed");
          }}
        />
      ) : null}

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <div className={toolbarStyles.toolbar} style={{ marginBottom: 0 }}>
            <div className={toolbarStyles.grow}>
              <Input
                placeholder={t("projects.searchPlaceholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Segmented
              accent="blue"
              ariaLabel={t("projects.allStatuses")}
              options={statusOptions}
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
            />
          </div>

          <WorkspacePanel
            accent="blue"
            icon={<ProjectsIcon />}
            title={t("projects.title")}
            subtitle={loading ? undefined : t("projects.showingCount", { count: projects.length })}
            tight
          >
            {loading ? (
              <LoadingBlock label={t("projects.loadingList")} />
            ) : projects.length === 0 ? (
              filtered ? (
                <ZeroState
                  accent="blue"
                  icon={<ProjectsIcon />}
                  title={t("workspace.projects.emptyFilteredTitle")}
                  text={t("workspace.projects.emptyFilteredText")}
                  actions={
                    <Button size="sm" variant="secondary" onClick={clearFilters}>
                      {t("workspace.projects.clearFilters")}
                    </Button>
                  }
                />
              ) : (
                <ZeroState
                  accent="cyan"
                  icon={<ProjectsIcon />}
                  title={t("workspace.projects.emptyTitle")}
                  text={canManage ? t("workspace.projects.emptyManagerText") : t("workspace.projects.emptyMemberText")}
                  actions={
                    canManage ? (
                      <Button size="sm" onClick={() => setPanelMode("create")}>
                        {t("projects.newProject")}
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
                        <th>{t("projects.columns.name")}</th>
                        <th>{t("projects.columns.code")}</th>
                        <th>{t("projects.columns.status")}</th>
                        <th>{t("projects.columns.updated")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {projects.map((project) => (
                        <tr key={project.id}>
                          <td>
                            <Link href={`/projects/${project.id}`} style={{ fontWeight: 600 }}>
                              {project.name}
                            </Link>
                            {project.description ? (
                              <div className={tableStyles.muted} style={{ fontSize: "var(--font-size-xs)", marginTop: 2 }}>
                                {project.description}
                              </div>
                            ) : null}
                          </td>
                          <td className={tableStyles.muted}>{project.project_code || t("common.emptyValue")}</td>
                          <td>
                            <Badge tone={PROJECT_STATUS_TONE[project.status]}>{t(PROJECT_STATUS_KEYS[project.status])}</Badge>
                          </td>
                          <td className={tableStyles.muted}>{formatDate(locale, project.updated_at)}</td>
                          <td>
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              {canManage ? (
                                <Button size="sm" variant="secondary" onClick={() => setPanelMode(project)}>
                                  {t("common.edit")}
                                </Button>
                              ) : null}
                              {canDelete ? (
                                <Button
                                  size="sm"
                                  variant="danger"
                                  disabled={deletingId === project.id}
                                  onClick={() => handleDelete(project)}
                                >
                                  {deletingId === project.id ? t("common.deleting") : t("common.delete")}
                                </Button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {nextCursor ? (
                  <div className={tableStyles.footer}>
                    <span className={tableStyles.muted}>{t("projects.showingCount", { count: projects.length })}</span>
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
            accent="cyan"
            icon={<GaugeIcon />}
            title={t("workspace.projects.statusTitle")}
            subtitle={t("workspace.projects.statusSubtitle")}
            tight
          >
            <StatusLegend items={statusLegend} total={projects.length} />
          </WorkspacePanel>

          <Disclosure accent="blue" icon={<InsightIcon />} label={t("workspace.projects.workflowTitle")}>
            <StepList
              accent="cyan"
              steps={[
                { title: t("workspace.projects.steps.createTitle"), description: t("workspace.projects.steps.createDescription") },
                { title: t("workspace.projects.steps.attachTitle"), description: t("workspace.projects.steps.attachDescription") },
                { title: t("workspace.projects.steps.deliverTitle"), description: t("workspace.projects.steps.deliverDescription") },
                { title: t("workspace.projects.steps.reportTitle"), description: t("workspace.projects.steps.reportDescription") },
              ]}
            />
          </Disclosure>

          <WorkspaceNote accent="blue" icon={<ShieldIcon />}>
            {t("workspace.projects.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
