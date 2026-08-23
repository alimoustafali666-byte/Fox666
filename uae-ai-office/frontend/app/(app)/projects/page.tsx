"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { projectsApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ProjectFormPanel } from "@/components/projects/ProjectFormPanel";
import { ProjectsIcon } from "@/components/layout/icons";
import { PROJECT_STATUS_KEYS, PROJECT_STATUS_TONE } from "@/components/projects/statusLabels";
import { PROJECT_STATUSES, type ProjectPublic } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

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
  const [statusFilter, setStatusFilter] = useState("");
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

  return (
    <div>
      <PageHeader
        title={t("projects.title")}
        description={t("projects.description")}
        actions={
          canManage ? (
            <Button onClick={() => setPanelMode(panelMode === "create" ? "closed" : "create")}>
              {panelMode === "create" ? t("common.close") : t("projects.newProject")}
            </Button>
          ) : null
        }
      />

      {panelMode !== "closed" ? (
        <div style={{ marginBottom: "var(--space-6)" }}>
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
        </div>
      ) : null}

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className={toolbarStyles.toolbar}>
        <div className={toolbarStyles.grow}>
          <Input placeholder={t("projects.searchPlaceholder")} value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className={toolbarStyles.field}>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">{t("projects.allStatuses")}</option>
            {PROJECT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(PROJECT_STATUS_KEYS[s])}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        {loading ? (
          <LoadingBlock label={t("projects.loadingList")} />
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<ProjectsIcon />}
            title={t("projects.noProjectsTitle")}
            description={canManage ? t("projects.noProjectsManager") : t("projects.noProjectsMember")}
            action={
              canManage ? (
                <Button size="sm" onClick={() => setPanelMode("create")}>
                  {t("projects.newProject")}
                </Button>
              ) : undefined
            }
          />
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
      </Card>
    </div>
  );
}

