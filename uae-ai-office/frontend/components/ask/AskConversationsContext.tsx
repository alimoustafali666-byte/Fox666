"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { conversationsApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import type { ConversationPublic } from "@/lib/types";

interface AskConversationsValue {
  conversations: ConversationPublic[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createConversation: () => Promise<ConversationPublic>;
}

const AskConversationsContext = createContext<AskConversationsValue | null>(null);

export function AskConversationsProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [conversations, setConversations] = useState<ConversationPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await conversationsApi.list({ limit: 50 });
      setConversations(page.items);
    } catch {
      setError(t("ask.genericListError"));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createConversation = useCallback(async () => {
    const conversation = await conversationsApi.create();
    setConversations((prev) => [conversation, ...prev]);
    return conversation;
  }, []);

  const value = useMemo(
    () => ({ conversations, loading, error, refresh, createConversation }),
    [conversations, loading, error, refresh, createConversation]
  );

  return <AskConversationsContext.Provider value={value}>{children}</AskConversationsContext.Provider>;
}

export function useAskConversations(): AskConversationsValue {
  const ctx = useContext(AskConversationsContext);
  if (!ctx) throw new Error("useAskConversations must be used within AskConversationsProvider");
  return ctx;
}

