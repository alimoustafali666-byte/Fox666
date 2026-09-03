"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import { useAuth } from "@/lib/auth-context";
import { useMessagesUnreadBadge } from "@/lib/use-messages-badge";
import clsx from "../ui/clsx";
import { BrandMark } from "./BrandMark";
import { DubaiSkyline } from "./DubaiSkyline";
import { ROLE_LABEL_KEYS } from "./roles";
import {
  AskIcon,
  BriefIcon,
  DashboardIcon,
  DocumentsIcon,
  HelpIcon,
  MessagesIcon,
  ProjectsIcon,
  ReportsIcon,
  SettingsIcon,
  TasksIcon,
} from "./icons";
import styles from "./Sidebar.module.css";

type NavItem = { href: string; labelKey: TranslationKey; icon: typeof DashboardIcon; accent: string };

// Same ten destinations and the same order as before -- the approved design
// only groups them under section labels, it adds and removes nothing.
const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", labelKey: "nav.dashboard", icon: DashboardIcon, accent: "blue" },
      { href: "/ask", labelKey: "nav.ask", icon: AskIcon, accent: "cyan" },
      { href: "/messages", labelKey: "nav.messages", icon: MessagesIcon, accent: "magenta" },
      { href: "/documents", labelKey: "nav.documents", icon: DocumentsIcon, accent: "amber" },
    ],
  },
  {
    label: "Delivery",
    items: [
      { href: "/projects", labelKey: "nav.projects", icon: ProjectsIcon, accent: "green" },
      { href: "/tasks", labelKey: "nav.tasks", icon: TasksIcon, accent: "rose" },
      { href: "/brief", labelKey: "nav.brief", icon: BriefIcon, accent: "sky" },
      { href: "/reports", labelKey: "nav.reports", icon: ReportsIcon, accent: "violet" },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/support", labelKey: "nav.help", icon: HelpIcon, accent: "orange" },
      { href: "/settings", labelKey: "nav.settings", icon: SettingsIcon, accent: "teal" },
    ],
  },
];

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
          <BrandMark size={32} />
          <div>
            <div className={styles.brandName}>{t("common.appName")}</div>
            <div className={styles.brandSub}>{t("common.tagline")}</div>
          </div>
        </div>
        <div className={styles.navScroll}>
          {NAV_GROUPS.map((group) => (
            <div className={styles.navGroup} key={group.label}>
              <span className={styles.groupLabel}>{group.label}</span>
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
                      <span className={styles.activeBar} />
                      <span className={styles.icon}>
                        <Icon />
                      </span>
                      {t(item.labelKey)}
                      {item.href === "/messages" && unreadMessages > 0 ? (
                        <span className={styles.navBadge}>{unreadMessages > 99 ? "99+" : unreadMessages}</span>
                      ) : null}
                    </Link>
                  );
                })}
              </nav>
            </div>
          ))}
        </div>
        <DubaiSkyline variant="sidebar" className={styles.skyline} />
        <div className={styles.dock}>
          <div className={styles.profile}>
            <div className={styles.profileAvatar}>{user ? initials(user.full_name, user.email) : ""}</div>
            <div className={styles.profileInfo}>
              <div className={styles.profileName}>{user?.full_name || user?.email}</div>
              {role ? <div className={styles.profileRole}>{t(ROLE_LABEL_KEYS[role])}</div> : null}
            </div>
            <span className={styles.status} aria-label="Online" />
          </div>
        </div>
      </aside>
    </>
  );
}

