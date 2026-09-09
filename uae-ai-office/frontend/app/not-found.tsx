"use client";

import Link from "next/link";
import { useTranslation } from "@/lib/i18n";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchIcon } from "@/components/layout/icons";

/** 404 for addresses outside both route groups (and for any unmatched
 *  path before a group's own not-found applies). Kept minimal and
 *  chrome-free: at this level there is no guarantee the visitor is
 *  signed in, so it links to the root, which routes them to the
 *  dashboard or to login depending on session state. */
export default function RootNotFound() {
  const { t } = useTranslation();

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "var(--space-6)" }}>
      <EmptyState
        icon={<SearchIcon />}
        title={t("notFound.title")}
        description={t("notFound.description")}
        action={
          <Link href="/" className={buttonClassName("primary")}>
            {t("notFound.backToDashboard")}
          </Link>
        }
      />
    </div>
  );
}
