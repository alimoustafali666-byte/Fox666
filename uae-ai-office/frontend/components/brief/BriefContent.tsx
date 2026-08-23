"use client";

import { EmptyState } from "@/components/ui/EmptyState";
import { useTranslation } from "@/lib/i18n";
import type { DailyBriefPublic } from "@/lib/types";
import { BriefCategorySection } from "./BriefCategorySection";
import { CATEGORY_ORDER } from "./categories";

export function BriefContent({ brief }: { brief: DailyBriefPublic }) {
  const { t } = useTranslation();

  if (brief.items.length === 0) {
    return (
      <EmptyState
        title={t("brief.nothingToReportTitle")}
        description={brief.summary || t("brief.nothingToReportDescription")}
      />
    );
  }

  return (
    <div>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-5)" }}>
        {brief.summary}
      </p>
      {CATEGORY_ORDER.map((category) => (
        <BriefCategorySection
          key={category}
          category={category}
          items={brief.items.filter((item) => item.category === category)}
        />
      ))}
    </div>
  );
}

