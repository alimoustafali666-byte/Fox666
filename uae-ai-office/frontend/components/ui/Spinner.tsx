"use client";

import { useTranslation } from "@/lib/i18n";
import clsx from "./clsx";
import styles from "./Spinner.module.css";

export function Spinner({ size = "md" }: { size?: "sm" | "md" }) {
  const { t } = useTranslation();
  return <span className={clsx(styles.spinner, styles[size])} role="status" aria-label={t("common.loadingAriaLabel")} />;
}

export function LoadingBlock({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div className={styles.center}>
      <Spinner />
      <span style={{ marginInlineStart: 10, color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        {label ?? t("common.loading")}
      </span>
    </div>
  );
}

