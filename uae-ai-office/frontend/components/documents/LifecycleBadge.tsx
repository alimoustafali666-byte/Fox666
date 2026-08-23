"use client";

import { Badge } from "@/components/ui/Badge";
import { useTranslation } from "@/lib/i18n";
import type { DocumentPublic } from "@/lib/types";
import { getLifecycleInfo } from "./lifecycle";

export function LifecycleBadge({ document }: { document: DocumentPublic }) {
  const { t } = useTranslation();
  const info = getLifecycleInfo(document);
  return (
    <Badge tone={info.tone} dot>
      {t(info.labelKey)}
    </Badge>
  );
}

