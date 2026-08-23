"use client";

import { useEffect, useState } from "react";
import { collaborationApi } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import type { AttachmentPublic } from "@/lib/types";
import styles from "./MessageRow.module.css";

export function AttachmentView({ attachment }: { attachment: AttachmentPublic }) {
  const { t } = useTranslation();
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
    return url ? (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt={attachment.file_name} className={styles.attachmentImage} />
    ) : (
      <div className={styles.attachmentPlaceholder}>{attachment.file_name}</div>
    );
  }

  if (attachment.kind === "voice_note") {
    return url ? (
      <audio controls src={url} className={styles.attachmentAudio} />
    ) : (
      <div className={styles.attachmentPlaceholder}>{attachment.file_name}</div>
    );
  }

  return (
    <a href={url ?? undefined} className={styles.attachmentFile} target="_blank" rel="noreferrer">
      📎 {attachment.file_name}
      {!url ? ` (${t("common.loading")})` : ""}
    </a>
  );
}

