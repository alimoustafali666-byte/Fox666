import type { ReactNode } from "react";
import styles from "./EmptyState.module.css";

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  /** Optional glyph shown above the title in a soft gradient circle -- gives an otherwise-bare empty state a bit of product identity. */
  icon?: ReactNode;
}) {
  return (
    <div className={styles.wrap}>
      {icon ? <div className={styles.icon}>{icon}</div> : null}
      <div className={styles.title}>{title}</div>
      {description ? <div className={styles.description}>{description}</div> : null}
      {action ? <div className={styles.actions}>{action}</div> : null}
    </div>
  );
}

