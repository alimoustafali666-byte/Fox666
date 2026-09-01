"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAskConversations } from "@/components/ask/AskConversationsContext";
import { useTranslation } from "@/lib/i18n";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { SparkIcon } from "@/components/layout/icons";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { errorMessage } from "@/lib/auth-context";

export default function AskLandingPage() {
  const { createConversation } = useAskConversations();
  const router = useRouter();
  const { t } = useTranslation();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setCreating(true);
    setError(null);
    try {
      const conversation = await createConversation();
      router.push(`/ask/${conversation.id}`);
    } catch (err) {
      setError(errorMessage(err, t("ask.genericListError")));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: "var(--space-4)" }}>
      {error ? <ErrorBanner message={error} /> : null}
      <EmptyState
        icon={<SparkIcon />}
        title={t("ask.emptyTitle")}
        description={t("ask.emptyDescription")}
        action={
          <Button onClick={handleStart} loading={creating}>
            {creating ? t("ask.starting") : t("ask.startConversation")}
          </Button>
        }
      />
    </div>
  );
}

