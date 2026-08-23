"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation, type TranslationKey } from "@/lib/i18n";
import { useMessagesUnreadBadge } from "@/lib/use-messages-badge";
import clsx from "../ui/clsx";
import { BrandMark } from "./BrandMark";
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

const NAV_ITEMS: { href: string; labelKey: TranslationKey; icon: typeof DashboardIcon }[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: DashboardIcon },
  { href: "/ask", labelKey: "nav.ask", icon: AskIcon },
  { href: "/messages", labelKey: "nav.messages", icon: MessagesIcon },
  { href: "/documents", labelKey: "nav.documents", icon: DocumentsIcon },
  { href: "/projects", labelKey: "nav.projects", icon: ProjectsIcon },
  { href: "/tasks", labelKey: "nav.tasks", icon: TasksIcon },
  { href: "/brief", labelKey: "nav.brief", icon: BriefIcon },
  { href: "/reports", labelKey: "nav.reports", icon: ReportsIcon },
  { href: "/support", labelKey: "nav.help", icon: HelpIcon },
  { href: "/settings", labelKey: "nav.settings", icon: SettingsIcon },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { t } = useTranslation();
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
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(styles.navItem, active && styles.navItemActive)}
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
      </aside>
    </>
  );
}

