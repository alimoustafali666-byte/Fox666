"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiError, auditApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  Disclosure,
  PointList,
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
  AuditIcon,
  DocumentsIcon,
  ReportsIcon,
  ShieldIcon,
  TasksIcon,
  TeamIcon,
} from "@/components/layout/icons";
import type { AuditLogEntry, CompanyMemberPublic } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import toolbarStyles from "@/components/ui/Toolbar.module.css";
import settingsStyles from "../Settings.module.css";
import styles from "./AuditLog.module.css";

export default function AuditLogPage() {
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("");

  const filtered = actionFilter.trim() !== "" || resourceTypeFilter.trim() !== "";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    try {
      const page = await auditApi.list({
        action: actionFilter || undefined,
        resource_type: resourceTypeFilter || undefined,
        limit: 25,
      });
      setEntries(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setForbidden(true);
      } else {
        setError(errorMessage(err, t("settings.auditLog.genericLoadError")));
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionFilter, resourceTypeFilter]);

  useEffect(() => {
    const timeout = setTimeout(load, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionFilter, resourceTypeFilter]);

  useEffect(() => {
    tenancyApi
      .listMembers()
      .then(setMembers)
      .catch(() => setMembers([]));
  }, []);

  // Counted from the entries actually returned for the current filters --
  // these describe the page in view, never the whole log.
  const distinctActions = useMemo(() => new Set(entries.map((e) => e.action)).size, [entries]);
  const distinctActors = useMemo(
    () => new Set(entries.map((e) => e.actor_user_id ?? "system")).size,
    [entries]
  );

  async function loadMore() {
    if (!nextCursor) return;
    setLoadingMore(true);
    try {
      const page = await auditApi.list({
        action: actionFilter || undefined,
        resource_type: resourceTypeFilter || undefined,
        limit: 25,
        cursor: nextCursor,
      });
      setEntries((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("settings.auditLog.genericLoadMoreError")));
    } finally {
      setLoadingMore(false);
    }
  }

  function actorLabel(actorUserId: string | null): string {
    if (!actorUserId) return t("settings.auditLog.systemActor");
    const member = members.find((m) => m.user_id === actorUserId);
    return member?.full_name || member?.email || actorUserId;
  }

  if (forbidden) {
    return (
      <WorkspacePage module="settings">
        <Link href="/settings" className={settingsStyles.backLink}>
          {backArrow} {t("settings.auditLog.backToSettings")}
        </Link>
        <WorkspaceHero
          accent="violet"
          badge={t("workspace.audit.badge")}
          icon={<AuditIcon />}
          title={t("settings.auditLog.pageTitle")}
          description={t("workspace.audit.description")}
        />
        <WorkspacePanel accent="amber" icon={<ShieldIcon />} title={t("settings.auditLog.forbiddenTitle")}>
          <ZeroState
            accent="amber"
            icon={<ShieldIcon />}
            title={t("settings.auditLog.forbiddenTitle")}
            text={t("settings.auditLog.forbiddenDescription")}
            actions={
              <Link href="/settings" className={buttonClassName("secondary", "sm")}>
                {t("settings.auditLog.backToSettings")}
              </Link>
            }
          />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  return (
    <WorkspacePage module="settings">
      <Link href="/settings" className={settingsStyles.backLink}>
        {backArrow} {t("settings.auditLog.backToSettings")}
      </Link>

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="amber"
        badge={t("workspace.audit.badge")}
        icon={<AuditIcon />}
        title={t("settings.auditLog.pageTitle")}
        description={t("workspace.audit.description")}
        metrics={[
          {
            label: t("workspace.audit.metrics.entriesLabel"),
            value: loading ? "—" : entries.length,
            hint: t("workspace.audit.metrics.entriesHint"),
            icon: <AuditIcon />,
          },
          {
            label: t("workspace.audit.metrics.actionsLabel"),
            value: loading ? "—" : distinctActions,
            hint: t("workspace.audit.metrics.actionsHint"),
            icon: <TasksIcon />,
          },
          {
            label: t("workspace.audit.metrics.actorsLabel"),
            value: loading ? "—" : distinctActors,
            hint: t("workspace.audit.metrics.actorsHint"),
            icon: <TeamIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="amber" icon={<AuditIcon />} title={t("settings.auditLog.pageTitle")} tight>
            <div className={toolbarStyles.toolbar}>
              <div className={toolbarStyles.field} style={{ width: 220 }}>
                <Input
                  placeholder={t("settings.auditLog.filterByAction")}
                  value={actionFilter}
                  onChange={(e) => setActionFilter(e.target.value)}
                />
              </div>
              <div className={toolbarStyles.field} style={{ width: 220 }}>
                <Input
                  placeholder={t("settings.auditLog.filterByResourceType")}
                  value={resourceTypeFilter}
                  onChange={(e) => setResourceTypeFilter(e.target.value)}
                />
              </div>
              {filtered ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setActionFilter("");
                    setResourceTypeFilter("");
                  }}
                >
                  {t("workspace.audit.clearFilters")}
                </Button>
              ) : null}
            </div>

            {loading ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={6} />
              </div>
            ) : entries.length === 0 ? (
              <ZeroState
                accent="amber"
                icon={<AuditIcon />}
                title={filtered ? t("workspace.audit.emptyFilteredTitle") : t("workspace.audit.emptyTitle")}
                text={filtered ? t("workspace.audit.emptyFilteredText") : t("workspace.audit.emptyText")}
                actions={
                  filtered ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setActionFilter("");
                        setResourceTypeFilter("");
                      }}
                    >
                      {t("workspace.audit.clearFilters")}
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <>
                <div className={tableStyles.wrap}>
                  <table className={tableStyles.table}>
                    <thead>
                      <tr>
                        <th>{t("settings.auditLog.columns.time")}</th>
                        <th>{t("settings.auditLog.columns.actor")}</th>
                        <th>{t("settings.auditLog.columns.action")}</th>
                        <th>{t("settings.auditLog.columns.resource")}</th>
                        <th>{t("settings.auditLog.columns.ipAddress")}</th>
                        <th>{t("settings.auditLog.columns.metadata")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((entry) => (
                        <tr key={entry.id}>
                          <td className={tableStyles.muted}>{formatDateTime(locale, entry.created_at)}</td>
                          <td>{actorLabel(entry.actor_user_id)}</td>
                          <td>{entry.action}</td>
                          <td className={tableStyles.muted}>{entry.resource_type}</td>
                          <td className={tableStyles.muted} dir="ltr" style={{ textAlign: "start" }}>
                            {entry.ip_address ?? t("common.emptyValue")}
                          </td>
                          <td>
                            <span
                              className={styles.metadata}
                              dir="ltr"
                              title={JSON.stringify(entry.metadata ?? {})}
                            >
                              {entry.metadata ? JSON.stringify(entry.metadata) : t("common.emptyValue")}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {nextCursor ? (
                  <div className={tableStyles.footer}>
                    <span className={tableStyles.muted}>
                      {t("settings.auditLog.showingCount", { count: entries.length })}
                    </span>
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
          <Disclosure accent="violet" icon={<ShieldIcon />} label={t("workspace.audit.coversTitle")}>
            <PointList
              accent="violet"
              items={[
                { icon: <TeamIcon />, title: t("workspace.audit.covers.accessTitle"), text: t("workspace.audit.covers.accessDescription") },
                { icon: <DocumentsIcon />, title: t("workspace.audit.covers.contentTitle"), text: t("workspace.audit.covers.contentDescription") },
                { icon: <TasksIcon />, title: t("workspace.audit.covers.deliveryTitle"), text: t("workspace.audit.covers.deliveryDescription") },
                { icon: <ReportsIcon />, title: t("workspace.audit.covers.exportTitle"), text: t("workspace.audit.covers.exportDescription") },
              ]}
            />
          </Disclosure>

          <WorkspacePanel accent="green" icon={<ReportsIcon />} title={t("nav.reports")} tight>
            <div style={{ padding: "var(--space-3)" }}>
              <Link href="/reports" className={buttonClassName("secondary", "sm", true)}>
                {t("nav.reports")}
              </Link>
            </div>
          </WorkspacePanel>

          <WorkspaceNote accent="amber" icon={<ShieldIcon />}>
            {t("workspace.audit.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
