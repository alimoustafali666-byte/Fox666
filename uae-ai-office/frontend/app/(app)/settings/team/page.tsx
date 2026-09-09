"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError, tenancyApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation, formatDate } from "@/lib/i18n";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClassName } from "@/components/ui/Button";
import { FieldWrapper, Input, Select } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  SkeletonRows,
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
import { AuditIcon, SettingsIcon, ShieldIcon, TeamIcon } from "@/components/layout/icons";
import { ROLE_LABEL_KEYS, ROLE_TONE, ROLES } from "@/components/layout/roles";
import type { CompanyMemberPublic, InvitationCreateResponse, InvitationPublic, Role } from "@/lib/types";
import tableStyles from "@/components/ui/Table.module.css";
import styles from "../Settings.module.css";

/** Colour per role, matched to the accent palette so the legend, the badges
 *  and the rest of the workspace read as one system. */
const ROLE_COLOR: Record<Role, string> = {
  owner: "#e05ad0",
  admin: "#8b6bff",
  manager: "#4d8dff",
  member: "#35d9f2",
};

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
  // The most recent invite/resend result. Held in state because the
  // one-time token only ever exists in that response -- listInvitations()
  // deliberately never returns it -- so this panel is the operator's
  // single chance to copy the link. That matters most while email
  // delivery is unconfigured, when the link is the ONLY way the invite
  // reaches anyone.
  const [inviteResult, setInviteResult] = useState<InvitationCreateResponse | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);

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

  // Every number below is a count of what actually loaded -- nothing is
  // estimated, and an unloaded panel shows an em dash rather than a zero.
  const pendingCount = useMemo(
    () => invitations.filter((invitation) => invitation.status === "pending").length,
    [invitations]
  );
  const adminCount = useMemo(
    () => members.filter((m) => m.role === "owner" || m.role === "admin").length,
    [members]
  );

  const roleLegend: LegendItem[] = ROLES.map((r) => ({
    label: t(ROLE_LABEL_KEYS[r]),
    description: t(`workspace.team.roleDescriptions.${r}` as never),
    color: ROLE_COLOR[r],
    count: loading ? undefined : members.filter((m) => m.role === r).length,
  }));

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

  async function copyInviteLink(url: string) {
    // navigator.clipboard is unavailable on insecure origins and in some
    // embedded browsers, so the manual-selection fallback below is not
    // optional -- without it the link would be unreachable in exactly the
    // deployments most likely to be running before email is configured.
    try {
      await navigator.clipboard.writeText(url);
      setLinkCopied(true);
    } catch {
      setLinkCopied(false);
    }
  }

  async function handleInvite(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusyUserId("invite");
    try {
      const created = await tenancyApi.createInvitation({ email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      setInviteResult(created);
      setLinkCopied(false);
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
      const resent = await tenancyApi.resendInvitation(invitation.id);
      setInviteResult(resent);
      setLinkCopied(false);
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

  if (forbidden) {
    return (
      <WorkspacePage module="settings">
        <Link href="/settings" className={styles.backLink}>
          {backArrow} {t("settings.team.backToSettings")}
        </Link>
        <WorkspaceHero
          accent="violet"
          badge={t("workspace.team.badge")}
          icon={<TeamIcon />}
          title={t("settings.team.pageTitle")}
          description={t("workspace.team.description")}
        />
        <WorkspacePanel accent="amber" icon={<ShieldIcon />} title={t("settings.team.forbiddenTitle")}>
          <ZeroState
            accent="amber"
            icon={<ShieldIcon />}
            title={t("settings.team.forbiddenTitle")}
            text={t("settings.team.forbiddenDescription")}
            actions={
              <Link href="/settings" className={buttonClassName("secondary", "sm")}>
                {t("settings.team.backToSettings")}
              </Link>
            }
          />
        </WorkspacePanel>
      </WorkspacePage>
    );
  }

  return (
    <WorkspacePage module="settings">
      <Link href="/settings" className={styles.backLink}>
        {backArrow} {t("settings.team.backToSettings")}
      </Link>

      {error ? <ErrorBanner message={error} /> : null}

      <WorkspaceHero
        accent="violet"
        badge={t("workspace.team.badge")}
        icon={<TeamIcon />}
        title={t("settings.team.pageTitle")}
        description={t("workspace.team.description")}
        metrics={[
          {
            label: t("workspace.team.metrics.membersLabel"),
            value: loading ? "—" : members.length,
            hint: t("workspace.team.metrics.membersHint"),
            icon: <TeamIcon />,
          },
          {
            label: t("workspace.team.metrics.pendingLabel"),
            value: loading ? "—" : pendingCount,
            hint: t("workspace.team.metrics.pendingHint"),
            icon: <SettingsIcon />,
          },
          {
            label: t("workspace.team.metrics.ownersLabel"),
            value: loading ? "—" : adminCount,
            hint: t("workspace.team.metrics.ownersHint"),
            icon: <ShieldIcon />,
          },
        ]}
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel accent="violet" icon={<TeamIcon />} title={t("settings.team.pageTitle")} tight>
            {loading ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={4} />
              </div>
            ) : members.length === 0 ? (
              <ZeroState
                accent="violet"
                icon={<TeamIcon />}
                title={t("workspace.team.membersEmptyTitle")}
                text={t("workspace.team.membersEmptyText")}
              />
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
          </WorkspacePanel>

          <WorkspacePanel accent="cyan" icon={<SettingsIcon />} title={t("settings.team.invitationsTitle")} tight>
            {loading ? (
              <div style={{ padding: "var(--space-3)" }}>
                <SkeletonRows count={3} />
              </div>
            ) : invitations.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<SettingsIcon />}
                title={t("workspace.team.invitationsEmptyTitle")}
                text={t("workspace.team.invitationsEmptyText")}
              />
            ) : (
              <div className={tableStyles.wrap}>
                <table className={tableStyles.table}>
                  <thead>
                    <tr>
                      <th>{t("settings.team.inviteEmail")}</th>
                      <th>{t("settings.team.inviteRole")}</th>
                      <th>{t("settings.team.invitationStatus")}</th>
                      <th>{t("settings.team.invitationExpires")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {invitations.map((invitation) => (
                      <tr key={invitation.id}>
                        <td>{invitation.email}</td>
                        <td>
                          <Badge tone={ROLE_TONE[invitation.role]}>{t(ROLE_LABEL_KEYS[invitation.role])}</Badge>
                        </td>
                        <td>{t(`settings.team.${invitation.status}` as never)}</td>
                        <td className={tableStyles.muted}>{formatDate(locale, invitation.expires_at)}</td>
                        <td>
                          {invitation.status === "pending" ? (
                            <span style={{ display: "inline-flex", gap: "var(--space-2)" }}>
                              <Button
                                size="sm"
                                disabled={busyUserId === invitation.id}
                                onClick={() => handleResend(invitation)}
                              >
                                {t("settings.team.resendButton")}
                              </Button>
                              <Button
                                size="sm"
                                variant="danger"
                                disabled={busyUserId === invitation.id}
                                onClick={() => handleCancel(invitation)}
                              >
                                {t("settings.team.cancelButton")}
                              </Button>
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </WorkspacePanel>
        </WorkspaceColumn>

        <WorkspaceColumn>
          {canManage ? (
            <WorkspacePanel accent="blue" icon={<TeamIcon />} title={t("settings.team.inviteTitle")}>
              <form onSubmit={handleInvite} style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <FieldWrapper label={t("settings.team.inviteEmail")} htmlFor="invite-email">
                  <Input
                    id="invite-email"
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                  />
                </FieldWrapper>
                <FieldWrapper label={t("settings.team.inviteRole")} htmlFor="invite-role">
                  <Select id="invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as Role)}>
                    {ROLES.filter((r) => r !== "owner").map((r) => (
                      <option key={r} value={r}>
                        {t(ROLE_LABEL_KEYS[r])}
                      </option>
                    ))}
                  </Select>
                </FieldWrapper>
                <Button type="submit" disabled={busyUserId === "invite"} block>
                  {t("settings.team.inviteButton")}
                </Button>
              </form>
            </WorkspacePanel>
          ) : null}


          {inviteResult ? (
            <WorkspacePanel
              accent={inviteResult.email_delivery.status === "sent" ? "green" : "amber"}
              icon={<TeamIcon />}
              title={t("settings.team.inviteLinkTitle")}
              subtitle={t("settings.team.inviteLinkFor", { email: inviteResult.email })}
            >
              <p className={styles.helperText} style={{ marginTop: 0 }}>
                {inviteResult.email_delivery.status === "sent"
                  ? t("settings.team.inviteDeliverySent", { email: inviteResult.email })
                  : inviteResult.email_delivery.status === "not_configured"
                    ? t("settings.team.inviteDeliveryNotConfigured", { email: inviteResult.email })
                    : t("settings.team.inviteDeliveryFailed", { email: inviteResult.email })}
              </p>
              <FieldWrapper label={t("settings.team.inviteLinkTitle")} htmlFor="invite-link">
                <Input
                  id="invite-link"
                  readOnly
                  value={inviteResult.invite_url}
                  dir="ltr"
                  onFocus={(event) => event.currentTarget.select()}
                />
              </FieldWrapper>
              <p className={styles.helperText}>
                {t("settings.team.inviteLinkHelp", {
                  expires: formatDate(locale, inviteResult.expires_at),
                  role: t(ROLE_LABEL_KEYS[inviteResult.role]),
                })}
              </p>
              {linkCopied ? <p className={styles.statusText}>{t("settings.team.inviteLinkCopied")}</p> : null}
              <div className={styles.actionRow}>
                <Button size="sm" onClick={() => copyInviteLink(inviteResult.invite_url)}>
                  {t("settings.team.inviteLinkCopy")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setInviteResult(null)}>
                  {t("settings.team.inviteLinkDismiss")}
                </Button>
              </div>
            </WorkspacePanel>
          ) : null}

          <WorkspacePanel
            accent="magenta"
            icon={<ShieldIcon />}
            title={t("workspace.team.rolesTitle")}
            subtitle={t("workspace.team.rolesSubtitle")}
            tight
          >
            <StatusLegend items={roleLegend} total={members.length} />
          </WorkspacePanel>

          {canManage ? (
            <WorkspacePanel accent="amber" icon={<AuditIcon />} title={t("settings.auditLog.pageTitle")} tight>
              <div style={{ padding: "var(--space-3)" }}>
                <Link href="/settings/audit-log" className={buttonClassName("secondary", "sm", true)}>
                  {t("settings.auditLog.pageTitle")}
                </Link>
              </div>
            </WorkspacePanel>
          ) : null}

          <WorkspaceNote accent="violet" icon={<ShieldIcon />}>
            {t("workspace.team.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
