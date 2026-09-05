"use client";

// Chart primitives for the dashboard. Hand-authored SVG rather than a chart
// dependency: the shapes needed here are small, every one of them is fed by a
// real series derived in ./metrics.ts, and theme-dependent colours are read
// from CSS variables so both themes stay correct without a second render.
//
// The empty states below are deliberately *designed* rather than blank -- but
// none of them plots a number. Where a visual has no data behind it, its
// geometry is fixed and decorative, and the copy says so.
import { useId } from "react";
import styles from "./DashboardOverview.module.css";

export const AI_SPECTRUM = ["#35d9f2", "#3b82f6", "#8b6bff", "#e05ad0", "#2fd48a"];

function smoothPath(values: number[], x: (i: number) => number, y: (v: number) => number): string {
  if (values.length === 0) return "";
  let path = `M ${x(0)} ${y(values[0])}`;
  for (let i = 1; i < values.length; i += 1) {
    const px = x(i - 1);
    const py = y(values[i - 1]);
    const cx = x(i);
    const cy = y(values[i]);
    const mx = px + (cx - px) / 2;
    path += ` C ${mx} ${py} ${mx} ${cy} ${cx} ${cy}`;
  }
  return path;
}

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

/**
 * Compact trend line. With no movement in the series it still draws a
 * luminous baseline with an end node, so a zero KPI reads as "measured, flat"
 * rather than as a blank card -- the baseline sits on zero, it is not a value.
 */
