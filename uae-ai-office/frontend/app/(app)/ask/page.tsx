"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAskConversations } from "@/components/ask/AskConversationsContext";
import { useTranslation } from "@/lib/i18n";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { SparkIcon } from "@/components/layout/icons";

export default function AskLandingPage() {
  const { createConversation } = useAskConversations();
  const router = useRouter();
  const { t } = useTranslation();
  const [creating, setCreating] = useState(false);

  async function handleStart() {
    setCreating(true);
    try {
      const conversation = await createConversation();
      router.push(`/ask/${conversation.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
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

