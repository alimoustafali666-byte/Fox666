"use client";

import { useTranslation } from "@/lib/i18n";
import type { DailyBriefPublic } from "@/lib/types";
import { StatTile, StatTileRow } from "@/components/ui/StatTile";
import { CATEGORY_LABEL_KEYS, CATEGORY_ORDER, CATEGORY_TONE } from "./categories";

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
    <StatTileRow>
      {counts.map(({ category, count }) => (
        <StatTile
          key={category}
          tone={CATEGORY_TONE[category]}
          count={count}
          label={t(CATEGORY_LABEL_KEYS[category])}
        />
      ))}
    </StatTileRow>
  );
}
