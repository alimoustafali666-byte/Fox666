"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { tasksApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TaskTable } from "@/components/tasks/TaskTable";
import { TASK_PRIORITY_KEYS, TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import { GaugeIcon, PulseIcon, ShieldIcon, TargetIcon, TasksIcon, TeamIcon } from "@/components/layout/icons";
import {
  InfoList,
  InfoRow,
  StatusLegend,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
  ZeroState,
  type LegendItem,
} from "@/components/ui/Workspace";
import type { TranslationKey } from "@/lib/i18n";
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

  // Counted off the rows already loaded for the active filters -- this is a
  // view of what is on screen, never a projection of the whole company.
  const counts = useMemo(() => {
    const byStatus = {} as Record<TaskStatus, number>;
    for (const status of TASK_STATUSES) byStatus[status] = 0;
    const byAssignee = new Map<string, number>();
    for (const task of tasks) {
      byStatus[task.status] += 1;
      const key = task.assigned_to ?? "";
      byAssignee.set(key, (byAssignee.get(key) ?? 0) + 1);
    }
    const open = byStatus.todo + byStatus.in_progress + byStatus.blocked;
    return { byStatus, byAssignee, open };
  }, [tasks]);

  const workload = useMemo(() => {
    const nameOf = (id: string) => {
      if (!id) return t("workspace.teamTasks.unassignedLabel");
      const member = members.find((m) => m.user_id === id);
      return member ? member.full_name || member.email : id;
    };
    return [...counts.byAssignee.entries()]
      .map(([id, count]) => ({ id, name: nameOf(id), count }))
      .sort((a, b) => b.count - a.count);
  }, [counts.byAssignee, members, t]);

  const filtered = Boolean(assigneeFilter || statusFilter || priorityFilter || dueFilter);

  function clearFilters() {
    setAssigneeFilter("");
    setStatusFilter("");
    setPriorityFilter("");
    setDueFilter("");
  }

  // Doubles as the status filter, so the breakdown is a control rather than
  // a caption. Selecting the active row again clears the filter.
  const statusLegend: LegendItem[] = TASK_STATUSES.map((status) => ({
    label: t(TASK_STATUS_KEYS[status]),
    description: t(STATUS_DESCRIPTION_KEYS[status]),
    color: STATUS_COLOR[status],
    count: loading ? undefined : counts.byStatus[status],
    active: statusFilter === status,
    onSelect: () => setStatusFilter((current) => (current === status ? "" : status)),
  }));

  if (!canView) {
    return (
      <WorkspacePage module="tasks">
        <WorkspaceHero
          accent="green"
          badge={t("workspace.tasks.badge")}
          icon={<TeamIcon />}
          title={t("tasks.teamTasksTitle")}
        />
        <WorkspacePanel accent="amber" icon={<ShieldIcon />} title={t("tasks.teamForbiddenTitle")} tight>
          <ZeroState
            accent="amber"
            icon={<ShieldIcon />}
            title={t("tasks.teamForbiddenTitle")}
            text={t("tasks.teamForbiddenDescription")}
            actions={
              <Link href="/tasks" className={buttonClassName("primary", "sm")}>
                {t("tasks.myTasksTitle")}
              </Link>
            }
          />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  return (
    <WorkspacePage module="tasks">
      <WorkspaceHero
        accent="blue"
        badge={t("workspace.tasks.badge")}
        icon={<TeamIcon />}
        title={t("tasks.teamTasksTitle")}
        description={t("tasks.teamTasksDescription")}
        actions={
          <Link href="/tasks/new" className={buttonClassName("primary", "md")}>
            {t("tasks.newTask")}
          </Link>
        }
        metrics={[
          {
            label: t("workspace.tasks.metrics.loadedLabel"),
            value: loading ? "—" : tasks.length,
            hint: t("workspace.tasks.metrics.loadedHint"),
            icon: <TasksIcon />,
          },
          {
            label: t("workspace.tasks.metrics.openLabel"),
            value: loading ? "—" : counts.open,
            hint: t("workspace.tasks.metrics.openHint"),
            icon: <TargetIcon />,
          },
          {
            label: t("workspace.tasks.metrics.blockedLabel"),
            value: loading ? "—" : counts.byStatus.blocked,
            hint: t("workspace.tasks.metrics.blockedHint"),
            icon: <GaugeIcon />,
          },
          {
            label: t("workspace.messages.metrics.teamLabel"),
            value: members.length || "—",
            hint: t("workspace.messages.metrics.teamHint"),
            icon: <TeamIcon />,
          },
        ]}
      />

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <div className={toolbarStyles.toolbar} style={{ marginBottom: 0 }}>
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

      <WorkspacePanel
        accent="blue"
        icon={<TasksIcon />}
        title={t("tasks.teamTasksTitle")}
        subtitle={loading ? undefined : t("tasks.showingCount", { count: tasks.length })}
        tight
      >
        {loading ? (
          <LoadingBlock label={t("tasks.loadingList")} />
        ) : tasks.length === 0 ? (
          filtered ? (
            <ZeroState
              accent="blue"
              icon={<TasksIcon />}
              title={t("workspace.teamTasks.emptyFilteredTitle")}
              text={t("workspace.teamTasks.emptyFilteredText")}
              actions={
                <Button size="sm" variant="secondary" onClick={clearFilters}>
                  {t("workspace.tasks.clearFilters")}
                </Button>
              }
            />
          ) : (
            <ZeroState
              accent="green"
              icon={<TasksIcon />}
              title={t("workspace.teamTasks.emptyTitle")}
              text={t("workspace.teamTasks.emptyText")}
              actions={
                <Link href="/tasks/new" className={buttonClassName("primary", "sm")}>
                  {t("tasks.newTask")}
                </Link>
              }
            />
          )
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
      </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="violet"
            icon={<TeamIcon />}
            title={t("workspace.teamTasks.workloadTitle")}
            subtitle={t("workspace.teamTasks.workloadSubtitle")}
            tight
          >
            {loading ? (
              <LoadingBlock label={t("tasks.loadingList")} />
            ) : workload.length === 0 ? (
              <ZeroState accent="violet" icon={<TeamIcon />} title={t("workspace.teamTasks.emptyTitle")} />
            ) : (
              <InfoList>
                {workload.map((entry) => (
                  <InfoRow
                    key={entry.id || "unassigned"}
                    accent="violet"
                    icon={<TeamIcon />}
                    label={entry.name}
                    value={entry.count}
                    onClick={entry.id ? () => setAssigneeFilter(entry.id) : undefined}
                  />
                ))}
              </InfoList>
            )}
          </WorkspacePanel>

          <WorkspacePanel
            accent="green"
            icon={<PulseIcon />}
            title={t("workspace.tasks.statusTitle")}
            subtitle={t("workspace.tasks.statusSubtitle")}
            tight
          >
            <StatusLegend items={statusLegend} total={tasks.length} />
          </WorkspacePanel>

          <WorkspaceNote accent="blue" icon={<ShieldIcon />}>
            {t("workspace.teamTasks.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}

const STATUS_COLOR: Record<TaskStatus, string> = {
  todo: "#8b6bff",
  in_progress: "#3b82f6",
  blocked: "#ffa43d",
  completed: "#2fd48a",
  cancelled: "#6b7c96",
};

const STATUS_DESCRIPTION_KEYS: Record<TaskStatus, TranslationKey> = {
  todo: "workspace.tasks.statusDescriptions.todo",
  in_progress: "workspace.tasks.statusDescriptions.in_progress",
  blocked: "workspace.tasks.statusDescriptions.blocked",
  completed: "workspace.tasks.statusDescriptions.completed",
  cancelled: "workspace.tasks.statusDescriptions.cancelled",
};

