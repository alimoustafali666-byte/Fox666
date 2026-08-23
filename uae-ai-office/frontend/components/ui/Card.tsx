import type { ReactNode } from "react";
import clsx from "./clsx";
import styles from "./Card.module.css";

export function Card({
  children,
  className,
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  /** Adds a subtle hover lift + border tint -- for cards that are themselves a click target (e.g. wrapped in a Link). */
  interactive?: boolean;
}) {
  return <div className={clsx(styles.card, interactive && styles.interactive, className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  actions,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** Optional small icon chip shown before the title -- see .iconChip tones in Card.module.css. */
  icon?: ReactNode;
}) {
  return (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        {icon ? <span className={styles.iconChip}>{icon}</span> : null}
        <div>
          <div className={styles.title}>{title}</div>
          {subtitle ? <div className={styles.subtitle}>{subtitle}</div> : null}
        </div>
      </div>
      {actions ? <div>{actions}</div> : null}
    </div>
  );
}

export function CardBody({ children, tight = false }: { children: ReactNode; tight?: boolean }) {
  return <div className={tight ? styles.bodyTight : styles.body}>{children}</div>;
}

