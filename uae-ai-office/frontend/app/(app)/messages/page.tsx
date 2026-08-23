"use client";

import Link from "next/link";
import { useTranslation } from "@/lib/i18n";
import { EmptyState } from "@/components/ui/EmptyState";
import { buttonClassName } from "@/components/ui/Button";
import { MessagesIcon } from "@/components/layout/icons";

export default function MessagesLandingPage() {
  const { t } = useTranslation();

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
      <EmptyState
        icon={<MessagesIcon />}
        title={t("messages.emptyTitle")}
        description={t("messages.emptyDescription")}
        action={
          <Link href="/messages/new?type=direct" className={buttonClassName("primary", "md")}>
            {t("messages.newDirect")}
          </Link>
        }
      />
    </div>
  );
}

