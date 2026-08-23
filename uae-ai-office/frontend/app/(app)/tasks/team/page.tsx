"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { tasksApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TaskTable } from "@/components/tasks/TaskTable";
import { TASK_PRIORITY_KEYS, TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import { TASK_PRIORITIES, TASK_STATUSES, type CompanyMemberPublic, type TaskDueFilter, type TaskPriority, type TaskPublic, type TaskStatus } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

export default function TeamTasksPage() {
  const { role } = useAuth();
  const { t } = useTranslation();
  const canView = role === "owner" || role === "admin" || role === "manager";

  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [tasks, setTasks] = useState<TaskPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "">("");
  const [priorityFilter, setPriorityFilter] = useState<TaskPriority | "">("");
  const [dueFilter, setDueFilter] = useState<TaskDueFilter | "">("");

  useEffect(() => {
    if (!canView) return;
    tenancyApi.listMembers().then(setMembers).catch(() => setMembers([]));
  }, [canView]);

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError(null);
    try {
      const page = await tasksApi.list({
        assigned_to: assigneeFilter || undefined,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        due_filter: dueFilter || undefined,
        limit: 30,
      });
      setTasks(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("tasks.genericLoadError")));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView, assigneeFilter, statusFilter, priorityFilter, dueFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await tasksApi.list({
        assigned_to: assigneeFilter || undefined,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        due_filter: dueFilter || undefined,
        limit: 30,
        cursor: nextCursor,
      });
      setTasks((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  }

  if (!canView) {
    return (
      <div>
        <PageHeader title={t("tasks.teamTasksTitle")} />
        <Card>
          <EmptyState title={t("tasks.teamForbiddenTitle")} description={t("tasks.teamForbiddenDescription")} />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={t("tasks.teamTasksTitle")}
        description={t("tasks.teamTasksDescription")}
        actions={
          <Link href="/tasks/new" className={buttonClassName("primary", "md")}>
            {t("tasks.newTask")}
          </Link>
        }
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className={toolbarStyles.toolbar}>
        <div className={toolbarStyles.field}>
          <Select value={assigneeFilter} onChange={(e) => setAssigneeFilter(e.target.value)}>
            <option value="">{t("tasks.allAssignees")}</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name || m.email}
              </option>
            ))}
          </Select>
        </div>
        <div className={toolbarStyles.field}>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as TaskStatus | "")}>
            <option value="">{t("tasks.allStatuses")}</option>
            {TASK_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(TASK_STATUS_KEYS[s])}
              </option>
            ))}
          </Select>
        </div>
        <div className={toolbarStyles.field}>
          <Select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value as TaskPriority | "")}>
            <option value="">{t("tasks.allPriorities")}</option>
            {TASK_PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {t(TASK_PRIORITY_KEYS[p])}
              </option>
            ))}
          </Select>
        </div>
        <div className={toolbarStyles.field}>
          <Select value={dueFilter} onChange={(e) => setDueFilter(e.target.value as TaskDueFilter | "")}>
            <option value="">{t("tasks.allDueDates")}</option>
            <option value="overdue">{t("tasks.dueFilters.overdue")}</option>
            <option value="due_today">{t("tasks.dueFilters.due_today")}</option>
            <option value="upcoming">{t("tasks.dueFilters.upcoming")}</option>
          </Select>
        </div>
      </div>

      <Card>
        {loading ? (
          <LoadingBlock label={t("tasks.loadingList")} />
        ) : tasks.length === 0 ? (
          <EmptyState title={t("tasks.noTasksTitle")} description={t("tasks.noTasksTeamDescription")} />
        ) : (
          <>
            <TaskTable tasks={tasks} />
            {nextCursor ? (
              <div className={tableStyles.footer}>
                <span className={tableStyles.muted}>{t("tasks.showingCount", { count: tasks.length })}</span>
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