export function Sparkline({
  values,
  from,
  to,
  height = 44,
  strokeWidth = 2,
}: {
  values: number[];
  from: string;
  to: string;
  height?: number;
  strokeWidth?: number;
}) {
  const uid = useId().replace(/:/g, "");
  const width = 240;
  const pad = 6;
  const max = Math.max(...values, 0);
  const flat = max <= 0;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const y = (v: number) => (flat ? height - pad : height - pad - (v / max) * (height - pad * 2));
  const line = flat
    ? `M 0 ${height - pad} L ${width} ${height - pad}`
    : smoothPath(values, (i) => i * step, y);
  const area = `${line} L ${width} ${height} L 0 ${height} Z`;

  return (
    <svg
      className={styles.spark}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={`sparkStroke-${uid}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor={from} stopOpacity={flat ? 0.15 : 1} />
          <stop offset="1" stopColor={to} stopOpacity={flat ? 0.85 : 1} />
        </linearGradient>
        <linearGradient id={`sparkFill-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={to} stopOpacity={flat ? 0.16 : 0.32} />
          <stop offset="1" stopColor={to} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sparkFill-${uid})`} />
      <path
        d={line}
        fill="none"
        stroke={`url(#sparkStroke-${uid})`}
        strokeWidth={flat ? 1.6 : strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={flat ? "5 6" : undefined}
        vectorEffect="non-scaling-stroke"
      />
      {flat ? (
        <circle cx={width - 3} cy={height - pad} r="2.6" fill={to} vectorEffect="non-scaling-stroke" />
      ) : null}
    </svg>
  );
}

export interface RingSegment {
  value: number;
  from: string;
  to: string;
}

/**
 * Multicolour donut. Each segment's arc length is its real share of the total.
 * With no data it falls back to an evenly divided spectrum ring at low opacity
 * -- fixed geometry that plots nothing, paired with a "0 …" centre label.
 */
export function ProgressRing({
  segments,
  centerValue,
  centerLabel,
  size = 150,
  thickness,
  empty = false,
}: {
  segments: RingSegment[];
  centerValue: string;
  centerLabel: string;
  size?: number;
  thickness?: number;
  empty?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const stroke = thickness ?? size / 6.4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const total = segments.reduce((a, segment) => a + segment.value, 0);
  const gap = circumference * 0.012;

  let offset = 0;
  const arcs = empty
    ? AI_SPECTRUM.map((color, index) => {
        const length = circumference / AI_SPECTRUM.length - gap;
        const arc = (
          <circle
            key={index}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeOpacity="0.3"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${length} ${circumference - length}`}
            strokeDashoffset={-offset}
          />
        );
        offset += length + gap;
        return arc;
      })
    : segments.map((segment, index) => {
        if (total <= 0 || segment.value <= 0) return null;
        const length = (segment.value / total) * circumference;
        const arc = (
          <circle
            key={index}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={`url(#ringSeg-${uid}-${index})`}
            strokeWidth={stroke}
            strokeLinecap="butt"
            strokeDasharray={`${length} ${circumference - length}`}
            strokeDashoffset={-offset}
          />
        );
        offset += length;
        return arc;
      });

  return (
    <div className={styles.ringWrap} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
        <defs>
          {segments.map((segment, index) => (
            <linearGradient key={index} id={`ringSeg-${uid}-${index}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor={segment.from} />
              <stop offset="1" stopColor={segment.to} />
            </linearGradient>
          ))}
          <radialGradient id={`ringCore-${uid}`}>
            <stop offset="0" stopColor="#8b6bff" stopOpacity={empty ? 0.14 : 0.2} />
            <stop offset="1" stopColor="#8b6bff" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius - stroke} fill={`url(#ringCore-${uid})`} />
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {!empty ? (
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--ai-track)" strokeWidth={stroke} />
          ) : null}
          {arcs}
        </g>
      </svg>
      <div className={styles.ringCenter}>
        <strong>{centerValue}</strong>
        <span>{centerLabel}</span>
      </div>
    </div>
  );
}

/**
 * AI Business Pulse orb. `score` (0-100, real) drives the luminous progress
 * arc. Without a score the arc is replaced by a fixed spectrum orbit and the
 * "Building Intelligence" centre -- geometry only, no implied measurement.
 * The radar ticks and orbit rings are decorative in both states.
 */
export function PulseOrb({
  score,
  centerValue,
  centerLabel,
  size = 156,
}: {
  score: number | null;
  centerValue: string;
  centerLabel: string;
  size?: number;
}) {
  const uid = useId().replace(/:/g, "");
  const c = size / 2;
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = score === null ? 0 : (Math.max(0, Math.min(100, score)) / 100) * circumference;
  const orbit = radius - 14;
  const ticks = Array.from({ length: 36 }, (_, i) => i * 10);

  return (
    <div className={styles.ringWrap} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`orb-${uid}`} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#35d9f2" />
            <stop offset="0.34" stopColor="#3b82f6" />
            <stop offset="0.68" stopColor="#8b6bff" />
            <stop offset="1" stopColor="#e05ad0" />
          </linearGradient>
          <radialGradient id={`orbCore-${uid}`}>
            <stop offset="0" stopColor="#8b6bff" stopOpacity="0.32" />
            <stop offset="0.7" stopColor="#3b82f6" stopOpacity="0.1" />
            <stop offset="1" stopColor="#3b82f6" stopOpacity="0" />
          </radialGradient>
          <filter id={`orbGlow-${uid}`} x="-45%" y="-45%" width="190%" height="190%">
            <feGaussianBlur stdDeviation="5.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle cx={c} cy={c} r={orbit - 4} fill={`url(#orbCore-${uid})`} />

        {/* Radar ticks -- fixed decoration, identical in every state. */}
        <g stroke="var(--ai-track)" strokeWidth="1.4" strokeLinecap="round">
          {ticks.map((deg) => {
            const outer = polar(c, c, radius - stroke - 2, deg);
            const inner = polar(c, c, radius - stroke - (deg % 90 === 0 ? 9 : 5), deg);
            return <line key={deg} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} />;
          })}
        </g>

        <g transform={`rotate(-90 ${c} ${c})`}>
          {score === null ? (
            AI_SPECTRUM.slice(0, 4).map((color, index) => {
              const seg = circumference / 4 - circumference * 0.02;
              return (
                <circle
                  key={index}
                  cx={c}
                  cy={c}
                  r={radius}
                  fill="none"
                  stroke={color}
                  strokeOpacity="0.4"
                  strokeWidth={stroke}
                  strokeLinecap="round"
                  strokeDasharray={`${seg} ${circumference - seg}`}
                  strokeDashoffset={-(index * (circumference / 4))}
                />
              );
            })
          ) : (
            <>
              <circle cx={c} cy={c} r={radius} fill="none" stroke="var(--ai-track)" strokeWidth={stroke} />
              <circle
                cx={c}
                cy={c}
                r={radius}
                fill="none"
                stroke={`url(#orb-${uid})`}
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={`${filled} ${circumference - filled}`}
                filter={`url(#orbGlow-${uid})`}
              />
            </>
          )}

          <circle cx={c} cy={c} r={orbit} fill="none" stroke="var(--ai-track)" strokeWidth="1.3" strokeDasharray="2 8" />
          <circle
            cx={c}
            cy={c}
            r={orbit - 9}
            fill="none"
            stroke="#8b6bff"
            strokeOpacity="0.34"
            strokeWidth="1.3"
            strokeDasharray={`${(orbit - 9) * 2.1} ${(orbit - 9) * 6}`}
          />
        </g>
      </svg>
      <div className={styles.ringCenter}>
        <strong className={score === null ? styles.orbBuilding : styles.scoreValue}>{centerValue}</strong>
        <span>{centerLabel}</span>
      </div>
    </div>
  );
}

export interface AreaSeries {
  values: number[];
  from: string;
  to: string;
  label: string;
}

/** Multi-series line chart with a value axis, day labels and data points. */
export function AreaChart({ series, labels }: { series: AreaSeries[]; labels: string[] }) {
  const uid = useId().replace(/:/g, "");
  const width = 660;
  const height = 178;
  const padLeft = 30;
  const padRight = 8;
  const padBottom = 18;
  const padTop = 10;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padBottom - padTop;

  const rawMax = Math.max(1, ...series.flatMap((entry) => entry.values));
  const stepSize = Math.max(1, Math.ceil(rawMax / 4));
  const max = stepSize * 4;
  const ticks = [4, 3, 2, 1, 0].map((i) => i * stepSize);

  const count = Math.max(...series.map((entry) => entry.values.length), 1);
  const step = count > 1 ? plotWidth / (count - 1) : 0;
  const x = (i: number) => padLeft + i * step;
  const y = (v: number) => padTop + plotHeight - (v / max) * plotHeight;

  return (
    <div className={styles.chart}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <defs>
          {series.map((entry, index) => (
            <linearGradient key={`s${index}`} id={`areaStroke-${uid}-${index}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor={entry.from} />
              <stop offset="1" stopColor={entry.to} />
            </linearGradient>
          ))}
          {series.map((entry, index) => (
            <linearGradient key={`f${index}`} id={`areaFill-${uid}-${index}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={entry.to} stopOpacity="0.26" />
              <stop offset="1" stopColor={entry.to} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        <g stroke="var(--ai-track)" strokeWidth="1">
          {ticks.map((_, index) => (
            <line
              key={index}
              x1={padLeft}
              x2={width - padRight}
              y1={padTop + (index * plotHeight) / (ticks.length - 1)}
              y2={padTop + (index * plotHeight) / (ticks.length - 1)}
            />
          ))}
          {labels.map((_, index) => (
            <line
              key={`v${index}`}
              y1={padTop}
              y2={padTop + plotHeight}
              x1={padLeft + (index * plotWidth) / (labels.length - 1)}
              x2={padLeft + (index * plotWidth) / (labels.length - 1)}
              strokeDasharray="2 7"
            />
          ))}
        </g>
        <g fill="var(--ai-faint)" fontSize="9.5" fontFamily="IBM Plex Mono, monospace">
          {ticks.map((tick, index) => (
            <text key={index} x={padLeft - 6} y={padTop + (index * plotHeight) / (ticks.length - 1) + 3.5} textAnchor="end">
              {tick}
            </text>
          ))}
        </g>

        {series.map((entry, index) => (
          <path
            key={`area${index}`}
            d={`${smoothPath(entry.values, x, y)} L ${x(entry.values.length - 1)} ${padTop + plotHeight} L ${padLeft} ${padTop + plotHeight} Z`}
            fill={`url(#areaFill-${uid}-${index})`}
          />
        ))}
        {series.map((entry, index) => (
          <path
            key={`line${index}`}
            d={smoothPath(entry.values, x, y)}
            fill="none"
            stroke={`url(#areaStroke-${uid}-${index})`}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {series.map((entry, index) =>
          entry.values.map((value, i) =>
            i % 2 === 0 ? (
              <circle
                key={`p${index}-${i}`}
                cx={x(i)}
                cy={y(value)}
                r="2.6"
                fill="var(--ai-panel-solid)"
                stroke={entry.to}
                strokeWidth="1.8"
              />
            ) : null,
          ),
        )}
      </svg>
      <div className={styles.chartLabels}>
        {labels.map((label, index) => (
          <span key={index}>{label}</span>
        ))}
      </div>
    </div>
  );
}

/**
 * Analytics canvas before there is any history: the real grid, plus three
 * decorative gradient waves at low opacity. Carries no axis values and no
 * points, so it cannot be mistaken for a plotted series.
 */
export function AnalyticsInitCanvas() {
  const uid = useId().replace(/:/g, "");
  const waves = [
    { d: "M0 108 C 110 78, 190 126, 300 96 S 500 56, 660 88", color: "#3b82f6" },
    { d: "M0 128 C 120 104, 210 142, 330 118 S 520 84, 660 112", color: "#2fd48a" },
    { d: "M0 88 C 100 62, 200 104, 320 74 S 530 40, 660 68", color: "#8b6bff" },
  ];
  return (
    <svg
      className={styles.initCanvas}
      viewBox="0 0 660 168"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        {waves.map((wave, index) => (
          <linearGradient key={index} id={`init-${uid}-${index}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={wave.color} stopOpacity="0" />
            <stop offset="0.45" stopColor={wave.color} stopOpacity="0.55" />
            <stop offset="1" stopColor={wave.color} stopOpacity="0" />
          </linearGradient>
        ))}
        <linearGradient id={`initFill-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3b82f6" stopOpacity="0.12" />
          <stop offset="1" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g stroke="var(--ai-track)" strokeWidth="1">
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1="0" x2="660" y1={12 + i * 34} y2={12 + i * 34} />
        ))}
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <line key={`v${i}`} y1="12" y2="148" x1={i * 110} x2={i * 110} strokeDasharray="2 8" />
        ))}
      </g>
      <path d={`${waves[0].d} L 660 168 L 0 168 Z`} fill={`url(#initFill-${uid})`} />
      {waves.map((wave, index) => (
        <path
          key={index}
          d={wave.d}
          fill="none"
          stroke={`url(#init-${uid}-${index})`}
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="7 9"
        />
      ))}
    </svg>
  );
}

/** Horizontal meter with a luminous endpoint node. */
export function Meter({ value, from, to }: { value: number; from: string; to: string }) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div className={styles.meter} aria-hidden="true">
      <span style={{ width: `${width}%`, background: `linear-gradient(90deg, ${from}, ${to})` }}>
        <i style={{ background: to, boxShadow: `0 0 8px ${to}` }} />
      </span>
    </div>
  );
}

/** Designed stand-in for a metric with no backend source. */
export function MeterAwaiting() {
  return (
    <div className={styles.meterAwaiting} aria-hidden="true">
      <span />
    </div>
  );
}

/** Restrained row skeleton for list panels with nothing to list yet. */
export function RowsSkeleton() {
  return (
    <div className={styles.skeletonRows} aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}
