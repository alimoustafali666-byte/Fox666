"use client";

import { useEffect, useState } from "react";
import { useAuth, errorMessage } from "@/lib/auth-context";
import { tenancyApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { CompanyBrandingCard } from "@/components/settings/CompanyBrandingCard";
import {
  AuditIcon,
  BriefIcon,
  InsightIcon,
  SettingsIcon,
  ShieldIcon,
  TeamIcon,
} from "@/components/layout/icons";
import {
  Disclosure,
  InfoList,
  InfoRow,
  MetaGrid,
  MetaItem,
  PointList,
  WorkspaceColumn,
  WorkspaceHero,
  WorkspaceNote,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceSplit,
} from "@/components/ui/Workspace";
import { ROLE_LABEL_KEYS } from "@/components/layout/roles";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import styles from "./Settings.module.css";

export default function SettingsPage() {
  const { company, role, user, updateProfile, changePassword } = useAuth();
  const { t } = useTranslation();
  const canViewAuditLog = role === "owner" || role === "admin";
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [scheduleTimezone, setScheduleTimezone] = useState("");
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileBusy, setProfileBusy] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordBusy, setPasswordBusy] = useState(false);

  useEffect(() => {
    setFullName(user?.full_name ?? "");
  }, [user?.full_name]);

  useEffect(() => {
    if (!canViewAuditLog) return;
    tenancyApi.getDailyBriefSchedule().then((schedule) => {
      setScheduleEnabled(schedule.enabled);
      setScheduleTime(schedule.time.slice(0, 5));
      setScheduleTimezone(schedule.timezone);
    }).catch((err) => setScheduleError(errorMessage(err, t("settings.dailyBriefSchedule.loadError"))));
  }, [canViewAuditLog, t]);

  async function saveSchedule() {
    setSavingSchedule(true);
    try {
      setScheduleError(null);
      const schedule = await tenancyApi.updateDailyBriefSchedule({ enabled: scheduleEnabled, time: scheduleTime });
      setScheduleTimezone(schedule.timezone);
    } catch (err) {
      setScheduleError(errorMessage(err, t("settings.dailyBriefSchedule.saveError")));
    } finally {
      setSavingSchedule(false);
    }
  }

  async function saveProfile() {
    setProfileBusy(true); setProfileMessage(null);
    try { await updateProfile(fullName); setProfileMessage(t("settings.profile.saved")); }
    catch (err) { setProfileMessage(errorMessage(err, t("settings.profile.error"))); }
    finally { setProfileBusy(false); }
  }

  async function savePassword() {
    setPasswordBusy(true); setPasswordMessage(null);
    try { await changePassword(currentPassword, newPassword); setCurrentPassword(""); setNewPassword(""); setPasswordMessage(t("settings.profile.passwordSaved")); }
    catch (err) { setPasswordMessage(errorMessage(err, t("settings.profile.passwordError"))); }
    finally { setPasswordBusy(false); }
  }

  return (
    <WorkspacePage module="settings">
      <WorkspaceHero
        accent="blue"
        compact
        badge={t("workspace.settings.badge")}
        icon={<SettingsIcon />}
        title={t("settings.title")}
        description={t("workspace.settings.description")}
        side={
          <MetaGrid>
            <MetaItem label={t("workspace.settings.companyLabel")}>{company?.name ?? t("common.emptyValue")}</MetaItem>
            <MetaItem label={t("workspace.settings.roleLabel")}>{role ? t(ROLE_LABEL_KEYS[role]) : t("common.emptyValue")}</MetaItem>
          </MetaGrid>
        }
      />

      <WorkspaceSplit>
        <WorkspaceColumn>
          <WorkspacePanel
            accent="blue"
            icon={<TeamIcon />}
            title={t("settings.profile.title")}
            subtitle={t("workspace.settings.profileSubtitle")}
          >
            <FieldWrapper label={t("settings.profile.name")} htmlFor="profile-name">
              <Input id="profile-name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
            </FieldWrapper>
            <div className={styles.metaLabel}>{t("workspace.settings.emailLabel")}</div>
            <div className={styles.metaValue}>{user?.email}</div>
            <p className={styles.helperText}>{t("workspace.settings.emailNote")}</p>
            {profileMessage ? <p className={styles.statusText}>{profileMessage}</p> : null}
            <div className={styles.actionRow}>
              <Button onClick={saveProfile} loading={profileBusy}>{t("settings.profile.save")}</Button>
            </div>

            <div className={styles.subSection}>
              <div className={styles.subTitle}>{t("settings.profile.password")}</div>
              <p className={styles.helperText}>{t("workspace.settings.passwordSubtitle")}</p>
              <div className={styles.fieldPair}>
                <FieldWrapper label={t("settings.profile.currentPassword")} htmlFor="current-password">
                  <Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
                </FieldWrapper>
                <FieldWrapper label={t("settings.profile.newPassword")} htmlFor="new-password">
                  <Input id="new-password" type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
                </FieldWrapper>
              </div>
              {passwordMessage ? <p className={styles.statusText}>{passwordMessage}</p> : null}
              <div className={styles.actionRow}>
                <Button
                  variant="secondary"
                  onClick={savePassword}
                  loading={passwordBusy}
                  disabled={!currentPassword || newPassword.length < 12}
                >
                  {t("settings.profile.changePassword")}
                </Button>
              </div>
            </div>
          </WorkspacePanel>

          {company ? <CompanyBrandingCard /> : null}
        </WorkspaceColumn>

        <WorkspaceColumn>
          {canViewAuditLog ? (
            <WorkspacePanel
              accent="violet"
              icon={<BriefIcon />}
              title={t("settings.dailyBriefSchedule.title")}
              subtitle={t("workspace.settings.groups.automationSubtitle")}
            >
              <p className={styles.helperText} style={{ marginTop: 0 }}>{t("settings.dailyBriefSchedule.description")}</p>
              {scheduleError ? <ErrorBanner message={scheduleError} /> : null}
              <label className={styles.toggleRow}>
                <input
                  type="checkbox"
                  className={styles.checkbox}
                  checked={scheduleEnabled}
                  onChange={(event) => setScheduleEnabled(event.target.checked)}
                />
                {t("settings.dailyBriefSchedule.enabled")}
              </label>
              <FieldWrapper label={t("settings.dailyBriefSchedule.time")} htmlFor="daily-brief-time">
                <Input id="daily-brief-time" type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} disabled={!scheduleEnabled} />
              </FieldWrapper>
              <p className={styles.helperText}>{t("settings.dailyBriefSchedule.timezone", { timezone: scheduleTimezone || company?.timezone || "" })}</p>
              <div className={styles.actionRow}>
                <Button variant="secondary" onClick={saveSchedule} loading={savingSchedule}>{t("settings.dailyBriefSchedule.save")}</Button>
              </div>
            </WorkspacePanel>
          ) : null}

          <WorkspacePanel
            accent="cyan"
            icon={<ShieldIcon />}
            title={t("workspace.settings.groups.accessTitle")}
            subtitle={t("workspace.settings.groups.accessSubtitle")}
            tight
          >
            <InfoList>
              <InfoRow
                accent="violet"
                icon={<TeamIcon />}
                href="/settings/team"
                label={t("settings.team.linkTitle")}
                meta={t("settings.team.linkDescription")}
              />
              {canViewAuditLog ? (
                <InfoRow
                  accent="cyan"
                  icon={<AuditIcon />}
                  href="/settings/audit-log"
                  label={t("settings.auditLog.linkTitle")}
                  meta={t("settings.auditLog.linkDescription")}
                />
              ) : null}
            </InfoList>
            {!canViewAuditLog ? (
              <div style={{ padding: "var(--space-2) var(--space-4) var(--space-4)" }}>
                <p className={styles.helperText} style={{ marginTop: 0 }}>{t("workspace.settings.restricted")}</p>
              </div>
            ) : null}
          </WorkspacePanel>

          <Disclosure accent="blue" icon={<InsightIcon />} label={t("workspace.settings.securityTitle")}>
            <PointList
              accent="blue"
              items={[
                { icon: <ShieldIcon />, title: t("workspace.settings.security.passwordTitle"), text: t("workspace.settings.security.passwordDescription") },
                { icon: <TeamIcon />, title: t("workspace.settings.security.rolesTitle"), text: t("workspace.settings.security.rolesDescription") },
                { icon: <AuditIcon />, title: t("workspace.settings.security.auditTitle"), text: t("workspace.settings.security.auditDescription") },
                { icon: <SettingsIcon />, title: t("workspace.settings.security.offboardTitle"), text: t("workspace.settings.security.offboardDescription") },
              ]}
            />
          </Disclosure>

          <WorkspaceNote accent="blue" icon={<ShieldIcon />}>
            {t("workspace.settings.note")}
          </WorkspaceNote>
        </WorkspaceColumn>
      </WorkspaceSplit>
    </WorkspacePage>
  );
}
