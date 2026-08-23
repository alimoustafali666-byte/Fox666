import type { BadgeTone } from "@/components/ui/Badge";
import type { TranslationKey } from "@/lib/i18n";
import type { Role } from "@/lib/types";

// Shared between Header (role badge) and Settings > Team (role column) --
// a single place mapping the domain enum to a translation key, never to
// literal display text (see lib/i18n's centralized-dictionary rule).
export const ROLE_LABEL_KEYS: Record<Role, TranslationKey> = {
  owner: "common.roles.owner",
  admin: "common.roles.admin",
  manager: "common.roles.manager",
  member: "common.roles.member",
};

export const ROLE_TONE: Record<Role, BadgeTone> = {
  owner: "primary",
  admin: "info",
  manager: "info",
  member: "neutral",
};

export const ROLES: Role[] = ["owner", "admin", "manager", "member"];

