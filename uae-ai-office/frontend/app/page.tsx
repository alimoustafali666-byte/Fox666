"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { LoadingBlock } from "@/components/ui/Spinner";

export default function RootPage() {
  const { status } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    } else if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  return <LoadingBlock label={t("rootLoading")} />;
}

