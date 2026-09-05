"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { projectsApi, tasksApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  Disclosure,
  InfoList,
  InfoRow,
  PointList,
  SkeletonRows,
  StatusLegend,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  type LegendItem,
} from "@/components/ui/Workspace";
import {
  BriefIcon,
  ClockIcon,
  GaugeIcon,
  ProjectsIcon,
  ShieldIcon,
  TargetIcon,
  TasksIcon,
  TeamIcon,
} from "@/components/layout/icons";
import { TASK_PRIORITY_KEYS, TASK_SOURCE_KEYS } from "@/components/tasks/taskLabels";
import {
  TASK_PRIORITIES,
  type CompanyMemberPublic,
  type ProjectPublic,
  type TaskPriority,
  type TaskSourceType,
} from "@/lib/types";

/** Priority colours, shared with the task board so the same level reads the
 *  same colour everywhere. */
const PRIORITY_COLOR: Record<TaskPriority, string> = {
  low: "#6d7e9d",
  normal: "#4d8dff",
  high: "#ffa43d",
  urgent: "#ff5470",
};

export default function NewTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, role } = useAuth();
  const { t } = useTranslation();
  const canAssignOthers = role === "owner" || role === "admin" || role === "manager";

  const sourceType = (searchParams.get("source_type") as TaskSourceType | null) || "manual";
  const sourceId = searchParams.get("source_id");

  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState(searchParams.get("title") || "");
  const [description, setDescription] = useState(searchParams.get("description") || "");
  const [projectId, setProjectId] = useState(searchParams.get("project_id") || "");
  const [assignedTo, setAssignedTo] = useState(searchParams.get("assigned_to") || "");
  const [priority, setPriority] = useState<TaskPriority>(
    (searchParams.get("priority") as TaskPriority | null) || "normal"
  );
  const [dueDate, setDueDate] = useState(searchParams.get("due_date") || "");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [memberList, projectPage] = await Promise.all([
          tenancyApi.listMembers(),
          projectsApi.list({ limit: 100 }),
        ]);
        setMembers(memberList);
        setProjects(projectPage.items);
      } catch {
        setError(t("tasks.newTaskForm.genericError"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  // The legend explains the four levels and marks the one currently chosen.
  // It carries no counts -- nothing has been created yet.
  const priorityLegend: LegendItem[] = TASK_PRIORITIES.map((p) => ({
    label: t(TASK_PRIORITY_KEYS[p]),
    description: t(`workspace.tasks.priorityDescriptions.${p}` as never),
    color: PRIORITY_COLOR[p],
  }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const task = await tasksApi.create({
        title: title.trim(),
        description: description.trim() || undefined,
        project_id: projectId || undefined,
        assigned_to: assignedTo || undefined,
        priority,
        due_date: dueDate || undefined,
        source_type: sourceType,
        source_id: sourceId || undefined,
      });
      router.push(`/tasks/${task.id}`);
    } catch (err) {
      setError(errorMessage(err, t("tasks.newTaskForm.genericError")));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <WorkspacePage module="tasks">
      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="green"
        badge={t("workspace.newTask.badge")}
        icon={<TasksIcon />}
        title={t("tasks.newTaskForm.title")}
        description={t("workspace.newTask.description")}
        actions={
          <>
            <Link href="/tasks" className={buttonClassName("secondary", "md")}>
              {t("nav.tasks")}
            </Link>
            {sourceType !== "manual" ? (
              <span className={buttonClassName("ghost", "md")} style={{ pointerEvents: "none" }}>
                {t(TASK_SOURCE_KEYS[sourceType])}
              </span>
            ) : null}
          </>
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="blue" icon={<TasksIcon />} title={t("tasks.newTaskForm.title")}>
            {loading ? (
              <SkeletonRows count={6} />
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <FieldWrapper label={t("tasks.newTaskForm.titleLabel")} htmlFor="task-title">
                  <Input
                    id="task-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={300}
                    required
                  />
                </FieldWrapper>

                <FieldWrapper label={t("tasks.newTaskForm.descriptionLabel")} htmlFor="task-description" optional>
                  <Textarea
                    id="task-description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={5}
                    maxLength={8000}
                  />
                </FieldWrapper>

                <FieldWrapper label={t("tasks.newTaskForm.projectLabel")} htmlFor="task-project" optional>
                  <Select id="task-project" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                    <option value="">{t("common.noProject")}</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </FieldWrapper>

                <FieldWrapper label={t("tasks.newTaskForm.assigneeLabel")} htmlFor="task-assignee" optional>
                  <Select id="task-assignee" value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)}>
                    <option value="">{t("tasks.unassigned")}</option>
                    {user ? <option value={user.id}>{t("tasks.newTaskForm.assignToMe")}</option> : null}
                    {canAssignOthers
                      ? members
                          .filter((m) => m.user_id !== user?.id)
                          .map((m) => (
                            <option key={m.user_id} value={m.user_id}>
                              {m.full_name || m.email}
                            </option>
                          ))
                      : null}
                  </Select>
                </FieldWrapper>

                <FieldWrapper label={t("tasks.newTaskForm.priorityLabel")} htmlFor="task-priority">
                  <Select
                    id="task-priority"
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as TaskPriority)}
                  >
                    {TASK_PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {t(TASK_PRIORITY_KEYS[p])}
                      </option>
                    ))}
                  </Select>
                </FieldWrapper>

                <FieldWrapper label={t("tasks.newTaskForm.dueDateLabel")} htmlFor="task-due-date" optional>
                  <Input
                    id="task-due-date"
                    type="date"
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                  />
                </FieldWrapper>

                <div style={{ display: "flex", gap: "var(--space-3)" }}>
                  <Button type="submit" loading={submitting} disabled={!title.trim()}>
                    {submitting ? t("tasks.newTaskForm.creating") : t("tasks.newTaskForm.createButton")}
                  </Button>
                  <Button type="button" variant="secondary" onClick={() => router.back()}>
                    {t("tasks.newTaskForm.cancelButton")}
                  </Button>
                </div>
              </form>
            )}
          </WorkspacePanel>

          <Disclosure accent="cyan" icon={<TargetIcon />} label={t("workspace.newTask.tipsTitle")}>
            <PointList
              accent="cyan"
              items={[
                { icon: <TargetIcon />, title: t("workspace.newTask.tips.titleTitle"), text: t("workspace.newTask.tips.titleDescription") },
                { icon: <TeamIcon />, title: t("workspace.newTask.tips.assigneeTitle"), text: t("workspace.newTask.tips.assigneeDescription") },
                { icon: <GaugeIcon />, title: t("workspace.newTask.tips.priorityTitle"), text: t("workspace.newTask.tips.priorityDescription") },
                { icon: <ClockIcon />, title: t("workspace.newTask.tips.dueTitle"), text: t("workspace.newTask.tips.dueDescription") },
              ]}
            />
          </Disclosure>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="amber"
            icon={<GaugeIcon />}
            title={t("workspace.newTask.priorityTitle")}
            subtitle={t("workspace.newTask.prioritySubtitle")}
            tight
          >
            <StatusLegend items={priorityLegend} />
          </WorkspacePanel>

          <WorkspacePanel accent="violet" icon={<TasksIcon />} title={t("workspace.newTask.linkedTitle")} tight>
            <InfoList>
              <InfoRow
                accent="blue"
                icon={<TasksIcon />}
                href="/tasks"
                label={t("workspace.newTask.linked.boardTitle")}
                meta={t("workspace.newTask.linked.boardDescription")}
              />
              <InfoRow
                accent="cyan"
                icon={<ProjectsIcon />}
                href="/projects"
                label={t("workspace.newTask.linked.projectTitle")}
                meta={t("workspace.newTask.linked.projectDescription")}
              />
              <InfoRow
                accent="magenta"
                icon={<BriefIcon />}
                href="/brief"
                label={t("workspace.newTask.linked.briefTitle")}
                meta={t("workspace.newTask.linked.briefDescription")}
              />
            </InfoList>
          </WorkspacePanel>

          <WorkspaceNote accent="blue" icon={<ShieldIcon />}>
            {t("workspace.newTask.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
