"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { documentsApi, projectsApi, tasksApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClassName } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { TaskTable } from "@/components/tasks/TaskTable";
import { ProjectFormPanel } from "@/components/projects/ProjectFormPanel";
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
  ZeroState,
} from "@/components/ui/Workspace";
import {
  CalendarIcon,
  ClockIcon,
  DocumentsIcon,
  MessagesIcon,
  ProjectsIcon,
  ShieldIcon,
  TasksIcon,
  UploadIcon,
} from "@/components/layout/icons";
import { PROJECT_STATUS_KEYS, PROJECT_STATUS_TONE } from "@/components/projects/statusLabels";
import type { DocumentPublic, ProjectPublic, TaskPublic } from "@/lib/types";
import styles from "../Projects.module.css";

/** A task still needing attention -- everything but a finished outcome. */
const OPEN_TASK_STATUSES = new Set(["todo", "in_progress", "blocked"]);

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const { dir, t, locale } = useTranslation();
  const { role } = useAuth();
  const router = useRouter();
  const canCreateTask = role === "owner" || role === "admin" || role === "manager" || role === "member";
  const canManage = role === "owner" || role === "admin" || role === "manager";
  const canDelete = role === "owner" || role === "admin";
  const backArrow = dir === "rtl" ? "→" : "←";

  const [project, setProject] = useState<ProjectPublic | null>(null);
  const [tasks, setTasks] = useState<TaskPublic[]>([]);
  const [documents, setDocuments] = useState<DocumentPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectDetail, taskPage, documentPage] = await Promise.all([
        projectsApi.get(params.id),
        tasksApi.list({ project_id: params.id, limit: 30 }),
        documentsApi.list({ project_id: params.id, limit: 30 }),
      ]);
      setProject(projectDetail);
      setTasks(taskPage.items);
      setNextCursor(taskPage.next_cursor);
      setDocuments(documentPage.items);
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

  // Counted from the pages actually loaded above -- never estimated.
  const openTasks = useMemo(
    () => tasks.filter((task) => OPEN_TASK_STATUSES.has(task.status)).length,
    [tasks]
  );

  async function loadMoreTasks() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await tasksApi.list({ project_id: params.id, limit: 30, cursor: nextCursor });
      setTasks((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("projects.genericLoadMoreError")));
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDelete() {
    if (!project || !window.confirm(t("projects.confirmDelete", { name: project.name }))) return;
    setError(null);
    try {
      await projectsApi.remove(project.id);
      router.push("/projects");
    } catch (err) {
      setError(errorMessage(err, t("projects.genericDeleteError")));
    }
  }

  if (loading) {
    return (
      <WorkspacePage module="projects">
        <Link href="/projects" className={styles.backLink}>
          {backArrow} {t("projects.detail.backToProjects")}
        </Link>
        <WorkspacePanel accent="blue" icon={<ProjectsIcon />} title={t("projects.detail.loading")}>
          <SkeletonRows count={6} />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  if (!project) {
    return (
      <WorkspacePage module="projects">
        <Link href="/projects" className={styles.backLink}>
          {backArrow} {t("projects.detail.backToProjects")}
        </Link>
        <ErrorBanner message={error || t("projects.detail.genericLoadError")} />
      </WorkspacePage>
    );
  }

  return (
    <WorkspacePage module="projects">
      <Link href="/projects" className={styles.backLink}>
        {backArrow} {t("projects.detail.backToProjects")}
      </Link>

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="blue"
        badge={t("workspace.projectDetail.badge")}
        icon={<ProjectsIcon />}
        title={project.name}
        description={project.description || undefined}
        actions={
          <>
            <Badge tone={PROJECT_STATUS_TONE[project.status]}>{t(PROJECT_STATUS_KEYS[project.status])}</Badge>
            {canCreateTask ? (
              <Link href={`/tasks/new?project_id=${project.id}`} className={buttonClassName("primary", "md")}>
                {t("tasks.newTask")}
              </Link>
            ) : null}
            {canManage ? (
              <Button size="md" variant="secondary" onClick={() => setEditing((value) => !value)}>
                {editing ? t("common.cancel") : t("common.edit")}
              </Button>
            ) : null}
            {canDelete ? (
              <Button size="md" variant="danger" onClick={handleDelete}>
                {t("common.delete")}
              </Button>
            ) : null}
          </>
        }
        metrics={[
          {
            label: t("workspace.projectDetail.metrics.tasksLabel"),
            value: tasks.length,
            hint: t("workspace.projectDetail.metrics.tasksHint"),
            icon: <TasksIcon />,
          },
          {
            label: t("workspace.projectDetail.metrics.openLabel"),
            value: openTasks,
            hint: t("workspace.projectDetail.metrics.openHint"),
            icon: <ClockIcon />,
          },
          {
            label: t("workspace.projectDetail.metrics.documentsLabel"),
            value: documents.length,
            hint: t("workspace.projectDetail.metrics.documentsHint"),
            icon: <DocumentsIcon />,
          },
          {
            label: t("workspace.projectDetail.metrics.createdLabel"),
            value: <span style={{ fontSize: 15 }}>{formatDate(locale, project.created_at)}</span>,
            hint: t("workspace.projectDetail.metrics.createdHint"),
            icon: <CalendarIcon />,
          },
        ]}
      />

      {editing ? (
        <ProjectFormPanel
          project={project}
          onCancel={() => setEditing(false)}
          onSaved={(saved) => {
            setProject(saved);
            setEditing(false);
          }}
        />
      ) : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="blue"
            icon={<TasksIcon />}
            title={t("projects.detail.tasksTitle")}
            tight
            action={
              canCreateTask ? (
                <Link href={`/tasks/new?project_id=${project.id}`} className={buttonClassName("ghost", "sm")}>
                  {t("tasks.newTask")}
                </Link>
              ) : undefined
            }
          >
            {tasks.length === 0 ? (
              <ZeroState
                accent="blue"
                icon={<TasksIcon />}
                title={t("projects.detail.noTasksTitle")}
                text={t("projects.detail.noTasksDescription")}
                actions={
                  canCreateTask ? (
                    <Link href={`/tasks/new?project_id=${project.id}`} className={buttonClassName("primary", "sm")}>
                      {t("tasks.newTask")}
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              <>
                <TaskTable tasks={tasks} showProject={false} />
                {nextCursor ? (
                  <div style={{ textAlign: "center", padding: "var(--space-3)" }}>
                    <Button size="sm" variant="secondary" onClick={loadMoreTasks} disabled={loadingMore}>
                      {loadingMore ? t("common.loading") : t("common.loadMore")}
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </WorkspacePanel>

          <WorkspacePanel
            accent="cyan"
            icon={<DocumentsIcon />}
            title={t("projects.detail.documentsTitle")}
            tight
            action={
              canManage ? (
                <Link href="/documents?upload=1" className={buttonClassName("ghost", "sm")}>
                  {t("documents.uploadDocument")}
                </Link>
              ) : undefined
            }
          >
            {documents.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<UploadIcon />}
                title={t("projects.detail.noDocumentsTitle")}
                text={t("projects.detail.noDocumentsDescription")}
                actions={
                  canManage ? (
                    <Link href="/documents?upload=1" className={buttonClassName("primary", "sm")}>
                      {t("documents.uploadDocument")}
                    </Link>
                  ) : undefined
                }
              />
            ) : (
              <InfoList>
                {documents.map((document) => (
                  <InfoRow
                    key={document.id}
                    accent="cyan"
                    icon={<DocumentsIcon />}
                    href={`/documents/${document.id}`}
                    label={document.file_name}
                    meta={formatDate(locale, document.created_at, { month: "short", day: "numeric" })}
                    value={<Badge tone="neutral">{document.status}</Badge>}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel accent="violet" icon={<ProjectsIcon />} title={t("workspace.projectDetail.relatedTitle")} tight>
            <InfoList>
              <InfoRow
                accent="blue"
                icon={<TasksIcon />}
                href={`/tasks?project_id=${project.id}`}
                label={t("workspace.projectDetail.related.tasksTitle")}
                meta={t("workspace.projectDetail.related.tasksDescription")}
              />
              <InfoRow
                accent="cyan"
                icon={<DocumentsIcon />}
                href="/documents"
                label={t("workspace.projectDetail.related.documentsTitle")}
                meta={t("workspace.projectDetail.related.documentsDescription")}
              />
              <InfoRow
                accent="magenta"
                icon={<MessagesIcon />}
                href="/messages/new?type=project_channel"
                label={t("workspace.projectDetail.related.channelTitle")}
                meta={t("workspace.projectDetail.related.channelDescription")}
              />
            </InfoList>
          </WorkspacePanel>

          <WorkspaceNote accent="blue" icon={<ShieldIcon />}>
            {t("workspace.projectDetail.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
