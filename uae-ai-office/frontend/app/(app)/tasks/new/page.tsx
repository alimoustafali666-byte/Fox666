"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { projectsApi, tasksApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TASK_PRIORITY_KEYS, TASK_SOURCE_KEYS } from "@/components/tasks/taskLabels";
import { TASK_PRIORITIES, type CompanyMemberPublic, type ProjectPublic, type TaskPriority, type TaskSourceType } from "@/lib/types";

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
  const [priority, setPriority] = useState<TaskPriority>((searchParams.get("priority") as TaskPriority | null) || "normal");
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

  if (loading) return <LoadingBlock label={t("common.loading")} />;

  return (
    <div style={{ padding: "var(--space-6)", maxWidth: 560, margin: "0 auto" }}>
      <Card>
        <CardHeader
          title={t("tasks.newTaskForm.title")}
          subtitle={sourceType !== "manual" ? t(TASK_SOURCE_KEYS[sourceType]) : undefined}
        />
        <CardBody>
          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <form onSubmit={handleSubmit}>
            <FieldWrapper label={t("tasks.newTaskForm.titleLabel")} htmlFor="task-title">
              <Input id="task-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} required />
            </FieldWrapper>

            <FieldWrapper label={t("tasks.newTaskForm.descriptionLabel")} htmlFor="task-description" optional>
              <Textarea id="task-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={8000} />
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
              <Select id="task-priority" value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)}>
                {TASK_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {t(TASK_PRIORITY_KEYS[p])}
                  </option>
                ))}
              </Select>
            </FieldWrapper>

            <FieldWrapper label={t("tasks.newTaskForm.dueDateLabel")} htmlFor="task-due-date" optional>
              <Input id="task-due-date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </FieldWrapper>

            <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-5)" }}>
              <Button type="submit" loading={submitting} disabled={!title.trim()}>
                {submitting ? t("tasks.newTaskForm.creating") : t("tasks.newTaskForm.createButton")}
              </Button>
              <Button type="button" variant="secondary" onClick={() => router.back()}>
                {t("tasks.newTaskForm.cancelButton")}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}

