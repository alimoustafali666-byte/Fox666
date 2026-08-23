"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { CompanyBrandingCard } from "@/components/settings/CompanyBrandingCard";
import { AuditIcon, TeamIcon } from "@/components/layout/icons";
import styles from "./Settings.module.css";

export default function SettingsPage() {
  const { company, role } = useAuth();
  const { t } = useTranslation();
  const canViewAuditLog = role === "owner" || role === "admin";

  return (
    <div>
      <PageHeader title={t("settings.title")} description={t("settings.description")} />

      {company ? (
        <div style={{ marginBottom: "var(--space-6)" }}>
          <CompanyBrandingCard />
        </div>
      ) : null}

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

