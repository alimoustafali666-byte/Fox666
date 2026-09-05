import type { TranslationKey } from "@/lib/i18n";
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

export type NavItem = {
  href: string;
  labelKey: TranslationKey;
  icon: typeof DashboardIcon;
  accent: string;
};

// The same ten destinations the sidebar has always had -- the approved master
// only regroups them under WORKSPACE / ACCOUNT, it adds and removes nothing.
// The header's quick search reads from this list too, so it can never jump
// anywhere the navigation doesn't already go.
export const NAV_GROUPS: { label: TranslationKey; items: NavItem[] }[] = [
  {
    label: "dashboard.v2.navWorkspace",
    items: [
      { href: "/dashboard", labelKey: "nav.dashboard", icon: DashboardIcon, accent: "blue" },
      { href: "/ask", labelKey: "nav.ask", icon: AskIcon, accent: "cyan" },
      { href: "/messages", labelKey: "nav.messages", icon: MessagesIcon, accent: "magenta" },
      { href: "/projects", labelKey: "nav.projects", icon: ProjectsIcon, accent: "green" },
      { href: "/tasks", labelKey: "nav.tasks", icon: TasksIcon, accent: "rose" },
      { href: "/brief", labelKey: "nav.brief", icon: BriefIcon, accent: "sky" },
      { href: "/reports", labelKey: "nav.reports", icon: ReportsIcon, accent: "violet" },
      { href: "/documents", labelKey: "nav.documents", icon: DocumentsIcon, accent: "amber" },
    ],
  },
  {
    label: "dashboard.v2.navAccount",
    items: [
      { href: "/settings", labelKey: "nav.settings", icon: SettingsIcon, accent: "teal" },
      { href: "/support", labelKey: "nav.help", icon: HelpIcon, accent: "orange" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
