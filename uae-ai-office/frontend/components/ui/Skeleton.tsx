"use client";

import { useTranslation } from "@/lib/i18n";
import clsx from "./clsx";
import styles from "./Skeleton.module.css";

// Shaped loading placeholders -- used where a bare spinner would leave the
// incoming layout unpredictable (list rows, KPI tiles, cards). Purely
// visual: never gates data-readiness logic, so it carries no risk to any
// loading/error state a page already implements.
export function Skeleton({ width, height, radius, className }: { width?: string | number; height?: string | number; radius?: string; className?: string }) {
  return (
    <span
      className={clsx("uae-skeleton", styles.block, className)}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonRows({ rows = 3, className }: { rows?: number; className?: string }) {
  const { t } = useTranslation();
  return (
    <div className={clsx(styles.rows, className)} role="status" aria-label={t("common.loadingAriaLabel")}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={14} radius="var(--radius-sm)" />
      ))}
    </div>
  );
}

