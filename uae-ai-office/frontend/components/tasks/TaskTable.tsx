"use client";

import Link from "next/link";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import { TASK_PRIORITY_KEYS, TASK_PRIORITY_TONE, TASK_STATUS_KEYS, TASK_STATUS_TONE } from "./taskLabels";
import type { TaskPublic } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import styles from "./TaskTable.module.css";

const OPEN_STATUSES = new Set(["todo", "in_progress", "blocked"]);

function isOverdue(task: TaskPublic, today: string): boolean {
  return !!task.due_date && task.due_date < today && OPEN_STATUSES.has(task.status);
}

export function TaskTable({
  tasks,
  showAssignee = true,
  showProject = true,
}: {
  tasks: TaskPublic[];
  showAssignee?: boolean;
  showProject?: boolean;
}) {
  const { t, locale } = useTranslation();
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className={tableStyles.wrap}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>{t("tasks.columns.title")}</th>
            <th>{t("tasks.columns.status")}</th>
            <th>{t("tasks.columns.priority")}</th>
            {showAssignee ? <th>{t("tasks.columns.assignee")}</th> : null}
            {showProject ? <th>{t("tasks.columns.project")}</th> : null}
            <th>{t("tasks.columns.dueDate")}</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>
                <Link href={`/tasks/${task.id}`} className={styles.titleLink}>
                  {task.title}
                </Link>
              </td>
              <td>
                <Badge tone={TASK_STATUS_TONE[task.status]}>{t(TASK_STATUS_KEYS[task.status])}</Badge>
              </td>
              <td>
                <Badge tone={TASK_PRIORITY_TONE[task.priority]}>{t(TASK_PRIORITY_KEYS[task.priority])}</Badge>
              </td>
              {showAssignee ? (
                <td className={tableStyles.muted}>{task.assignee_name || t("tasks.unassigned")}</td>
              ) : null}
              {showProject ? <td className={tableStyles.muted}>{task.project_name || t("common.noProject")}</td> : null}
              <td className={isOverdue(task, today) ? styles.overdueDate : tableStyles.muted}>
                {task.due_date ? formatDate(locale, task.due_date, { month: "short", day: "numeric" }) : t("common.emptyValue")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

