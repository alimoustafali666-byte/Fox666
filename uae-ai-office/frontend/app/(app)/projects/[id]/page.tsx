"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { projectsApi, tasksApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TaskTable } from "@/components/tasks/TaskTable";
import { PROJECT_STATUS_KEYS, PROJECT_STATUS_TONE } from "@/components/projects/statusLabels";
import type { ProjectPublic, TaskPublic } from "@/lib/types";
import styles from "../Projects.module.css";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { dir, t, locale } = useTranslation();
  const { role } = useAuth();
  const canCreateTask = role === "owner" || role === "admin" || role === "manager" || role === "member";
  const backArrow = dir === "rtl" ? "→" : "←";

  const [project, setProject] = useState<ProjectPublic | null>(null);
  const [tasks, setTasks] = useState<TaskPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectDetail, taskPage] = await Promise.all([
        projectsApi.get(params.id),
        tasksApi.list({ project_id: params.id, limit: 30 }),
      ]);
      setProject(projectDetail);
      setTasks(taskPage.items);
      setNextCursor(taskPage.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("projects.detail.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function loadMoreTasks() {
    if (!nextCursor) return;
    const page = await tasksApi.list({ project_id: params.id, limit: 30, cursor: nextCursor });
    setTasks((prev) => [...prev, ...page.items]);
    setNextCursor(page.next_cursor);
  }

  if (loading) return <LoadingBlock label={t("projects.detail.loading")} />;
  if (!project) return <ErrorBanner message={error || t("projects.detail.genericLoadError")} />;

  return (
    <div>
      <Link href="/projects" className={styles.backLink}>
        {backArrow} {t("projects.detail.backToProjects")}
      </Link>

      <PageHeader
        title={project.name}
        description={project.description || undefined}
        actions={<Badge tone={PROJECT_STATUS_TONE[project.status]}>{t(PROJECT_STATUS_KEYS[project.status])}</Badge>}
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <Card>
        <CardHeader
          title={t("projects.detail.tasksTitle")}
          actions={
            canCreateTask ? (
              <Link href={`/tasks/new?project_id=${project.id}`} className={buttonClassName("primary", "sm")}>
                {t("tasks.newTask")}
              </Link>
            ) : undefined
          }
        />
        <CardBody>
          {tasks.length === 0 ? (
            <EmptyState title={t("projects.detail.noTasksTitle")} description={t("projects.detail.noTasksDescription")} />
          ) : (
            <>
              <TaskTable tasks={tasks} showProject={false} />
              {nextCursor ? (
                <div style={{ textAlign: "center", marginTop: "var(--space-4)" }}>
                  <button type="button" className={buttonClassName("secondary", "sm")} onClick={loadMoreTasks}>
                    {t("common.loadMore")}
                  </button>
                </div>
              ) : null}
            </>
          )}
        </CardBody>
      </Card>

      <div style={{ marginTop: "var(--space-4)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
        {t("projects.detail.createdOn", { date: formatDate(locale, project.created_at) })}
      </div>
    </div>
  );
}

