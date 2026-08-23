"use client";

import Link from "next/link";
import { useTranslation } from "@/lib/i18n";
import type { CitationPublic } from "@/lib/types";
import styles from "./Thread.module.css";

export function CitationChip({ citation }: { citation: CitationPublic }) {
  const { t } = useTranslation();

  // Renders only the safe, business-facing metadata the backend returns
  // (file name, document type, and page/sheet/section) -- never a
  // storage key, embedding vector, or signed URL; those are never part of
  // CitationPublic in the first place.
  function formatLocation(c: CitationPublic): string | null {
    if (c.page_number != null) return t("ask.citationPage", { n: c.page_number });
    if (c.sheet_name) return c.sheet_name;
    if (c.section_name) return c.section_name;
    return null;
  }

  const location = formatLocation(citation);
  return (
    <Link href={`/documents/${citation.document_id}`} className={styles.citationChip}>
      <svg width="11" height="11" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M5 2.5h5.5L13.5 5.5V15.5H5z" />
      </svg>
      {citation.file_name}
      {location ? ` · ${location}` : ""}
    </Link>
  );
}

