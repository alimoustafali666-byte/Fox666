"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { collaborationApi, documentsApi, tasksApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate, formatDateTime, type TranslationKey } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { FieldWrapper, Input, Select, Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import {
  TASK_PRIORITY_KEYS,
  TASK_PRIORITY_TONE,
  TASK_SOURCE_KEYS,
  TASK_STATUS_KEYS,
  TASK_STATUS_TONE,
} from "@/components/tasks/taskLabels";
import {
  TASK_PRIORITIES,
  TASK_STATUSES,
  type CompanyMemberPublic,
  type TaskActivityPublic,
  type TaskCommentPublic,
  type TaskPriority,
  type TaskPublic,
  type TaskStatus,
} from "@/lib/types";
import styles from "./TaskDetail.module.css";

const ACTIVITY_LABEL_KEY: Record<string, TranslationKey> = {
  created: "tasks.activity.created",
  assigned: "tasks.activity.assigned",
  reassigned: "tasks.activity.reassigned",
  status_changed: "tasks.activity.status_changed",
  priority_changed: "tasks.activity.priority_changed",
  due_date_changed: "tasks.activity.due_date_changed",
  completed: "tasks.activity.completed",
  reopened: "tasks.activity.reopened",
  commented: "tasks.activity.commented",
};

