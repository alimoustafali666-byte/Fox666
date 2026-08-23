"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ROLE_LABEL_KEYS, ROLE_TONE, ROLES } from "@/components/layout/roles";
import type { CompanyMemberPublic, Role } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import styles from "../Settings.module.css";

export default function TeamPage() {
  const { user, role: actorRole } = useAuth();
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";
  const canManage = actorRole === "owner" || actorRole === "admin";

  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    tenancyApi
      .listMembers()
      .then((data) => {
        setMembers(data);
        setForbidden(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setForbidden(true);
        } else {
          setError(errorMessage(err, t("settings.team.genericLoadError")));
        }
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ownerCount = members.filter((m) => m.role === "owner").length;

  function canEditMember(member: CompanyMemberPublic): boolean {
    if (!canManage) return false;
    if (member.role === "owner" && actorRole !== "owner") return false;
    return true;
  }

  function canRemoveMember(member: CompanyMemberPublic): boolean {
    if (!canEditMember(member)) return false;
    if (member.user_id === user?.id) return false;
    if (member.role === "owner" && ownerCount <= 1) return false;
    return true;
  }

  async function handleRoleChange(member: CompanyMemberPublic, newRole: Role) {
    setError(null);
    setBusyUserId(member.user_id);
    try {
      const updated = await tenancyApi.updateMemberRole(member.user_id, newRole);
      setMembers((prev) => prev.map((m) => (m.user_id === updated.user_id ? updated : m)));
    } catch (err) {
      setError(errorMessage(err, t("settings.team.genericRoleChangeError")));
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleRemove(member: CompanyMemberPublic) {
    if (!window.confirm(t("settings.team.confirmRemove", { name: member.full_name || member.email }))) return;
    setError(null);
    setBusyUserId(member.user_id);
    try {
      await tenancyApi.removeMember(member.user_id);
      setMembers((prev) => prev.filter((m) => m.user_id !== member.user_id));
    } catch (err) {
      setError(errorMessage(err, t("settings.team.genericRemoveError")));
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <div>
      <Link href="/settings" className={styles.backLink}>
        {backArrow} {t("settings.team.backToSettings")}
      </Link>

      <PageHeader title={t("settings.team.pageTitle")} description={t("settings.team.pageDescription")} />

      {forbidden ? (
        <Card>
          <EmptyState title={t("settings.team.forbiddenTitle")} description={t("settings.team.forbiddenDescription")} />
        </Card>
      ) : (
        <>
          {error ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <Card>
            {loading ? (
              <LoadingBlock label={t("settings.team.loadingLabel")} />
            ) : (
              <div className={tableStyles.wrap}>
                <table className={tableStyles.table}>
                  <thead>
                    <tr>
                      <th>{t("settings.team.columns.name")}</th>
                      <th>{t("settings.team.columns.email")}</th>
                      <th>{t("settings.team.columns.role")}</th>
                      <th>{t("settings.team.columns.memberSince")}</th>
                      {canManage ? <th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((member) => (
                      <tr key={member.user_id}>
                        <td>{member.full_name || t("common.emptyValue")}</td>
                        <td className={tableStyles.muted}>{member.email}</td>
                        <td>
                          {canEditMember(member) ? (
                            <Select
                              value={member.role}
                              disabled={busyUserId === member.user_id}
                              onChange={(e) => handleRoleChange(member, e.target.value as Role)}
                              style={{ width: "auto", display: "inline-block" }}
                            >
                              {ROLES.filter((r) => r !== "owner" || actorRole === "owner").map((r) => (
                                <option key={r} value={r}>
                                  {t(ROLE_LABEL_KEYS[r])}
                                </option>
                              ))}
                            </Select>
                          ) : (
                            <Badge tone={ROLE_TONE[member.role]}>{t(ROLE_LABEL_KEYS[member.role])}</Badge>
                          )}
                        </td>
                        <td className={tableStyles.muted}>{formatDate(locale, member.created_at)}</td>
                        {canManage ? (
                          <td>
                            {canRemoveMember(member) ? (
                              <Button
                                size="sm"
                                variant="danger"
                                disabled={busyUserId === member.user_id}
                                onClick={() => handleRemove(member)}
                              >
                                {t("settings.team.removeButton")}
                              </Button>
                            ) : null}
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

