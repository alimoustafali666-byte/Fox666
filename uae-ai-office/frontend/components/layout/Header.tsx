"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { buttonClassName } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { CompanyLogo } from "./CompanyLogo";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MenuIcon } from "./icons";
import { ROLE_LABEL_KEYS } from "./roles";
import styles from "./Header.module.css";

// Today's date in the active locale -- rendered client-side after mount so a
// server-rendered date can never disagree with the viewer's own clock.
function DateChip({ locale }: { locale: string }) {
  const [today, setToday] = useState<Date | null>(null);
  useEffect(() => { setToday(new Date()); }, []);
  if (!today) return null;
  return (
    <div className={styles.dateChip}>
      <span className={styles.dateMain}>
        {new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short", year: "numeric" }).format(today)}
      </span>
      <span className={styles.dateSub}>
        {new Intl.DateTimeFormat(locale, { weekday: "long" }).format(today)}
      </span>
    </div>
  );
}

function initials(name: string | null, email: string): string {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function Header({ onToggleMenu }: { onToggleMenu: () => void }) {
  const { user, company, role, logout, switchCompany } = useAuth();
  const { t, locale } = useTranslation();
  const [companies, setCompanies] = useState<{ company_id: string; company_name: string }[]>([]);
  useEffect(() => { authApi.listCompanies().then(setCompanies).catch(() => setCompanies([])); }, []);

  return (
    <header className={styles.header}>
      <button
        type="button"
        className={styles.menuButton}
        onClick={onToggleMenu}
        aria-label={t("appShell.toggleNavigation")}
      >
        <MenuIcon />
      </button>

      {company ? (
        <div className={styles.companyRow}>
          <CompanyLogo hasLogo={company.has_logo} size={32} />
          <div className={styles.company}>
            <span className={styles.companyName}>{company.name}</span>
            <span className={styles.companyMeta}>
              {company.country} · {company.timezone}
            </span>
          </div>
        </div>
      ) : null}
      {companies.length > 1 ? <select className={styles.companySelect} aria-label="Company" value={company?.id ?? ""} onChange={(event) => void switchCompany(event.target.value)}><option value="">{company?.name}</option>{companies.filter((item) => item.company_id !== company?.id).map((item) => <option key={item.company_id} value={item.company_id}>{item.company_name}</option>)}</select> : null}

      <div className={styles.spacer} />

      <DateChip locale={locale} />

      <div className={styles.divider} />

      <div className={styles.user}>
        <div className={styles.avatar}>{user ? initials(user.full_name, user.email) : ""}</div>
        <div className={styles.userInfo}>
          <span className={styles.userName}>{user?.full_name || user?.email}</span>
          <span className={styles.userEmail}>{user?.email}</span>
        </div>
        {role ? <Badge tone="primary">{t(ROLE_LABEL_KEYS[role])}</Badge> : null}
      </div>

      <div className={styles.divider} />

      <LanguageSwitcher />

      <button
        type="button"
        className={buttonClassName("secondary", "sm")}
        onClick={() => {
          void logout();
        }}
      >
        {t("header.logOut")}
      </button>
    </header>
  );
}

