"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import clsx from "./clsx";
import { ChevronRightIcon } from "@/components/layout/icons";
import styles from "./Workspace.module.css";

/**
 * Workspace kit -- the dashboard's visual language, extracted.
 *
 * These are presentation primitives only: none of them fetch, derive, or
 * invent a value. Every number rendered here is passed in by a page that got
 * it from a real response, and every decorative element (the hero field, the
 * zero-state orbits) is fixed chrome that never encodes data.
 */

export type Accent = "cyan" | "blue" | "violet" | "magenta" | "green" | "amber";

function accentProps(accent: Accent = "blue") {
  return { className: styles.accent, "data-accent": accent };
}

/** Merges the accent class with a caller-supplied one. */
function withAccent(accent: Accent | undefined, ...extra: (string | false | undefined)[]) {
  return { className: clsx(styles.accent, ...extra), "data-accent": accent ?? "blue" };
}

// ── Layout ──────────────────────────────────────────────────────────────

/** Which product area this route belongs to. Drives only the decorative
 *  field geometry behind the hero, so each module is recognisable at a
 *  glance without leaving the one family palette. */
export type ModuleId =
  | "ask"
  | "messages"
  | "projects"
  | "tasks"
  | "brief"
  | "reports"
  | "documents"
  | "settings"
  | "support";

export function WorkspacePage({
  children,
  className,
  module: moduleId,
}: {
  children: ReactNode;
  className?: string;
  module?: ModuleId;
}) {
  return (
    <div className={clsx(styles.page, className)} data-module={moduleId}>
      {children}
    </div>
  );
}

/** Owns its own scrollbar -- for routes mounted in a fixed-height flex shell. */
export function WorkspaceScroller({ children, module: moduleId }: { children: ReactNode; module?: ModuleId }) {
  return (
    <div className={styles.scroller} data-module={moduleId}>
      <div className={styles.page}>{children}</div>
    </div>
  );
}

