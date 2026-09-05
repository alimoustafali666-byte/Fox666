"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "@/lib/i18n";
import { useAuth } from "@/lib/auth-context";
import { useMessagesUnreadBadge } from "@/lib/use-messages-badge";
import clsx from "../ui/clsx";
import { BrandMark } from "./BrandMark";
import { NAV_GROUPS } from "./navItems";
import { ROLE_LABEL_KEYS } from "./roles";
import { ChevronRightIcon } from "./icons";
import styles from "./Sidebar.module.css";

function initials(name: string | null, email: string): string {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { t } = useTranslation();
  const { user, role } = useAuth();
  const unreadMessages = useMessagesUnreadBadge();

  return (
    <>
      {open ? <div className={styles.overlay} onClick={onClose} aria-hidden="true" /> : null}
      <aside className={clsx(styles.sidebar, open && styles.sidebarOpen)}>
        <div className={styles.glow} aria-hidden="true" />
        <div className={styles.brand}>
          <BrandMark size={30} />
          <div className={styles.brandText}>
            <div className={styles.brandName}>{t("common.appName")}</div>
            <div className={styles.brandSub}>{t("common.tagline")}</div>
          </div>
        </div>

        <div className={styles.navScroll}>
          {NAV_GROUPS.map((group) => (
            <div className={styles.navGroup} key={group.label}>
              <span className={styles.groupLabel}>{t(group.label)}</span>
              <nav className={styles.nav}>
                {group.items.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={clsx(styles.navItem, styles[`accent-${item.accent}`], active && styles.navItemActive)}
                    >
                      <span className={styles.icon}>
                        <Icon width={15} height={15} />
                      </span>
                      <span className={styles.navLabel}>{t(item.labelKey)}</span>
                      {item.href === "/messages" && unreadMessages > 0 ? (
                        <span className={styles.navBadge}>{unreadMessages > 99 ? "99+" : unreadMessages}</span>
                      ) : null}
                      <ChevronRightIcon width={14} height={14} className={styles.chevron} />
                    </Link>
                  );
                })}
              </nav>
            </div>
          ))}
        </div>

        <div className={styles.dock}>
          <Link href="/settings" className={styles.profile}>
            <span className={styles.profileAvatar}>{user ? initials(user.full_name, user.email) : ""}</span>
            <span className={styles.profileInfo}>
              <span className={styles.profileName}>{user?.full_name || user?.email}</span>
              {role ? <span className={styles.profileRole}>{t(ROLE_LABEL_KEYS[role])}</span> : null}
            </span>
            <ChevronRightIcon width={14} height={14} className={styles.profileChevron} />
          </Link>
        </div>
      </aside>
    </>
  );
}
