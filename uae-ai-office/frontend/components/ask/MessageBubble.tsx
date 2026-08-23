import Link from "next/link";
import clsx from "@/components/ui/clsx";
import { useTranslation } from "@/lib/i18n";
import type { MessagePublic } from "@/lib/types";
import { CitationChip } from "./CitationChip";
import styles from "./Thread.module.css";

export function MessageBubble({ message }: { message: MessagePublic }) {
  const { t } = useTranslation();

  if (message.role === "user") {
    return (
      <div className={clsx(styles.row, styles.rowUser)}>
        <div className={clsx(styles.bubble, styles.bubbleUser)}>{message.content}</div>
      </div>
    );
  }

  const insufficient = message.is_sufficient === false;

  return (
    <div className={clsx(styles.row, styles.rowAssistant)}>
      <div className={styles.assistantWrap}>
        <div className={clsx(styles.bubble, styles.bubbleAssistant, insufficient && styles.bubbleInsufficient)}>
          {message.content}
        </div>
        {message.citations.length > 0 ? (
          <div className={styles.citations}>
            {message.citations.map((citation) => (
              <CitationChip key={citation.document_chunk_id} citation={citation} />
            ))}
          </div>
        ) : null}
        <Link href={`/tasks/new?title=${encodeURIComponent(message.content.slice(0, 200))}`} className={styles.createTaskLink}>
          {t("ask.createTaskAction")}
        </Link>
      </div>
    </div>
  );
}