export function WorkspaceSplit({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <div className={wide ? styles.splitWide : styles.split}>{children}</div>;
}

export function WorkspaceColumn({ children }: { children: ReactNode }) {
  return <div className={styles.column}>{children}</div>;
}

// ── Hero ────────────────────────────────────────────────────────────────

export interface HeroMetric {
  label: string;
  /** Already-formatted -- the kit never computes or rounds a value. */
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
}

export function WorkspaceHero({
  accent = "blue",
  badge,
  icon,
  title,
  description,
  actions,
  side,
  metrics,
  compact = false,
}: {
  accent?: Accent;
  badge?: string;
  icon?: ReactNode;
  title: string;
  description?: string;
  actions?: ReactNode;
  side?: ReactNode;
  metrics?: HeroMetric[];
  /** Tighter band for a working route, where data should start higher. */
  compact?: boolean;
}) {
  return (
    <section {...withAccent(accent, styles.hero, compact && styles.heroCompact)}>
      <div className={styles.heroField} aria-hidden="true" />
      <div className={styles.heroTop}>
        <div className={styles.heroMain}>
          {badge ? (
            <span className={styles.heroBadge}>
              <i aria-hidden="true" />
              {badge}
            </span>
          ) : null}
          <div className={styles.heroHeading}>
            {icon ? <span className={styles.heroIcon}>{icon}</span> : null}
            <div>
              <h1>{title}</h1>
              {description ? <p className={styles.heroDescription}>{description}</p> : null}
            </div>
          </div>
          {actions ? <div className={styles.heroActions}>{actions}</div> : null}
        </div>
        {side ? <div className={styles.heroSide}>{side}</div> : null}
      </div>
      {metrics && metrics.length > 0 ? (
        <div className={styles.heroMetrics}>
          {metrics.map((metric) => (
            <div key={metric.label} className={styles.metric}>
              <div className={styles.metricLabel}>
                {metric.icon}
                {metric.label}
              </div>
              <div className={styles.metricValue}>{metric.value}</div>
              {metric.hint ? <div className={styles.metricHint}>{metric.hint}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

// ── Panel ───────────────────────────────────────────────────────────────

export function WorkspacePanel({
  accent = "blue",
  icon,
  title,
  subtitle,
  action,
  children,
  tight = false,
  className,
}: {
  accent?: Accent;
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  tight?: boolean;
  className?: string;
}) {
  return (
    <section {...withAccent(accent, styles.panel, className)}>
      <header className={styles.panelHead}>
        {icon ? <span className={styles.panelIcon}>{icon}</span> : null}
        <div className={styles.panelTitles}>
          <div className={styles.panelTitle}>{title}</div>
          {subtitle ? <div className={styles.panelSubtitle}>{subtitle}</div> : null}
        </div>
        {action ? <div className={styles.panelAction}>{action}</div> : null}
      </header>
      <div className={tight ? styles.panelBodyTight : styles.panelBody}>{children}</div>
    </section>
  );
}

export function SectionLabel({ title, aside }: { title: string; aside?: string }) {
  return (
    <div className={styles.sectionLabel}>
      <h2>{title}</h2>
      <span className={styles.sectionRule} aria-hidden="true" />
      {aside ? <span className={styles.sectionAside}>{aside}</span> : null}
    </div>
  );
}

// ── Feature / capability cards ──────────────────────────────────────────

export function CardGrid({ children, two = false }: { children: ReactNode; two?: boolean }) {
  return <div className={clsx(styles.cardGrid, two && styles.cardGridTwo)}>{children}</div>;
}

export function FeatureCard({
  accent = "blue",
  icon,
  title,
  description,
  meta,
  href,
  onClick,
}: {
  accent?: Accent;
  icon?: ReactNode;
  title: string;
  description: string;
  meta?: string;
  href?: string;
  /** Use instead of `href` when the card changes state on the current page
   *  rather than navigating -- a same-route query link would not remount. */
  onClick?: () => void;
}) {
  const body = (
    <>
      {icon ? <span className={styles.featureIcon}>{icon}</span> : null}
      <span className={styles.featureTitle}>{title}</span>
      <span className={styles.featureDescription}>{description}</span>
      {meta ? <span className={styles.featureMeta}>{meta}</span> : null}
    </>
  );

  if (href) {
    return (
      <Link href={href} {...withAccent(accent, styles.featureCard, styles.featureCardLink)}>
        {body}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} {...withAccent(accent, styles.featureCard, styles.featureCardLink)}>
        {body}
      </button>
    );
  }
  return <div {...withAccent(accent, styles.featureCard)}>{body}</div>;
}

// ── Prompt suggestions ──────────────────────────────────────────────────

export function PromptGrid({ children }: { children: ReactNode }) {
  return <div className={styles.promptGrid}>{children}</div>;
}

export function PromptCard({
  accent = "violet",
  tag,
  text,
  go,
  onClick,
  disabled,
}: {
  accent?: Accent;
  tag: string;
  text: string;
  go: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} {...withAccent(accent, styles.promptCard)}>
      <span className={styles.promptTag}>{tag}</span>
      <span className={styles.promptText}>{text}</span>
      <span className={styles.promptGo}>
        {go}
        <ChevronRightIcon />
      </span>
    </button>
  );
}

// ── Chips ───────────────────────────────────────────────────────────────

export function ChipRow({ children }: { children: ReactNode }) {
  return <div className={styles.chipRow}>{children}</div>;
}

export function ChipLink({
  accent = "blue",
  href,
  icon,
  children,
}: {
  accent?: Accent;
  href: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Link href={href} {...withAccent(accent, styles.chip)}>
      {icon}
      {children}
    </Link>
  );
}

export function ChipButton({
  accent = "blue",
  icon,
  onClick,
  disabled,
  children,
}: {
  accent?: Accent;
  icon?: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} {...withAccent(accent, styles.chip)}>
      {icon}
      {children}
    </button>
  );
}

// ── Step flow ───────────────────────────────────────────────────────────

export function StepFlow({
  accent = "cyan",
  steps,
}: {
  accent?: Accent;
  steps: { title: string; description: string }[];
}) {
  return (
    <div className={styles.steps}>
      {steps.map((step, index) => (
        <div key={step.title} {...withAccent(accent, styles.step)}>
          <span className={styles.stepNumber}>{index + 1}</span>
          <div className={styles.stepTitle}>{step.title}</div>
          <div className={styles.stepDescription}>{step.description}</div>
        </div>
      ))}
    </div>
  );
}

// ── Status framework legend ─────────────────────────────────────────────

export interface LegendItem {
  label: string;
  description: string;
  color: string;
  /** Real count from a loaded response, or undefined when nothing is known. */
  count?: number;
  /** Turns the row into a filter control for the list beside it. */
  onSelect?: () => void;
  active?: boolean;
}

/**
 * A distribution, not a glossary. The label carries the count and a bar whose
 * width is `count / total` -- both real numbers handed in by the caller, so
 * the bar is a rendering of the data rather than an illustration. The wordy
 * definition moves to the row's tooltip, where it is available on demand
 * without competing with the figures every day.
 */
export function StatusLegend({ items, total }: { items: LegendItem[]; total?: number }) {
  // Only ever a real denominator: the caller's own sum. Absent or zero means
  // there is nothing to be a proportion of, so no bar is drawn at all.
  const denominator = total && total > 0 ? total : 0;

  return (
    <div className={styles.legend}>
      {items.map((item) => {
        const share = denominator && item.count !== undefined ? item.count / denominator : 0;
        const body = (
          <>
            <span className={styles.legendDot} style={{ ["--legend-color" as string]: item.color }} aria-hidden="true" />
            <span className={styles.legendLabel}>{item.label}</span>
            <span className={styles.legendTrack} aria-hidden="true">
              <span
                className={styles.legendFill}
                style={{ width: `${Math.round(share * 100)}%`, ["--legend-color" as string]: item.color }}
              />
            </span>
            {item.count !== undefined ? (
              <span className={styles.legendCount} data-zero={item.count === 0}>
                {item.count}
              </span>
            ) : null}
          </>
        );

        if (item.onSelect) {
          return (
            <button
              key={item.label}
              type="button"
              className={styles.legendRow}
              data-active={item.active ? "true" : undefined}
              title={item.description}
              onClick={item.onSelect}
            >
              {body}
            </button>
          );
        }
        return (
          <div key={item.label} className={styles.legendRow} title={item.description}>
            {body}
          </div>
        );
      })}
    </div>
  );
}

// ── Compact info rows ───────────────────────────────────────────────────

export function InfoList({ children }: { children: ReactNode }) {
  return <div className={styles.infoList}>{children}</div>;
}

export function InfoRow({
  accent = "blue",
  icon,
  label,
  meta,
  value,
  href,
  onClick,
}: {
  accent?: Accent;
  icon?: ReactNode;
  label: string;
  meta?: string;
  value?: ReactNode;
  href?: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className={styles.infoRowMain}>
        {icon ? <span className={styles.infoRowIcon}>{icon}</span> : null}
        <span style={{ minWidth: 0 }}>
          <span className={styles.infoRowLabel} style={{ display: "block" }}>
            {label}
          </span>
          {meta ? <span className={styles.infoRowMeta}>{meta}</span> : null}
        </span>
      </span>
      {value !== undefined ? <span className={styles.infoRowValue}>{value}</span> : null}
    </>
  );

  if (href) {
    return (
      <Link href={href} {...withAccent(accent, styles.infoRow)}>
        {body}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        {...withAccent(accent, styles.infoRow)}
        style={{ width: "100%", background: "transparent", border: "none", cursor: "pointer", font: "inherit" }}
      >
        {body}
      </button>
    );
  }
  return <div {...withAccent(accent, styles.infoRow)}>{body}</div>;
}

// ── Quiet note ──────────────────────────────────────────────────────────

export function WorkspaceNote({
  accent = "cyan",
  icon,
  children,
}: {
  accent?: Accent;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div {...withAccent(accent, styles.note)}>
      {icon}
      <span>{children}</span>
    </div>
  );
}

// ── Designed zero-data block ────────────────────────────────────────────

export function ZeroState({
  accent = "violet",
  icon,
  title,
  text,
  actions,
}: {
  accent?: Accent;
  icon: ReactNode;
  title: string;
  text?: string;
  actions?: ReactNode;
}) {
  return (
    <div {...withAccent(accent, styles.zero)}>
      <span className={styles.zeroVisual} aria-hidden="true">
        {icon}
      </span>
      <div className={styles.zeroTitle}>{title}</div>
      {text ? <div className={styles.zeroText}>{text}</div> : null}
      {actions ? <div className={styles.zeroActions}>{actions}</div> : null}
    </div>
  );
}

// ── Loading rows ────────────────────────────────────────────────────────

export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div className={styles.skeletonRows} aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={clsx(styles.skeletonRow, "uae-skeleton")} />
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Polish primitives
//
// Added so a route is not a stack of identical rectangles. Same contract as
// everything above: presentation only. A caller passes values it already got
// from a real response; nothing here computes, rounds or invents one.
// ══════════════════════════════════════════════════════════════════════

// ── Stat strip ──────────────────────────────────────────────────────────

export interface StatItem {
  label: string;
  /** Already-formatted by the caller. */
  value: ReactNode;
  icon?: ReactNode;
  /** Greys the value when the caller knows it is a true zero. */
  zero?: boolean;
}

/** A rule of numbers rather than a row of boxes. */
export function StatStrip({ accent = "blue", items }: { accent?: Accent; items: StatItem[] }) {
  return (
    <div {...withAccent(accent, styles.statStrip)}>
      {items.map((item) => (
        <div key={item.label} className={styles.stat}>
          <div className={styles.statLabel}>
            {item.icon}
            {item.label}
          </div>
          <div className={styles.statValue} data-zero={item.zero ? "true" : undefined}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Progressive disclosure ──────────────────────────────────────────────

/** Demotes explanatory content behind one quiet line. Native <details>, so
 *  it stays keyboard-operable and find-in-page searchable when closed. */
export function Disclosure({
  accent = "blue",
  icon,
  label,
  defaultOpen = false,
  children,
}: {
  accent?: Accent;
  icon?: ReactNode;
  label: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details {...withAccent(accent, styles.disclosure)} open={defaultOpen}>
      <summary className={styles.disclosureSummary}>
        {icon}
        {label}
        <span className={styles.disclosureChevron} aria-hidden="true">
          <ChevronRightIcon />
        </span>
      </summary>
      <div className={styles.disclosureBody}>{children}</div>
    </details>
  );
}

// ── Compact capability rows ─────────────────────────────────────────────

export interface PointItem {
  icon?: ReactNode;
  title: string;
  text: string;
}

/** The quiet form of a capability grid, for use inside a Disclosure. */
export function PointList({ accent = "blue", items }: { accent?: Accent; items: PointItem[] }) {
  return (
    <div {...withAccent(accent, styles.pointList)}>
      {items.map((item) => (
        <div key={item.title} className={styles.point}>
          {item.icon ? <span className={styles.pointIcon}>{item.icon}</span> : null}
          <div style={{ minWidth: 0 }}>
            <div className={styles.pointTitle}>{item.title}</div>
            <div className={styles.pointText}>{item.text}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Inline numbered steps ───────────────────────────────────────────────

/** The flattened StepFlow: one line per step instead of four boxes. */
export function StepList({
  accent = "cyan",
  steps,
}: {
  accent?: Accent;
  steps: { title: string; description: string }[];
}) {
  return (
    <div {...withAccent(accent, styles.stepList)}>
      {steps.map((step, index) => (
        <div key={step.title} className={styles.stepRow}>
          <span className={styles.stepRowNum}>{index + 1}</span>
          <span className={styles.stepRowText}>
            <b>{step.title}.</b> {step.description}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Timeline ────────────────────────────────────────────────────────────

export function Timeline({ accent = "blue", children }: { accent?: Accent; children: ReactNode }) {
  return <div {...withAccent(accent, styles.timeline)}>{children}</div>;
}

export function TimelineItem({ line, meta }: { line: ReactNode; meta?: string }) {
  return (
    <div className={styles.timelineItem}>
      <div className={styles.timelineLine}>{line}</div>
      {meta ? <div className={styles.timelineMeta}>{meta}</div> : null}
    </div>
  );
}

// ── Segmented control ───────────────────────────────────────────────────

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
  /** Real count from a loaded response, or undefined when nothing is known. */
  count?: number;
}

export function Segmented<T extends string>({
  accent = "blue",
  options,
  value,
  onChange,
  ariaLabel,
}: {
  accent?: Accent;
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div {...withAccent(accent, styles.segmented)} role="tablist" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          data-active={option.value === value}
          className={styles.segment}
          onClick={() => onChange(option.value)}
        >
          {option.icon}
          {option.label}
          {option.count !== undefined ? <span className={styles.segmentCount}>{option.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

// ── Launch box ──────────────────────────────────────────────────────────

/** A real input as the primary affordance. The caller owns the value and the
 *  submit -- this only supplies the shape, so nothing is sent until the
 *  person presses the button or Enter. */
export function LaunchBox({
  accent = "violet",
  icon,
  value,
  onChange,
  onSubmit,
  placeholder,
  action,
  disabled,
  ariaLabel,
}: {
  accent?: Accent;
  icon?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  action: ReactNode;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  return (
    <form
      {...withAccent(accent, styles.launch)}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {icon ? (
        <span className={styles.launchIcon} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <input
        className={styles.launchInput}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={ariaLabel ?? placeholder}
      />
      {action}
    </form>
  );
}

// ── Meta grid ───────────────────────────────────────────────────────────

export function MetaGrid({ children }: { children: ReactNode }) {
  return <div className={styles.metaGrid}>{children}</div>;
}

export function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.metaItem}>
      <div className={styles.metaKey}>{label}</div>
      <div className={styles.metaVal}>{children}</div>
    </div>
  );
}

export { accentProps };
