"use client";

import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { buttonClassName } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { CompanyLogo } from "./CompanyLogo";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MenuIcon } from "./icons";
import { ROLE_LABEL_KEYS } from "./roles";
import styles from "./Header.module.css";

function initials(name: string | null, email: string): string {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function Header({ onToggleMenu }: { onToggleMenu: () => void }) {
  const { user, company, role, logout } = useAuth();
  const { t } = useTranslation();

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

      <div className={styles.spacer} />

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

