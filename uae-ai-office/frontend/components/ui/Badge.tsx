import type { ReactNode } from "react";
import clsx from "./clsx";
import styles from "./Badge.module.css";

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger" | "primary";

export function Badge({
  tone = "neutral",
  dot = false,
  children,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={clsx(styles.badge, styles[tone])}>
      {dot ? <span className={styles.dot} /> : null}
      {children}
    </span>
  );
}

