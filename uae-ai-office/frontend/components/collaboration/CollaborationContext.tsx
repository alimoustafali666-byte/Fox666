"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { buildCollaborationWebSocketUrl, collaborationApi, getAccessToken } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { collaborationSocket, type CollaborationSocketEvent } from "@/lib/collaboration-socket";
import { useTranslation } from "@/lib/i18n";
import type { ChatConversationPublic } from "@/lib/types";

interface CollaborationContextValue {
  conversations: ChatConversationPublic[];
  loading: boolean;
  error: string | null;
  totalUnread: number;
  directPeerNames: Record<string, string>;
  refresh: () => Promise<void>;
  createDirect: (otherUserId: string) => Promise<ChatConversationPublic>;
  createGroup: (data: { name: string; description?: string; member_user_ids: string[] }) => Promise<ChatConversationPublic>;
  createProjectChannel: (data: {
    project_id: string;
    name: string;
    description?: string;
    member_user_ids: string[];
  }) => Promise<ChatConversationPublic>;
  applyConversationPatch: (id: string, patch: Partial<ChatConversationPublic>) => void;
  subscribeSocket: (listener: (event: CollaborationSocketEvent) => void) => () => void;
  sendSocket: (payload: Record<string, unknown>) => void;
}

const CollaborationContext = createContext<CollaborationContextValue | null>(null);

collaborationSocket.configure(buildCollaborationWebSocketUrl);

export function CollaborationProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ChatConversationPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [directPeerNames, setDirectPeerNames] = useState<Record<string, string>>({});
  const connectedRef = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await collaborationApi.list({ limit: 100 });
      setConversations(page.items);
    } catch {
      setError(t("messages.genericListError"));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // One realtime connection for as long as the Messages area is
  // mounted -- typing/presence/call signaling are only meaningful while
  // the user is actually looking at conversations.
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      collaborationSocket.connect(token);
      connectedRef.current = true;
    }
    return () => {
      if (connectedRef.current) {
        collaborationSocket.disconnect();
        connectedRef.current = false;
      }
    };
  }, []);

  // Direct conversations are never given a `name` server-side (there's
  // no single right name for a 1:1 -- it depends on who's looking), so
  // the "who am I talking to" label is resolved client-side from the
  // member roster, once per conversation, and cached here.
  useEffect(() => {
    if (!user) return;
    const unresolved = conversations.filter((c) => c.type === "direct" && !(c.id in directPeerNames));
    if (unresolved.length === 0) return;
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        unresolved.map(async (c) => {
          try {
            const members = await collaborationApi.listMembers(c.id);
            const peer = members.find((m) => m.user_id !== user.id);
            return [c.id, peer?.full_name || t("messages.untitledDirect")] as const;
          } catch {
            return [c.id, t("messages.untitledDirect")] as const;
          }
        })
      );
      if (!cancelled) {
        setDirectPeerNames((prev) => ({ ...prev, ...Object.fromEntries(entries) }));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversations, user]);

  const createDirect = useCallback(async (otherUserId: string) => {
    const conversation = await collaborationApi.createDirect(otherUserId);
    setConversations((prev) => {
      if (prev.some((c) => c.id === conversation.id)) return prev;
      return [conversation, ...prev];
    });
    return conversation;
  }, []);

  const createGroup = useCallback(
    async (data: { name: string; description?: string; member_user_ids: string[] }) => {
      const conversation = await collaborationApi.createGroup(data);
      setConversations((prev) => [conversation, ...prev]);
      return conversation;
    },
    []
  );

  const createProjectChannel = useCallback(
    async (data: { project_id: string; name: string; description?: string; member_user_ids: string[] }) => {
      const conversation = await collaborationApi.createProjectChannel(data);
      setConversations((prev) => [conversation, ...prev]);
      return conversation;
    },
    []
  );

  const applyConversationPatch = useCallback((id: string, patch: Partial<ChatConversationPublic>) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }, []);

  const subscribeSocket = useCallback((listener: (event: CollaborationSocketEvent) => void) => {
    return collaborationSocket.subscribe(listener);
  }, []);

  const sendSocket = useCallback((payload: Record<string, unknown>) => {
    collaborationSocket.send(payload);
  }, []);

  const totalUnread = useMemo(() => conversations.reduce((sum, c) => sum + c.unread_count, 0), [conversations]);

  const value = useMemo(
    () => ({
      conversations,
      loading,
      error,
      totalUnread,
      directPeerNames,
      refresh,
      createDirect,
      createGroup,
      createProjectChannel,
      applyConversationPatch,
      subscribeSocket,
      sendSocket,
    }),
    [
      conversations,
      loading,
      error,
      totalUnread,
      directPeerNames,
      refresh,
      createDirect,
      createGroup,
      createProjectChannel,
      applyConversationPatch,
      subscribeSocket,
      sendSocket,
    ]
  );

  return <CollaborationContext.Provider value={value}>{children}</CollaborationContext.Provider>;
}

export function useCollaboration(): CollaborationContextValue {
  const ctx = useContext(CollaborationContext);
  if (!ctx) throw new Error("useCollaboration must be used within CollaborationProvider");
  return ctx;
}

