"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth, errorMessage } from "@/lib/auth-context";
import { authApi, tenancyApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { CompanyBrandingCard } from "@/components/settings/CompanyBrandingCard";
import { AuditIcon, TeamIcon } from "@/components/layout/icons";
import styles from "./Settings.module.css";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, Input } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

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
    <div>
      <PageHeader title={t("settings.title")} description={t("settings.description")} />

      <Card><CardBody><h2>{t("settings.profile.title")}</h2><FieldWrapper label={t("settings.profile.name")} htmlFor="profile-name"><Input id="profile-name" value={fullName} onChange={(event) => setFullName(event.target.value)} /></FieldWrapper><p>{user?.email}</p>{profileMessage ? <p>{profileMessage}</p> : null}<Button onClick={saveProfile} loading={profileBusy}>{t("settings.profile.save")}</Button><div style={{ marginTop: "var(--space-6)" }}><h3>{t("settings.profile.password")}</h3><FieldWrapper label={t("settings.profile.currentPassword")} htmlFor="current-password"><Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></FieldWrapper><FieldWrapper label={t("settings.profile.newPassword")} htmlFor="new-password"><Input id="new-password" type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></FieldWrapper>{passwordMessage ? <p>{passwordMessage}</p> : null}<Button onClick={savePassword} loading={passwordBusy} disabled={!currentPassword || newPassword.length < 12}>{t("settings.profile.changePassword")}</Button></div></CardBody></Card>

      {company ? (
        <div style={{ marginBottom: "var(--space-6)" }}>
          <CompanyBrandingCard />
        </div>
      ) : null}

      {canViewAuditLog ? <Card>
        <CardBody>
          <h2>{t("settings.dailyBriefSchedule.title")}</h2>
          <p>{t("settings.dailyBriefSchedule.description")}</p>
          {scheduleError ? <ErrorBanner message={scheduleError} /> : null}
          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: "16px 0" }}>
            <Input type="checkbox" checked={scheduleEnabled} onChange={(event) => setScheduleEnabled(event.target.checked)} />
            {t("settings.dailyBriefSchedule.enabled")}
          </label>
          <FieldWrapper label={t("settings.dailyBriefSchedule.time")} htmlFor="daily-brief-time">
            <Input id="daily-brief-time" type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} disabled={!scheduleEnabled} />
          </FieldWrapper>
          <p>{t("settings.dailyBriefSchedule.timezone", { timezone: scheduleTimezone || company?.timezone || "" })}</p>
          <Button onClick={saveSchedule} loading={savingSchedule}>{t("settings.dailyBriefSchedule.save")}</Button>
        </CardBody>
      </Card> : null}

      <div className={styles.grid}>
        <Link href="/settings/team" style={{ display: "block" }}>
          <Card className={styles.hoverCard}>
            <CardBody>
              <div className={styles.linkCard}>
                <span className={styles.linkIcon}>
                  <TeamIcon />
                </span>
                <span>
                  <div className={styles.linkTitle}>{t("settings.team.linkTitle")}</div>
                  <div className={styles.linkDescription}>{t("settings.team.linkDescription")}</div>
                </span>
              </div>
            </CardBody>
          </Card>
        </Link>

        {canViewAuditLog ? (
          <Link href="/settings/audit-log" style={{ display: "block" }}>
            <Card className={styles.hoverCard}>
              <CardBody>
                <div className={styles.linkCard}>
                  <span className={styles.linkIcon}>
                    <AuditIcon />
                  </span>
                  <span>
                    <div className={styles.linkTitle}>{t("settings.auditLog.linkTitle")}</div>
                    <div className={styles.linkDescription}>{t("settings.auditLog.linkDescription")}</div>
                  </span>
                </div>
              </CardBody>
            </Card>
          </Link>
        ) : null}
      </div>
    </div>
  );
}

