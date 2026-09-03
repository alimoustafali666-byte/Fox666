"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { authApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import { useMessagesUnreadBadge } from "@/lib/use-messages-badge";
import { CompanyLogo } from "./CompanyLogo";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { BellIcon, MenuIcon, SearchIcon } from "./icons";
import { NAV_ITEMS } from "./navItems";
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

// Quick jump across the workspace. It only ever resolves to destinations the
// navigation already exposes (see ./navItems) -- no new route, and no search
// endpoint is called, so it never invents results.
function QuickSearch() {
  const { t } = useTranslation();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement | null>(null);

  const term = query.trim().toLowerCase();
  const matches = term
    ? NAV_ITEMS.filter((item) => t(item.labelKey).toLowerCase().includes(term)).slice(0, 6)
    : [];

  function go(href: string) {
    setQuery("");
    setOpen(false);
    router.push(href);
  }

  return (
    <div
      className={styles.search}
      ref={boxRef}
      onBlur={(event) => {
        if (!boxRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <SearchIcon width={15} height={15} />
      <input
        type="search"
        value={query}
        placeholder={t("header.searchPlaceholder")}
        aria-label={t("header.search")}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "Enter" && matches.length > 0) {
            event.preventDefault();
            go(matches[0].href);
          }
        }}
      />
      {open && term ? (
        <div className={styles.searchResults} role="listbox">
          {matches.length > 0 ? (
            matches.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.href}
                  type="button"
                  role="option"
                  aria-selected="false"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => go(item.href)}
                >
                  <Icon width={15} height={15} />
                  {t(item.labelKey)}
                </button>
              );
            })
          ) : (
            <span className={styles.searchEmpty}>{t("header.noResults")}</span>
          )}
        </div>
      ) : null}
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
  const unread = useMessagesUnreadBadge();
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
          <CompanyLogo hasLogo={company.has_logo} size={26} />
          <div className={styles.company}>
            <span className={styles.companyName}>{company.name}</span>
            <span className={styles.companyMeta}>
              {company.country} · {company.timezone}
            </span>
          </div>
        </div>
      ) : null}

      {companies.length > 1 ? (
        <select
          className={styles.companySelect}
          aria-label="Company"
          value={company?.id ?? ""}
          onChange={(event) => void switchCompany(event.target.value)}
        >
          <option value="">{company?.name}</option>
          {companies
            .filter((item) => item.company_id !== company?.id)
            .map((item) => (
              <option key={item.company_id} value={item.company_id}>
                {item.company_name}
              </option>
            ))}
        </select>
      ) : null}

      <div className={styles.spacer} />

      <QuickSearch />

      <LanguageSwitcher />

      <Link
        href="/messages/notifications"
        className={styles.iconButton}
        aria-label={t("header.notifications")}
      >
        <BellIcon width={16} height={16} />
        {unread > 0 ? <span className={styles.iconBadge}>{unread > 99 ? "99+" : unread}</span> : null}
      </Link>

      <DateChip locale={locale} />

      <Link href="/settings" className={styles.user}>
        <span className={styles.avatar}>{user ? initials(user.full_name, user.email) : ""}</span>
        <span className={styles.userInfo}>
          <span className={styles.userName}>{user?.full_name || user?.email}</span>
          <span className={styles.userRole}>{role ? t(ROLE_LABEL_KEYS[role]) : ""}</span>
        </span>
      </Link>

      <button
        type="button"
        className={styles.logout}
        onClick={() => {
          void logout();
        }}
      >
        {t("header.logOut")}
      </button>
    </header>
  );
}
