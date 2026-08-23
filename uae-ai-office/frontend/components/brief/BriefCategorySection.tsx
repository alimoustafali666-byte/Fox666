"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { useTranslation } from "@/lib/i18n";
import type { BriefItemCategory, BriefItemPublic } from "@/lib/types";
import {
  CATEGORY_DESCRIPTION_KEYS,
  CATEGORY_LABEL_KEYS,
  CATEGORY_TONE,
  PRIORITY_LABEL_KEYS,
  PRIORITY_TONE,
} from "./categories";
import styles from "./BriefCategorySection.module.css";

export function BriefCategorySection({
  category,
  items,
}: {
  category: BriefItemCategory;
  items: BriefItemPublic[];
}) {
  const { t } = useTranslation();
  if (items.length === 0) return null;

  return (
    <div className={styles.section} data-tone={CATEGORY_TONE[category]}>
      <div className={styles.sectionHeader}>
        <span className={styles.sectionDot} />
        <span className={styles.sectionTitle}>{t(CATEGORY_LABEL_KEYS[category])}</span>
        <span className={styles.sectionCount}>({items.length})</span>
      </div>
      <div className={styles.sectionDescription}>{t(CATEGORY_DESCRIPTION_KEYS[category])}</div>
      <div className={styles.itemList}>
        {items.map((item) => (
          <div key={item.id} className={styles.item}>
            <div className={styles.itemText}>{item.text}</div>
            <div className={styles.itemMeta}>
              <Badge tone={PRIORITY_TONE[item.priority] ?? "neutral"}>
                {PRIORITY_LABEL_KEYS[item.priority]
                  ? t(PRIORITY_LABEL_KEYS[item.priority])
                  : t("brief.priorities.fallback", { n: item.priority })}
              </Badge>
              {item.source_document_id ? (
                <Link href={`/documents/${item.source_document_id}`} className={styles.sourceLink}>
                  {t("brief.viewSourceDocument")}
                </Link>
              ) : null}
              <Link
                href={`/tasks/new?title=${encodeURIComponent(item.text.slice(0, 200))}&source_type=daily_brief&source_id=${item.id}`}
                className={styles.sourceLink}
              >
                {t("brief.createTaskAction")}
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

