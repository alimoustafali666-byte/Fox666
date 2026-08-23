"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, auditApi, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock } from "@/components/ui/Spinner";
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

  return (
    <div>
      <Link href="/settings" className={settingsStyles.backLink}>
        {backArrow} {t("settings.auditLog.backToSettings")}
      </Link>

      <PageHeader title={t("settings.auditLog.pageTitle")} description={t("settings.auditLog.pageDescription")} />

      {forbidden ? (
        <Card>
          <EmptyState title={t("settings.auditLog.forbiddenTitle")} description={t("settings.auditLog.forbiddenDescription")} />
        </Card>
      ) : (
        <>
          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

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
          </div>

          <Card>
            {loading ? (
              <LoadingBlock label={t("settings.auditLog.loadingLabel")} />
            ) : entries.length === 0 ? (
              <EmptyState title={t("settings.auditLog.noMatchingTitle")} description={t("settings.auditLog.noMatchingDescription")} />
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
                    <span className={tableStyles.muted}>{t("settings.auditLog.showingCount", { count: entries.length })}</span>
                    <Button size="sm" variant="secondary" onClick={loadMore} loading={loadingMore}>
                      {loadingMore ? t("common.loading") : t("common.loadMore")}
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

