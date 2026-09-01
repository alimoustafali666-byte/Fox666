"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingBlock } from "@/components/ui/Spinner";
import { ROLE_LABEL_KEYS, ROLE_TONE, ROLES } from "@/components/layout/roles";
import type { CompanyMemberPublic, InvitationPublic, Role } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import styles from "../Settings.module.css";

export default function TeamPage() {
  const { user, role: actorRole } = useAuth();
  const { t, dir, locale } = useTranslation();
  const backArrow = dir === "rtl" ? "→" : "←";
  const canManage = actorRole === "owner" || actorRole === "admin";

  const [members, setMembers] = useState<CompanyMemberPublic[]>([]);
  const [invitations, setInvitations] = useState<InvitationPublic[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("member");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([tenancyApi.listMembers(), tenancyApi.listInvitations()])
      .then(([memberData, invitationData]) => {
        setMembers(memberData);
        setInvitations(invitationData);
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

  async function handleInvite(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusyUserId("invite");
    try {
      await tenancyApi.createInvitation({ email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      setInvitations(await tenancyApi.listInvitations());
    } catch (err) {
      setError(errorMessage(err, t("settings.team.genericInviteError")));
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleResend(invitation: InvitationPublic) {
    setError(null);
    setBusyUserId(invitation.id);
    try {
      await tenancyApi.resendInvitation(invitation.id);
      setInvitations(await tenancyApi.listInvitations());
    } catch (err) {
      setError(errorMessage(err, t("settings.team.genericInvitationActionError")));
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleCancel(invitation: InvitationPublic) {
    if (!window.confirm(t("settings.team.confirmCancel"))) return;
    setError(null);
    setBusyUserId(invitation.id);
    try {
      await tenancyApi.cancelInvitation(invitation.id);
      setInvitations(await tenancyApi.listInvitations());
    } catch (err) {
      setError(errorMessage(err, t("settings.team.genericInvitationActionError")));
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
            ) : members.length === 0 ? (
              <EmptyState title={t("settings.team.noMembersTitle")} description={t("settings.team.noMembersDescription")} />
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
          <Card>
            <CardBody>
              <h2>{t("settings.team.inviteTitle")}</h2>
              <form onSubmit={handleInvite} style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
                <FieldWrapper label={t("settings.team.inviteEmail")} htmlFor="invite-email">
                  <Input id="invite-email" type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
                </FieldWrapper>
                <FieldWrapper label={t("settings.team.inviteRole")} htmlFor="invite-role">
                  <Select id="invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as Role)}>
                    {ROLES.filter((r) => r !== "owner").map((r) => <option key={r} value={r}>{t(ROLE_LABEL_KEYS[r])}</option>)}
                  </Select>
                </FieldWrapper>
                <Button type="submit" disabled={busyUserId === "invite"}>{t("settings.team.inviteButton")}</Button>
              </form>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <h2>{t("settings.team.invitationsTitle")}</h2>
              {invitations.length === 0 ? <EmptyState title={t("settings.team.noInvitations")} /> : (
                <div className={tableStyles.wrap}>
                  <table className={tableStyles.table}><thead><tr><th>{t("settings.team.inviteEmail")}</th><th>{t("settings.team.inviteRole")}</th><th>{t("settings.team.invitationStatus")}</th><th>{t("settings.team.invitationExpires")}</th><th /></tr></thead>
                    <tbody>{invitations.map((invitation) => <tr key={invitation.id}><td>{invitation.email}</td><td><Badge tone={ROLE_TONE[invitation.role]}>{t(ROLE_LABEL_KEYS[invitation.role])}</Badge></td><td>{t(`settings.team.${invitation.status}` as never)}</td><td className={tableStyles.muted}>{formatDate(locale, invitation.expires_at)}</td><td>{invitation.status === "pending" ? <><Button size="sm" disabled={busyUserId === invitation.id} onClick={() => handleResend(invitation)}>{t("settings.team.resendButton")}</Button> <Button size="sm" variant="danger" disabled={busyUserId === invitation.id} onClick={() => handleCancel(invitation)}>{t("settings.team.cancelButton")}</Button></> : null}</td></tr>)}</tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

