"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { tasksApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TaskTable } from "@/components/tasks/TaskTable";
import { TasksIcon } from "@/components/layout/icons";
import { TASK_PRIORITIES, TASK_STATUSES, type TaskDueFilter, type TaskPriority, type TaskPublic, type TaskStatus } from "@/lib/types";
import { TASK_PRIORITY_KEYS, TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

export default function MyTasksPage() {
  const { user, role } = useAuth();
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const canSeeTeam = role === "owner" || role === "admin" || role === "manager";

  const [tasks, setTasks] = useState<TaskPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<TaskStatus | "">((searchParams.get("status") as TaskStatus | null) || "");
  const [priorityFilter, setPriorityFilter] = useState<TaskPriority | "">((searchParams.get("priority") as TaskPriority | null) || "");
  const [dueFilter, setDueFilter] = useState<TaskDueFilter | "">((searchParams.get("due") as TaskDueFilter | null) || "");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const page = await tasksApi.list({
        assigned_to: user.id,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        due_filter: dueFilter || undefined,
        search: search || undefined,
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
  }, [user?.id, statusFilter, priorityFilter, dueFilter, search]);

  useEffect(() => {
    const timeout = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, priorityFilter, dueFilter, search, user?.id]);

  async function loadMore() {
    if (!nextCursor || !user) return;
    setLoadingMore(true);
    try {
      const page = await tasksApi.list({
        assigned_to: user.id,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        due_filter: dueFilter || undefined,
        search: search || undefined,
        limit: 30,
        cursor: nextCursor,
      });
      setTasks((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("tasks.genericLoadMoreError")));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div>
      <PageHeader
        title={t("tasks.myTasksTitle")}
        description={t("tasks.myTasksDescription")}
        actions={
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            {canSeeTeam ? (
              <Link href="/tasks/team" className={buttonClassName("secondary", "md")}>
                {t("tasks.teamTasksLink")}
              </Link>
            ) : null}
            <Link href="/tasks/new" className={buttonClassName("primary", "md")}>
              {t("tasks.newTask")}
            </Link>
          </div>
        }
      />

      {error ? (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <div className={toolbarStyles.toolbar}>
        <div className={toolbarStyles.grow}>
          <Input placeholder={t("tasks.searchPlaceholder")} value={search} onChange={(e) => setSearch(e.target.value)} />
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
          <EmptyState
            icon={<TasksIcon />}
            title={t("tasks.noTasksTitle")}
            description={t("tasks.noTasksMyDescription")}
            action={
              <Link href="/tasks/new" className={buttonClassName("primary", "sm")}>
                {t("tasks.newTask")}
              </Link>
            }
          />
        ) : (
          <>
            <TaskTable tasks={tasks} showAssignee={false} />
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

