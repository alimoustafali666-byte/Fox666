"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslation, formatDateTime } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import clsx from "@/components/ui/clsx";
import { REACTION_EMOJIS, type ChatMessagePublic } from "@/lib/types";
import { AttachmentView } from "./AttachmentView";
import { REACTION_GLYPHS } from "./reactionGlyphs";
import styles from "./MessageRow.module.css";

interface MessageRowProps {
  message: ChatMessagePublic;
  currentUserId: string;
  isAdmin: boolean;
  isPinned: boolean;
  replyPreview: ChatMessagePublic | null;
  onReply: (message: ChatMessagePublic) => void;
  onEdit: (messageId: string, content: string) => Promise<void>;
  onDelete: (messageId: string) => void;
  onToggleReaction: (messageId: string, emoji: (typeof REACTION_EMOJIS)[number], alreadyReacted: boolean) => void;
  onTogglePin: (messageId: string, currentlyPinned: boolean) => void;
}

export function MessageRow({
  message,
  currentUserId,
  isAdmin,
  isPinned,
  replyPreview,
  onReply,
  onEdit,
  onDelete,
  onToggleReaction,
  onTogglePin,
}: MessageRowProps) {
  const { t, locale } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const isOwn = message.sender_id === currentUserId;
  const isSystem = message.message_type === "system";
  const isDeleted = message.deleted_at !== null;

  async function handleSaveEdit() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      await onEdit(message.id, trimmed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (isSystem) {
    return <div className={styles.systemRow}>{message.content}</div>;
  }

  return (
    <div id={`message-${message.id}`} className={clsx(styles.row, isOwn && styles.rowOwn)}>
      <div className={styles.bubbleWrap}>
        {!isOwn ? <div className={styles.senderName}>{message.sender_name || ""}</div> : null}

        {replyPreview ? (
          <a href={`#message-${replyPreview.id}`} className={styles.replyPreview}>
            {replyPreview.sender_name || ""}: {replyPreview.deleted_at ? t("messages.message.deletedPlaceholder") : replyPreview.content}
          </a>
        ) : null}

        <div className={clsx(styles.bubble, isOwn && styles.bubbleOwn, isDeleted && styles.bubbleDeleted)}>
          {isDeleted ? (
            t("messages.message.deletedPlaceholder")
          ) : editing ? (
            <div className={styles.editForm}>
              <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} maxLength={4000} />
              <div className={styles.editActions}>
                <Button size="sm" loading={saving} onClick={handleSaveEdit} disabled={!draft.trim()}>
                  {t("messages.message.saveEdit")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => { setEditing(false); setDraft(message.content); }}>
                  {t("messages.message.cancelEdit")}
                </Button>
              </div>
            </div>
          ) : (
            <>
              <span className={styles.content}>{message.content}</span>
              {message.edited_at ? <span className={styles.editedTag}> {t("messages.message.edited")}</span> : null}
            </>
          )}

          {!isDeleted && message.attachments.length > 0 ? (
            <div className={styles.attachments}>
              {message.attachments.map((a) => (
                <AttachmentView key={a.id} attachment={a} />
              ))}
            </div>
          ) : null}
        </div>

        {!isDeleted && message.reactions.length > 0 ? (
          <div className={styles.reactionsBar}>
            {message.reactions.map((r) => {
              const mine = r.user_ids.includes(currentUserId);
              return (
                <button
                  key={r.emoji}
                  type="button"
                  className={clsx(styles.reactionChip, mine && styles.reactionChipMine)}
                  onClick={() => onToggleReaction(message.id, r.emoji, mine)}
                  title={t(`messages.reactions.${r.emoji}` as never)}
                >
                  {REACTION_GLYPHS[r.emoji]} {r.user_ids.length}
                </button>
              );
            })}
          </div>
        ) : null}

        <div className={styles.metaRow}>
          <span className={styles.timestamp}>{formatDateTime(locale, message.created_at, { hour: "2-digit", minute: "2-digit" })}</span>

          {!isDeleted ? (
            <div className={styles.actions}>
              <button type="button" className={styles.actionButton} onClick={() => setPickerOpen((v) => !v)}>
                {t("messages.message.reactAction")}
              </button>
              <button type="button" className={styles.actionButton} onClick={() => onReply(message)}>
                {t("messages.message.replyAction")}
              </button>
              <Link
                href={`/tasks/new?title=${encodeURIComponent(message.content.slice(0, 200))}&source_type=message&source_id=${message.id}`}
                className={styles.actionButton}
              >
                {t("messages.message.createTaskAction")}
              </Link>
              {isAdmin ? (
                <button type="button" className={styles.actionButton} onClick={() => onTogglePin(message.id, isPinned)}>
                  {isPinned ? t("messages.message.unpinAction") : t("messages.message.pinAction")}
                </button>
              ) : null}
              {isOwn ? (
                <>
                  <button type="button" className={styles.actionButton} onClick={() => setEditing(true)}>
                    {t("messages.message.editAction")}
                  </button>
                  <button type="button" className={styles.actionButton} onClick={() => onDelete(message.id)}>
                    {t("messages.message.deleteAction")}
                  </button>
                </>
              ) : null}
            </div>
          ) : null}
        </div>

        {pickerOpen ? (
          <div className={styles.emojiPicker}>
            {REACTION_EMOJIS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                className={styles.emojiOption}
                onClick={() => {
                  const existing = message.reactions.find((r) => r.emoji === emoji);
                  onToggleReaction(message.id, emoji, existing ? existing.user_ids.includes(currentUserId) : false);
                  setPickerOpen(false);
                }}
                title={t(`messages.reactions.${emoji}` as never)}
              >
                {REACTION_GLYPHS[emoji]}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

