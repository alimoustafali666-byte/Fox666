"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { tasksApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { TaskTable } from "@/components/tasks/TaskTable";
import {
  GaugeIcon,
  PulseIcon,
  ShieldIcon,
  TargetIcon,
  TasksIcon,
} from "@/components/layout/icons";
import {
  Segmented,
  StatusLegend,
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
import {
  TASK_PRIORITIES,
  TASK_STATUSES,
  type TaskDueFilter,
  type TaskPriority,
  type TaskPublic,
  type TaskStatus,
} from "@/lib/types";
import { TASK_PRIORITY_KEYS, TASK_STATUS_KEYS } from "@/components/tasks/taskLabels";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";

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

const PRIORITY_COLOR: Record<TaskPriority, string> = {
  urgent: "#ff5470",
  high: "#ffa43d",
  normal: "#3b82f6",
  low: "#6b7c96",
};

const PRIORITY_DESCRIPTION_KEYS: Record<TaskPriority, TranslationKey> = {
  urgent: "workspace.tasks.priorityDescriptions.urgent",
  high: "workspace.tasks.priorityDescriptions.high",
  normal: "workspace.tasks.priorityDescriptions.normal",
  low: "workspace.tasks.priorityDescriptions.low",
};

/** Highest-signal first, matching how the priority filter is usually read. */
const PRIORITY_ORDER: TaskPriority[] = ["urgent", "high", "normal", "low"];

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

  // Every figure below is counted off the rows already returned for the
  // active filters -- nothing is projected onto the unfiltered total.
  const counts = useMemo(() => {
    const byStatus = {} as Record<TaskStatus, number>;
    for (const status of TASK_STATUSES) byStatus[status] = 0;
    const byPriority = {} as Record<TaskPriority, number>;
    for (const priority of TASK_PRIORITIES) byPriority[priority] = 0;
    for (const task of tasks) {
      byStatus[task.status] += 1;
      byPriority[task.priority] += 1;
    }
    const open = byStatus.todo + byStatus.in_progress + byStatus.blocked;
    return { byStatus, byPriority, open };
  }, [tasks]);

  const filtered = Boolean(statusFilter || priorityFilter || dueFilter || search);

  function clearFilters() {
    setStatusFilter("");
    setPriorityFilter("");
    setDueFilter("");
    setSearch("");
  }

  const dueOptions: SegmentOption<TaskDueFilter | "">[] = [
    { value: "", label: t("tasks.allDueDates") },
    { value: "overdue", label: t("tasks.dueFilters.overdue") },
    { value: "due_today", label: t("tasks.dueFilters.due_today") },
    { value: "upcoming", label: t("tasks.dueFilters.upcoming") },
  ];

  // The breakdown doubles as the filter: selecting a row applies it to the
  // list, selecting it again clears it. The definition stays available on the
  // row's tooltip rather than as a paragraph beside every number.
  const statusLegend: LegendItem[] = TASK_STATUSES.map((status) => ({
    label: t(TASK_STATUS_KEYS[status]),
    description: t(STATUS_DESCRIPTION_KEYS[status]),
    color: STATUS_COLOR[status],
    count: loading ? undefined : counts.byStatus[status],
    active: statusFilter === status,
    onSelect: () => setStatusFilter((current) => (current === status ? "" : status)),
  }));

  const priorityLegend: LegendItem[] = PRIORITY_ORDER.map((priority) => ({
    label: t(TASK_PRIORITY_KEYS[priority]),
    description: t(PRIORITY_DESCRIPTION_KEYS[priority]),
    color: PRIORITY_COLOR[priority],
    count: loading ? undefined : counts.byPriority[priority],
    active: priorityFilter === priority,
    onSelect: () => setPriorityFilter((current) => (current === priority ? "" : priority)),
  }));

  return (
    <WorkspacePage module="tasks">
      <WorkspaceHero
        accent="green"
        compact
        badge={t("workspace.tasks.badge")}
        icon={<TasksIcon />}
        title={t("tasks.myTasksTitle")}
        description={t("workspace.tasks.description")}
        actions={
          <>
            <Link href="/tasks/new" className={buttonClassName("primary", "md")}>
              {t("tasks.newTask")}
            </Link>
            {canSeeTeam ? (
              <Link href="/tasks/team" className={buttonClassName("secondary", "md")}>
                {t("tasks.teamTasksLink")}
              </Link>
            ) : null}
          </>
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
            label: t("workspace.tasks.metrics.progressLabel"),
            value: loading ? "—" : counts.byStatus.in_progress,
            hint: t("workspace.tasks.metrics.progressHint"),
            icon: <PulseIcon />,
          },
          {
            label: t("workspace.tasks.metrics.blockedLabel"),
            value: loading ? "—" : counts.byStatus.blocked,
            hint: t("workspace.tasks.metrics.blockedHint"),
            icon: <GaugeIcon />,
          },
        ]}
      />

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceSplit>
        <WorkspaceColumn>
          <div className={toolbarStyles.toolbar} style={{ marginBottom: 0 }}>
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
            <Segmented
              accent="green"
              ariaLabel={t("tasks.allDueDates")}
              options={dueOptions}
              value={dueFilter}
              onChange={(value) => setDueFilter(value)}
            />
          </div>

          <WorkspacePanel
            accent="green"
            icon={<TasksIcon />}
            title={t("tasks.myTasksTitle")}
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
                  title={t("workspace.tasks.emptyFilteredTitle")}
                  text={t("workspace.tasks.emptyFilteredText")}
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
                  title={t("workspace.tasks.emptyTitle")}
                  text={t("workspace.tasks.emptyText")}
                  actions={
                    <Link href="/tasks/new" className={buttonClassName("primary", "sm")}>
                      {t("tasks.newTask")}
                    </Link>
                  }
                />
              )
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
          </WorkspacePanel>

        </WorkspaceColumn>

        <WorkspaceColumn>
          <WorkspacePanel
            accent="blue"
            icon={<GaugeIcon />}
            title={t("workspace.tasks.statusTitle")}
            subtitle={t("workspace.tasks.statusSubtitle")}
            tight
          >
            <StatusLegend items={statusLegend} total={tasks.length} />
          </WorkspacePanel>

          <WorkspacePanel accent="amber" icon={<TargetIcon />} title={t("workspace.tasks.priorityTitle")} tight>
            <StatusLegend items={priorityLegend} total={tasks.length} />
          </WorkspacePanel>

          <WorkspaceNote accent="green" icon={<ShieldIcon />}>
            {t("workspace.tasks.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