export default function TaskDetailPage() {
  const params = useParams<{ taskId: string }>();
  const { user, role } = useAuth();
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";

  const [task, setTask] = useState<TaskPublic | null>(null);
  const [comments, setComments] = useState<TaskCommentPublic[]>([]);
  const [activity, setActivity] = useState<TaskActivityPublic[]>([]);
  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [sourceHref, setSourceHref] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [editingFields, setEditingFields] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftPriority, setDraftPriority] = useState<TaskPriority>("normal");
  const [draftAssignee, setDraftAssignee] = useState("");
  const [draftDueDate, setDraftDueDate] = useState("");

  const [commentBody, setCommentBody] = useState("");
  const [commentBusy, setCommentBusy] = useState(false);

  const canManage = role === "owner" || role === "admin" || role === "manager";
  const isCreator = !!task && !!user && task.created_by === user.id;
  const isAssignee = !!task && !!user && task.assigned_to === user.id;
  const canEditAllFields = canManage || isCreator;
  const canChangeStatus = canEditAllFields || isAssignee;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [taskDetail, commentList, activityList] = await Promise.all([
        tasksApi.get(params.taskId),
        tasksApi.listComments(params.taskId),
        tasksApi.listActivity(params.taskId),
      ]);
      setTask(taskDetail);
      setComments(commentList);
      setActivity(activityList);
      setDraftTitle(taskDetail.title);
      setDraftDescription(taskDetail.description || "");
      setDraftPriority(taskDetail.priority);
      setDraftAssignee(taskDetail.assigned_to || "");
      setDraftDueDate(taskDetail.due_date || "");

      if (taskDetail.source_type === "document" && taskDetail.source_id) {
        setSourceHref(`/documents/${taskDetail.source_id}`);
      } else if (taskDetail.source_type === "conversation" && taskDetail.source_id) {
        setSourceHref(`/messages/${taskDetail.source_id}`);
      } else if ((taskDetail.source_type === "message" || taskDetail.source_type === "ai_suggestion") && taskDetail.source_id) {
        collaborationApi
          .getMessageLocation(taskDetail.source_id)
          .then((loc) => setSourceHref(`/messages/${loc.conversation_id}#message-${taskDetail.source_id}`))
          .catch(() => setSourceHref(null));
      } else {
        setSourceHref(null);
      }
    } catch (err) {
      setError(errorMessage(err, t("tasks.detail.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.taskId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    tenancyApi.listMembers().then(setMembers).catch(() => setMembers([]));
  }, []);

  async function handleStatusChange(status: TaskStatus) {
    if (!task) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await tasksApi.update(task.id, { status });
      setTask(updated);
      const activityList = await tasksApi.listActivity(task.id);
      setActivity(activityList);
    } catch (err) {
      setError(errorMessage(err, t("tasks.detail.genericUpdateError")));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveFields(event: FormEvent) {
    event.preventDefault();
    if (!task) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await tasksApi.update(task.id, {
        title: draftTitle.trim(),
        description: draftDescription.trim() || null,
        priority: draftPriority,
        assigned_to: draftAssignee || null,
        due_date: draftDueDate || null,
      });
      setTask(updated);
      setEditingFields(false);
      const activityList = await tasksApi.listActivity(task.id);
      setActivity(activityList);
    } catch (err) {
      setError(errorMessage(err, t("tasks.detail.genericUpdateError")));
    } finally {
      setSaving(false);
    }
  }

  async function handleAddComment(event: FormEvent) {
    event.preventDefault();
    if (!task || !commentBody.trim()) return;
    setCommentBusy(true);
    setError(null);
    try {
      const comment = await tasksApi.addComment(task.id, commentBody.trim());
      setComments((prev) => [...prev, comment]);
      setCommentBody("");
      const activityList = await tasksApi.listActivity(task.id);
      setActivity(activityList);
    } catch (err) {
      setError(errorMessage(err, t("tasks.detail.genericCommentError")));
    } finally {
      setCommentBusy(false);
    }
  }

  if (loading) return <LoadingBlock label={t("tasks.detail.loading")} />;
  if (!task) return <ErrorBanner message={error || t("tasks.detail.genericLoadError")} />;

  return (
    <div>
      <Link href="/tasks" className={styles.backLink}>
        {backArrow} {t("tasks.detail.backToTasks")}
      </Link>

      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>{task.title}</h1>
          <div className={styles.badgeRow}>
            <Badge tone={TASK_STATUS_TONE[task.status]}>{t(TASK_STATUS_KEYS[task.status])}</Badge>
            <Badge tone={TASK_PRIORITY_TONE[task.priority]}>{t(TASK_PRIORITY_KEYS[task.priority])}</Badge>
          </div>
        </div>
        {canEditAllFields && !editingFields ? (
          <Button size="sm" variant="secondary" onClick={() => setEditingFields(true)}>
            {t("common.edit")}
          </Button>
        ) : null}
      </div>

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className={styles.layout}>
        <div className={styles.main}>
          <Card>
            <CardHeader title={t("tasks.detail.descriptionTitle")} />
            <CardBody>
              {editingFields ? (
                <form onSubmit={handleSaveFields}>
                  <FieldWrapper label={t("tasks.newTaskForm.titleLabel")} htmlFor="edit-title">
                    <Input id="edit-title" value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} maxLength={300} required />
                  </FieldWrapper>
                  <FieldWrapper label={t("tasks.newTaskForm.descriptionLabel")} htmlFor="edit-description" optional>
                    <Textarea id="edit-description" value={draftDescription} onChange={(e) => setDraftDescription(e.target.value)} rows={4} maxLength={8000} />
                  </FieldWrapper>
                  <FieldWrapper label={t("tasks.newTaskForm.priorityLabel")} htmlFor="edit-priority">
                    <Select id="edit-priority" value={draftPriority} onChange={(e) => setDraftPriority(e.target.value as TaskPriority)}>
                      {TASK_PRIORITIES.map((p) => (
                        <option key={p} value={p}>
                          {t(TASK_PRIORITY_KEYS[p])}
                        </option>
                      ))}
                    </Select>
                  </FieldWrapper>
                  <FieldWrapper label={t("tasks.newTaskForm.assigneeLabel")} htmlFor="edit-assignee" optional>
                    <Select id="edit-assignee" value={draftAssignee} onChange={(e) => setDraftAssignee(e.target.value)}>
                      <option value="">{t("tasks.unassigned")}</option>
                      {members.map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.full_name || m.email}
                        </option>
                      ))}
                    </Select>
                  </FieldWrapper>
                  <FieldWrapper label={t("tasks.newTaskForm.dueDateLabel")} htmlFor="edit-due-date" optional>
                    <Input id="edit-due-date" type="date" value={draftDueDate} onChange={(e) => setDraftDueDate(e.target.value)} />
                  </FieldWrapper>
                  <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
                    <Button type="submit" loading={saving}>
                      {t("tasks.detail.saveButton")}
                    </Button>
                    <Button type="button" variant="secondary" onClick={() => setEditingFields(false)}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                </form>
              ) : (
                <p className={styles.description}>{task.description || t("tasks.detail.noDescription")}</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title={t("tasks.detail.commentsTitle")} />
            <CardBody>
              {comments.length === 0 ? (
                <p className={styles.muted}>{t("tasks.detail.noComments")}</p>
              ) : (
                <div className={styles.commentList}>
                  {comments.map((c) => (
                    <div key={c.id} className={styles.comment}>
                      <div className={styles.commentMeta}>
                        <strong>{c.author_name || ""}</strong>
                        <span className={styles.muted}>{formatDateTime(locale, c.created_at)}</span>
                      </div>
                      <div className={styles.commentBody}>{c.body}</div>
                    </div>
                  ))}
                </div>
              )}
              <form onSubmit={handleAddComment} className={styles.commentForm}>
                <Textarea
                  placeholder={t("tasks.detail.commentPlaceholder")}
                  value={commentBody}
                  onChange={(e) => setCommentBody(e.target.value)}
                  rows={2}
                  maxLength={4000}
                />
                <Button type="submit" size="sm" loading={commentBusy} disabled={!commentBody.trim()}>
                  {t("tasks.detail.addComment")}
                </Button>
              </form>
            </CardBody>
          </Card>
        </div>

        <div className={styles.sidebar}>
          <Card>
            <CardHeader title={t("tasks.detail.detailsTitle")} />
            <CardBody>
              <dl className={styles.metaList}>
                <dt>{t("tasks.columns.status")}</dt>
                <dd>
                  {canChangeStatus ? (
                    <Select value={task.status} disabled={saving} onChange={(e) => handleStatusChange(e.target.value as TaskStatus)}>
                      {TASK_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {t(TASK_STATUS_KEYS[s])}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Badge tone={TASK_STATUS_TONE[task.status]}>{t(TASK_STATUS_KEYS[task.status])}</Badge>
                  )}
                </dd>

                <dt>{t("tasks.columns.assignee")}</dt>
                <dd>{task.assignee_name || t("tasks.unassigned")}</dd>

                <dt>{t("tasks.columns.project")}</dt>
                <dd>{task.project_name || t("common.noProject")}</dd>

                <dt>{t("tasks.columns.dueDate")}</dt>
                <dd>{task.due_date ? formatDate(locale, task.due_date, { month: "short", day: "numeric", year: "numeric" }) : t("common.emptyValue")}</dd>

                <dt>{t("tasks.detail.createdBy")}</dt>
                <dd>{task.creator_name || ""}</dd>

                <dt>{t("tasks.detail.source")}</dt>
                <dd>
                  {task.source_type === "manual" ? (
                    t(TASK_SOURCE_KEYS.manual)
                  ) : sourceHref ? (
                    <Link href={sourceHref}>{t(TASK_SOURCE_KEYS[task.source_type])}</Link>
                  ) : (
                    t(TASK_SOURCE_KEYS[task.source_type])
                  )}
                </dd>

                <dt>{t("tasks.detail.created")}</dt>
                <dd>{formatDateTime(locale, task.created_at)}</dd>

                {task.completed_at ? (
                  <>
                    <dt>{t("tasks.detail.completedAt")}</dt>
                    <dd>{formatDateTime(locale, task.completed_at)}</dd>
                  </>
                ) : null}
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title={t("tasks.detail.activityTitle")} />
            <CardBody>
              {activity.length === 0 ? (
                <p className={styles.muted}>{t("tasks.detail.noActivity")}</p>
              ) : (
                <div className={styles.activityList}>
                  {activity.map((a) => (
                    <div key={a.id} className={styles.activityItem}>
                      <div className={styles.activityLine}>
                        <strong>{a.actor_name || t("tasks.detail.systemActor")}</strong>{" "}
                        {t(ACTIVITY_LABEL_KEY[a.event_type] || "tasks.activity.status_changed")}
                      </div>
                      <div className={styles.muted}>{formatDateTime(locale, a.created_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

