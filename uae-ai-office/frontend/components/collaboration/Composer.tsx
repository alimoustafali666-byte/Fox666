"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from "react";
import { collaborationApi, ApiError } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import type { ChatMessagePublic } from "@/lib/types";
import styles from "./Composer.module.css";
import { MicIcon, PaperclipIcon, StopIcon } from "@/components/layout/icons";

const TYPING_DEBOUNCE_MS = 2500;

interface ComposerProps {
  conversationId: string;
  replyTo: ChatMessagePublic | null;
  onCancelReply: () => void;
  onSent: (message: ChatMessagePublic) => void;
  onAttachmentAdded: (message: ChatMessagePublic) => void;
  onTyping: () => void;
  onStopTyping: () => void;
}

export function Composer({ conversationId, replyTo, onCancelReply, onSent, onAttachmentAdded, onTyping, onStopTyping }: ComposerProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      if (recordIntervalRef.current) clearInterval(recordIntervalRef.current);
    };
  }, []);

  function handleContentChange(value: string) {
    setContent(value);
    onTyping();
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(onStopTyping, TYPING_DEBOUNCE_MS);
  }

  const handleSend = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      const trimmed = content.trim();
      if (!trimmed || sending) return;
      setError(null);
      setSending(true);
      try {
        const message = await collaborationApi.sendMessage(conversationId, {
          content: trimmed,
          reply_to_message_id: replyTo?.id ?? null,
        });
        setContent("");
        onCancelReply();
        onStopTyping();
        onSent(message);
      } catch (err) {
        const fallback =
          err instanceof ApiError && err.status === 429
            ? t("messages.composer.rateLimitedError")
            : t("messages.composer.genericSendError");
        setError(errorMessage(err, fallback));
      } finally {
        setSending(false);
      }
    },
    [content, sending, conversationId, replyTo, onCancelReply, onStopTyping, onSent, t]
  );

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend(event as unknown as FormEvent);
    }
  }

  async function uploadFile(file: File, durationSeconds?: number) {
    setError(null);
    setUploading(true);
    try {
      // Attachments hang off a message -- send a lightweight placeholder
      // text message first (or reuse the last own message?) -- the
      // backend requires an existing message_id, so a lone attachment
      // still needs a parent message. A short auto-caption keeps this
      // predictable rather than silently reusing an unrelated message.
      const parent = await collaborationApi.sendMessage(conversationId, {
        content: file.name,
        reply_to_message_id: replyTo?.id ?? null,
      });
      onCancelReply();
      const attachment = await collaborationApi.uploadAttachment(parent.id, {
        conversation_id: conversationId,
        file,
        duration_seconds: durationSeconds,
      });
      onAttachmentAdded({ ...parent, attachments: [attachment] });
    } catch (err) {
      setError(errorMessage(err, t("messages.composer.genericAttachError")));
    } finally {
      setUploading(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) uploadFile(file);
  }

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/ogg;codecs=opus";
      const recorder = new MediaRecorder(stream, { mimeType });
      recordedChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(recordedChunksRef.current, { type: mimeType });
        const extension = mimeType.startsWith("audio/webm") ? "webm" : "ogg";
        const file = new File([blob], `voice-note.${extension}`, { type: mimeType });
        const duration = recordSeconds;
        setRecordSeconds(0);
        await uploadFile(file, duration);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setRecordSeconds(0);
      recordIntervalRef.current = setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    } catch {
      setError(t("messages.composer.micUnavailable"));
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setRecording(false);
    if (recordIntervalRef.current) {
      clearInterval(recordIntervalRef.current);
      recordIntervalRef.current = null;
    }
  }

  return (
    <div className={styles.composer}>
      {error ? <ErrorBanner message={error} /> : null}

      {replyTo ? (
        <div className={styles.replyBanner}>
          <span>
            {t("messages.composer.replyingTo", { name: replyTo.sender_name || "" })}: {replyTo.content}
          </span>
          <button type="button" onClick={onCancelReply}>
            {t("messages.composer.cancelReply")}
          </button>
        </div>
      ) : null}

      <form className={styles.row} onSubmit={handleSend}>
        <input ref={fileInputRef} type="file" hidden onChange={handleFileChange} accept=".pdf,.docx,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.webp" />
        <button
          type="button"
          className={styles.iconButton}
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || recording}
          title={t("messages.composer.attach")}
        >
          <PaperclipIcon />
        </button>
        <button
          type="button"
          className={styles.iconButton}
          onClick={recording ? stopRecording : startRecording}
          disabled={uploading}
          title={recording ? t("messages.composer.stopRecording") : t("messages.composer.recordVoice")}
        >
          {recording ? <StopIcon /> : <MicIcon />}
        </button>

        <div className={styles.inputWrap}>
          {recording ? (
            <div className={styles.recordingIndicator}>{t("messages.composer.recording", { seconds: recordSeconds })}</div>
          ) : (
            <Textarea
              placeholder={t("messages.composer.placeholder")}
              value={content}
              onChange={(e) => handleContentChange(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              maxLength={4000}
              disabled={sending || uploading}
            />
          )}
        </div>

        <Button type="submit" loading={sending} disabled={!content.trim() || recording}>
          {sending ? t("messages.composer.sending") : t("messages.composer.send")}
        </Button>
      </form>
      {uploading ? <div className={styles.hint}>{t("messages.composer.uploading")}</div> : <div className={styles.hint}>{t("messages.composer.hint")}</div>}
    </div>
  );
}

