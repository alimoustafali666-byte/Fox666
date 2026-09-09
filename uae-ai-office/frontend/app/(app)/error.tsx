"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useTranslation } from "@/lib/i18n";
import { Button, buttonClassName } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ShieldIcon } from "@/components/layout/icons";

/** Route-level error boundary for every signed-in screen. Without it, an
 *  unhandled render error in one module blanks the whole application
 *  shell; with it, the sidebar and header stay usable and the user can
 *  navigate away from the broken screen. `digest` is the server-side
 *  correlation id Next.js attaches -- shown so a user reporting the
 *  problem can quote something that matches the server logs. */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useTranslation();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <EmptyState
      icon={<ShieldIcon />}
      title={t("errorBoundary.title")}
      description={
        error.digest
          ? `${t("errorBoundary.description")} (${t("errorBoundary.referenceLabel")}: ${error.digest})`
          : t("errorBoundary.description")
      }
      action={
        <>
          <Button onClick={reset}>{t("errorBoundary.retry")}</Button>
          <Link href="/dashboard" className={buttonClassName("secondary")}>
            {t("errorBoundary.backToDashboard")}
          </Link>
        </>
      }
    />
  );
}
