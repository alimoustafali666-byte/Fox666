"use client";

import { useTranslation } from "@/lib/i18n";
import type { DailyBriefPublic } from "@/lib/types";
import { CATEGORY_LABEL_KEYS, CATEGORY_ORDER, CATEGORY_TONE } from "./categories";
import styles from "./BriefStatsRow.module.css";

// Purely derived from the already-loaded brief.items -- no additional
// API calls and no fabricated metrics, per the Step 16 "only summary
// cards backed by data already available" constraint.
export function BriefStatsRow({ brief }: { brief: DailyBriefPublic }) {
  const { t } = useTranslation();

  const counts = CATEGORY_ORDER.map((category) => ({
    category,
    count: brief.items.filter((item) => item.category === category).length,
  }));

  if (counts.every((c) => c.count === 0)) return null;

  return (
    <div className={styles.row}>
      {counts.map(({ category, count }) => (
        <div key={category} className={styles.stat} data-tone={CATEGORY_TONE[category]}>
          <span className={styles.statBar} />
          <span className={styles.statCount}>{count}</span>
          <span className={styles.statLabel}>{t(CATEGORY_LABEL_KEYS[category])}</span>
        </div>
      ))}
    </div>
  );
}

