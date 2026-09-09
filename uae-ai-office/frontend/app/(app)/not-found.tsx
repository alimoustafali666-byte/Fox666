"use client";

import Link from "next/link";
import { useTranslation } from "@/lib/i18n";
import { buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchIcon } from "@/components/layout/icons";

/** 404 for signed-in routes. Rendered inside the app shell, so a mistyped
 *  or stale link leaves the user inside the product with working
 *  navigation rather than on a bare browser error page. */
export default function AppNotFound() {
  const { t } = useTranslation();

  return (
    <EmptyState
      icon={<SearchIcon />}
      title={t("notFound.title")}
      description={t("notFound.description")}
      action={
        <Link href="/dashboard" className={buttonClassName("primary")}>
          {t("notFound.backToDashboard")}
        </Link>
      }
    />
  );
}
