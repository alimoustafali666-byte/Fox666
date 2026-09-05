import type { ReactNode } from "react";
import Link from "next/link";
import type { BadgeTone } from "./Badge";
import styles from "./StatTile.module.css";

/**
 * A row of compact count tiles -- the shared version of the identical markup
 * that Tasks (TaskSummaryTiles) and Daily Brief (BriefStatsRow) each used to
 * carry. Both feed it real counts; this component never derives or invents a
 * value, it only renders what the caller passes.
 */
export function StatTileRow({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}

export function StatTile({
  count,
  label,
  tone = "primary",
  href,
}: {
  count: number;
  label: string;
  tone?: BadgeTone;
  /** When set the tile becomes a link; otherwise it renders as static. */
  href?: string;
}) {
  const inner = (
    <>
      <span className={styles.statBar} aria-hidden="true" />
      <span className={styles.statCount}>{count}</span>
      <span className={styles.statLabel}>{label}</span>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={styles.stat} data-tone={tone}>
        {inner}
      </Link>
    );
  }

  return (
    <div className={styles.stat} data-tone={tone}>
      {inner}
    </div>
  );
}
