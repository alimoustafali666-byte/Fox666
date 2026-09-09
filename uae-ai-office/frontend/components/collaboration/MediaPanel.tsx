"use client";

import { useEffect, useState } from "react";
import { collaborationApi } from "@/lib/api-client";
import { errorMessage } from "@/lib/auth-context";
import { formatDate, useTranslation } from "@/lib/i18n";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingBlock } from "@/components/ui/Spinner";
import { CloseIcon, PaperclipIcon } from "@/components/layout/icons";
import type { AttachmentKind, AttachmentPublic } from "@/lib/types";
import styles from "./ThreadToolPanel.module.css";

type Filter = "all" | AttachmentKind;

const FILTERS: { key: Filter; labelKey: Parameters<ReturnType<typeof useTranslation>["t"]>[0] }[] = [
  { key: "all", labelKey: "messages.media.filterAll" },
  { key: "image", labelKey: "messages.media.filterImage" },
  { key: "voice_note", labelKey: "messages.media.filterVoiceNote" },
  { key: "file", labelKey: "messages.media.filterFile" },
];

/** One attachment's signed URL, fetched on demand. Signed URLs are
 *  short-lived, so they are resolved per render of this panel rather
 *  than cached with the attachment list. */
function MediaTile({ attachment }: { attachment: AttachmentPublic }) {
  const { t, locale } = useTranslation();
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    collaborationApi
      .getAttachmentDownloadUrl(attachment.id)
      .then((res) => {
        if (!cancelled) setUrl(res.url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [attachment.id]);

  if (attachment.kind === "image") {
    return (
      <a
        className={styles.mediaCell}
        href={url ?? undefined}
        target="_blank"
        rel="noreferrer"
        title={attachment.file_name}
      >
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={attachment.file_name} style={{ width: "100%", borderRadius: "var(--radius-sm)" }} />
        ) : null}
        <span className={styles.mediaName}>{attachment.file_name}</span>
      </a>
    );
  }

  if (attachment.kind === "voice_note") {
    return (
      <div className={styles.mediaCell} style={{ gridColumn: "1 / -1" }}>
        {url ? <audio controls src={url} style={{ width: "100%" }} /> : null}
        <span className={styles.mediaName}>
          {attachment.file_name} · {formatDate(locale, attachment.created_at)}
        </span>
      </div>
    );
  }

  return (
    <a
      className={styles.fileRow}
      style={{ gridColumn: "1 / -1" }}
      href={url ?? undefined}
      target="_blank"
      rel="noreferrer"
    >
      <PaperclipIcon width={13} height={13} />
      <span className={styles.fileName}>{attachment.file_name}</span>
      <span className={styles.mediaName}>{url ? t("messages.media.download") : t("common.loading")}</span>
    </a>
  );
}

/** Everything shared in one conversation, filterable by kind. Backed by
 *  GET /collaboration/conversations/{id}/media, which returns newest
 *  first and is already scoped to the caller's membership. */
export function MediaPanel({ conversationId, onClose }: { conversationId: string; onClose: () => void }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<AttachmentPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    collaborationApi
      .listConversationMedia(conversationId, filter === "all" ? undefined : { kind: filter })
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err, t("messages.media.genericError")));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, filter]);

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.title}>{t("messages.media.panelTitle")}</div>
        <button type="button" className={styles.closeButton} onClick={onClose} aria-label={t("common.close")}>
          <CloseIcon width={14} height={14} />
        </button>
      </div>
      <div className={styles.hint}>{t("messages.media.panelHint")}</div>

      <div className={styles.filterRow}>
        {FILTERS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            className={styles.filterChip}
            aria-pressed={filter === entry.key}
            onClick={() => setFilter(entry.key)}
          >
            {t(entry.labelKey)}
          </button>
        ))}
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      {loading ? (
        <LoadingBlock label={t("common.loading")} />
      ) : items.length === 0 ? (
        <p className={styles.emptyText}>{t("messages.media.empty")}</p>
      ) : (
        <div className={styles.mediaGrid}>
          {items.map((attachment) => (
            <MediaTile key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}
    </aside>
  );
}
