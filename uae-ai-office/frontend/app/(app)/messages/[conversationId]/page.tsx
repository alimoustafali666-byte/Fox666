"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useCollaboration } from "@/components/collaboration/CollaborationContext";
import { AiPanel } from "@/components/collaboration/AiPanel";
import { CallPanel } from "@/components/collaboration/CallPanel";
import { Composer } from "@/components/collaboration/Composer";
import { MediaPanel } from "@/components/collaboration/MediaPanel";
import { MembersPanel } from "@/components/collaboration/MembersPanel";
import { MessageRow } from "@/components/collaboration/MessageRow";
import { SearchPanel } from "@/components/collaboration/SearchPanel";
import { useCollaborationCall } from "@/components/collaboration/useCollaborationCall";
import { collaborationApi, ApiError } from "@/lib/api-client";
import { errorMessage, useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { ZeroState } from "@/components/ui/Workspace";
import { MessagesIcon, PaperclipIcon, PhoneIcon, SearchIcon, SparkIcon, TeamIcon, VideoIcon } from "@/components/layout/icons";
import type { ChatConversationPublic, ChatMessagePublic, ConversationMemberPublic, ConversationType, PinnedMessagePublic } from "@/lib/types";
import type { TranslationKey } from "@/lib/i18n";
import styles from "./Thread.module.css";

const POLL_INTERVAL_MS = 6000;
const TYPING_DISPLAY_MS = 4000;

const TYPE_LABEL_KEY: Record<ConversationType, TranslationKey> = {
  direct: "messages.typeLabels.direct",
  group: "messages.typeLabels.group",
  project_channel: "messages.typeLabels.project_channel",
};

export default function ConversationThreadPage() {
  const params = useParams<{ conversationId: string }>();
  const router = useRouter();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { applyConversationPatch, subscribeSocket, sendSocket, directPeerNames, refresh: refreshConversations } = useCollaboration();

  const [conversation, setConversation] = useState<ChatConversationPublic | null>(null);
  const [members, setMembers] = useState<ConversationMemberPublic[]>([]);
  const [messages, setMessages] = useState<ChatMessagePublic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [pinned, setPinned] = useState<PinnedMessagePublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<ChatMessagePublic | null>(null);
  const [panel, setPanel] = useState<"members" | "ai" | "search" | "media" | null>(null);
  const [typingUsers, setTypingUsers] = useState<Map<string, number>>(new Map());
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<ChatMessagePublic[]>([]);
  messagesRef.current = messages;

  const conversationId = params.conversationId;
  const messageById = useMemo(() => new Map(messages.map((m) => [m.id, m])), [messages]);

  const self = members.find((m) => m.user_id === user?.id);
  const isAdmin = self ? self.role === "owner" || self.role === "admin" : false;
  const peerMember = conversation?.type === "direct" ? members.find((m) => m.user_id !== user?.id) : undefined;

  const call = useCollaborationCall({
    peerUserId: peerMember?.user_id ?? null,
    subscribeSocket,
    sendSocket,
  });

  const conversationTitle =
    conversation?.type === "direct"
      ? directPeerNames[conversation.id] || peerMember?.full_name || t("messages.untitledDirect")
      : conversation?.name || t("messages.untitledGroup");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [conversationDetail, memberList, messagePage, pins] = await Promise.all([
        collaborationApi.get(conversationId),
        collaborationApi.listMembers(conversationId),
        collaborationApi.listMessages(conversationId, { limit: 30 }),
        collaborationApi.listPins(conversationId),
      ]);
      setConversation(conversationDetail);
      setMembers(memberList);
      setMessages([...messagePage.items].reverse());
      setNextCursor(messagePage.next_cursor);
      setPinned(pins);
      const latest = messagePage.items[0];
      if (latest) {
        await collaborationApi.markRead(conversationId, latest.id);
        applyConversationPatch(conversationId, { unread_count: 0 });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError(t("messages.genericLoadError"));
      } else {
        setError(errorMessage(err, t("messages.genericLoadError")));
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  // Message delivery is REST-only (see backend/app/modules/collaboration/ws.py
  // -- the realtime socket carries only typing/presence/WebRTC signaling,
  // deliberately not message content), so a light poll keeps a peer's
  // sends, edits, deletes, and reactions showing up without a manual
  // refresh, mirroring the same tradeoff already made for the sidebar's
  // unread badge.
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const page = await collaborationApi.listMessages(conversationId, { limit: 30 });
        const current = messagesRef.current;
        const byId = new Map(current.map((m) => [m.id, m]));
        let changed = false;
        for (const incoming of page.items) {
          const existing = byId.get(incoming.id);
          if (!existing || JSON.stringify(existing) !== JSON.stringify(incoming)) {
            byId.set(incoming.id, incoming);
            changed = true;
          }
        }
        if (changed) {
          const merged = [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));
          setMessages(merged);
          const latest = page.items[0];
          if (latest && latest.sender_id !== user?.id) {
            await collaborationApi.markRead(conversationId, latest.id);
            applyConversationPatch(conversationId, { unread_count: 0 });
          }
        }
      } catch {
        // Best-effort background refresh -- a transient failure here
        // should never surface an error banner over an otherwise-working thread.
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, user?.id]);

  // Typing indicators: ephemeral, cleared automatically after a short
  // window in case a stop_typing event is ever missed (connection drop).
  useEffect(() => {
    const unsubscribe = subscribeSocket((event) => {
      if (event.type === "typing" && event.conversation_id === conversationId) {
        setTypingUsers((prev) => new Map(prev).set(event.user_id, Date.now()));
      } else if (event.type === "stop_typing" && event.conversation_id === conversationId) {
        setTypingUsers((prev) => {
          const next = new Map(prev);
          next.delete(event.user_id);
          return next;
        });
      }
    });
    return unsubscribe;
  }, [subscribeSocket, conversationId]);

  useEffect(() => {
    const interval = setInterval(() => {
      setTypingUsers((prev) => {
        const now = Date.now();
        const next = new Map([...prev].filter(([, ts]) => now - ts < TYPING_DISPLAY_MS));
        return next.size === prev.size ? prev : next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  async function loadOlder() {
    if (!nextCursor) return;
    try {
      const page = await collaborationApi.listMessages(conversationId, { limit: 30, cursor: nextCursor });
      setMessages((prev) => [...[...page.items].reverse(), ...prev]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function handleTyping() {
    sendSocket({ type: "typing", conversation_id: conversationId });
  }

  function handleStopTyping() {
    sendSocket({ type: "stop_typing", conversation_id: conversationId });
  }

  function handleMessageAppended(message: ChatMessagePublic) {
    setMessages((prev) => (prev.some((m) => m.id === message.id) ? prev : [...prev, message]));
    applyConversationPatch(conversationId, { updated_at: new Date().toISOString() });
  }

  function handleAttachmentAdded(message: ChatMessagePublic) {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === message.id);
      if (idx === -1) return [...prev, message];
      const next = [...prev];
      next[idx] = { ...next[idx], attachments: message.attachments };
      return next;
    });
  }

  async function handleEdit(messageId: string, content: string) {
    const updated = await collaborationApi.editMessage(messageId, content);
    setMessages((prev) => prev.map((m) => (m.id === messageId ? updated : m)));
  }

  async function handleDelete(messageId: string) {
    if (!window.confirm(t("messages.message.confirmDelete"))) return;
    try {
      const updated = await collaborationApi.deleteMessage(messageId);
      setMessages((prev) => prev.map((m) => (m.id === messageId ? updated : m)));
    } catch (err) {
      setError(errorMessage(err, t("messages.message.genericDeleteError")));
    }
  }

  async function handleToggleReaction(messageId: string, emoji: ChatMessagePublic["reactions"][number]["emoji"], alreadyReacted: boolean) {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId || !user) return m;
        const reactions = [...m.reactions];
        const idx = reactions.findIndex((r) => r.emoji === emoji);
        if (alreadyReacted) {
          if (idx >= 0) {
            const userIds = reactions[idx].user_ids.filter((id) => id !== user.id);
            if (userIds.length === 0) reactions.splice(idx, 1);
            else reactions[idx] = { ...reactions[idx], user_ids: userIds };
          }
        } else if (idx >= 0) {
          reactions[idx] = { ...reactions[idx], user_ids: [...reactions[idx].user_ids, user.id] };
        } else {
          reactions.push({ emoji, user_ids: [user.id] });
        }
        return { ...m, reactions };
      })
    );
    try {
      if (alreadyReacted) await collaborationApi.removeReaction(messageId, emoji);
      else await collaborationApi.addReaction(messageId, emoji);
    } catch (err) {
      setError(errorMessage(err, t("messages.message.genericReactionError")));
      load();
    }
  }

  async function handleTogglePin(messageId: string, currentlyPinned: boolean) {
    try {
      if (currentlyPinned) {
        await collaborationApi.unpinMessage(conversationId, messageId);
        setPinned((prev) => prev.filter((p) => p.message_id !== messageId));
      } else {
        await collaborationApi.pinMessage(conversationId, messageId);
        setPinned((prev) => [...prev, { message_id: messageId, pinned_by: user?.id ?? "", pinned_at: new Date().toISOString() }]);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function jumpToMessage(messageId: string) {
    document.getElementById(`message-${messageId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function handleLeft() {
    setPanel(null);
    refreshConversations();
    router.push("/messages");
  }

  const pinnedIds = new Set(pinned.map((p) => p.message_id));
  const typingNames = [...typingUsers.keys()]
    .map((id) => members.find((m) => m.user_id === id)?.full_name)
    .filter((name): name is string => Boolean(name));

  if (loading) return <LoadingBlock label={t("messages.loadingConversation")} />;
  if (!conversation) return <ErrorBanner message={error || t("messages.genericLoadError")} />;

  return (
    <>
      <div className={styles.header}>
        <div className={styles.headerTitleWrap}>
          <div className={styles.headerTitle}>{conversationTitle}</div>
          <div className={styles.headerMeta}>{t(TYPE_LABEL_KEY[conversation.type])}</div>
        </div>
        <div className={styles.headerActions}>
          {conversation.type === "direct" && peerMember ? (
            <>
              <button type="button" className={styles.iconAction} title={t("messages.calls.startVoiceCall")} onClick={() => call.startCall("voice", conversationId)}>
                <PhoneIcon />
              </button>
              <button type="button" className={styles.iconAction} title={t("messages.calls.startVideoCall")} onClick={() => call.startCall("video", conversationId)}>
                <VideoIcon />
              </button>
            </>
          ) : null}
          <button type="button" className={styles.iconAction} title={t("messages.search.openAction")} onClick={() => setPanel(panel === "search" ? null : "search")}>
            <SearchIcon />
          </button>
          <button type="button" className={styles.iconAction} title={t("messages.media.openAction")} onClick={() => setPanel(panel === "media" ? null : "media")}>
            <PaperclipIcon />
          </button>
          <button type="button" className={styles.iconAction} title={t("messages.ai.panelTitle")} onClick={() => setPanel(panel === "ai" ? null : "ai")}>
            <SparkIcon />
          </button>
          <button type="button" className={styles.iconAction} title={t("messages.members.title")} onClick={() => setPanel(panel === "members" ? null : "members")}>
            <TeamIcon />
          </button>
        </div>
      </div>

      {conversation.type !== "direct" ? (
        <div style={{ padding: "6px var(--space-5)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-border)" }}>
          {t("messages.calls.groupCallUnsupported")}
        </div>
      ) : null}

      {pinned.length > 0 ? (
        <div className={styles.pinnedBar}>
          <strong>{t("messages.message.pinnedMessagesTitle")}:</strong>
          {pinned.map((p) => (
            <button key={p.message_id} type="button" className={styles.pinnedLink} onClick={() => jumpToMessage(p.message_id)}>
              {messageById.get(p.message_id)?.content.slice(0, 40) || t("messages.message.jumpToMessage")}
            </button>
          ))}
        </div>
      ) : null}

      <div className={styles.body}>
        <div className={styles.threadColumn}>
          {error ? <ErrorBanner message={error} /> : null}

          <div className={styles.messages} ref={scrollRef} data-empty={messages.length === 0 ? "true" : undefined}>
            {nextCursor ? (
              <div className={styles.loadOlderWrap}>
                <Button size="sm" variant="secondary" onClick={loadOlder}>
                  {t("messages.loadOlder")}
                </Button>
              </div>
            ) : null}

            {messages.length === 0 ? (
              <ZeroState
                accent="cyan"
                icon={<MessagesIcon />}
                title={t("messages.threadEmpty")}
                text={t("workspace.messages.recentEmptyText")}
              />
            ) : (
              messages.map((message) => (
                <MessageRow
                  key={message.id}
                  message={message}
                  currentUserId={user?.id ?? ""}
                  isAdmin={isAdmin}
                  isPinned={pinnedIds.has(message.id)}
                  replyPreview={message.reply_to_message_id ? messageById.get(message.reply_to_message_id) ?? null : null}
                  onReply={setReplyTo}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  onToggleReaction={handleToggleReaction}
                  onTogglePin={handleTogglePin}
                />
              ))
            )}
          </div>

          <div className={styles.typingIndicator}>
            {typingNames.length === 1
              ? t("messages.typingIndicator", { name: typingNames[0] })
              : typingNames.length > 1
                ? t("messages.typingIndicatorMultiple")
                : ""}
          </div>

          <Composer
            conversationId={conversationId}
            replyTo={replyTo}
            onCancelReply={() => setReplyTo(null)}
            onSent={handleMessageAppended}
            onAttachmentAdded={handleAttachmentAdded}
            onTyping={handleTyping}
            onStopTyping={handleStopTyping}
          />
        </div>

        {panel === "members" ? (
          <MembersPanel
            conversation={conversation}
            onClose={() => setPanel(null)}
            onRenamed={(patch) => {
              setConversation((prev) => (prev ? { ...prev, ...patch } : prev));
              applyConversationPatch(conversationId, patch);
            }}
            onLeft={handleLeft}
          />
        ) : null}

        {panel === "ai" ? <AiPanel conversationId={conversationId} onClose={() => setPanel(null)} onJumpToMessage={jumpToMessage} /> : null}

        {panel === "search" ? (
          <SearchPanel conversationId={conversationId} onClose={() => setPanel(null)} onJumpToMessage={jumpToMessage} />
        ) : null}

        {panel === "media" ? <MediaPanel conversationId={conversationId} onClose={() => setPanel(null)} /> : null}
      </div>

      <CallPanel
        phase={call.phase}
        callType={call.callType}
        peerName={peerMember?.full_name || conversationTitle}
        localStream={call.localStream}
        remoteStream={call.remoteStream}
        muted={call.muted}
        cameraOff={call.cameraOff}
        onAnswer={call.answerCall}
        onDecline={call.declineCall}
        onHangUp={call.hangUp}
        onToggleMute={call.toggleMute}
        onToggleCamera={call.toggleCamera}
      />
    </>
  );
}

