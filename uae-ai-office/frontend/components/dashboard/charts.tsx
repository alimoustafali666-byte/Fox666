"use client";

// Chart primitives for the dashboard. Hand-authored SVG rather than a chart
// dependency: the shapes needed here are small and every one of them is fed
// by a real series derived in ./metrics.ts.
import { useId } from "react";
import styles from "./DashboardOverview.module.css";

function smoothPath(values: number[], width: number, height: number, pad: number): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const x = (i: number) => i * step;
  const y = (v: number) => height - pad - (v / max) * (height - pad * 2);

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

/** Compact trend line for a KPI card or a performance row. */
export function Sparkline({
  values,
  from,
  to,
  height = 40,
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
  const line = smoothPath(values, width, height, 4);
  if (!line) return null;
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
          <stop offset="0" stopColor={from} />
          <stop offset="1" stopColor={to} />
        </linearGradient>
        <linearGradient id={`sparkFill-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={to} stopOpacity="0.34" />
          <stop offset="1" stopColor={to} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sparkFill-${uid})`} />
      <path
        d={line}
        fill="none"
        stroke={`url(#sparkStroke-${uid})`}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export interface RingSegment {
  value: number;
  from: string;
  to: string;
}

/**
 * Multicolour progress ring. Each segment is drawn as an arc whose length is
 * its real share of the total -- no minimum sweep, so a zero never shows.
 */
export function ProgressRing({
  segments,
  centerValue,
  centerLabel,
  size = 168,
}: {
  segments: RingSegment[];
  centerValue: string;
  centerLabel: string;
  size?: number;
}) {
  const uid = useId().replace(/:/g, "");
  const stroke = size / 8.5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const total = segments.reduce((a, segment) => a + segment.value, 0);

  let offset = 0;
  const arcs = segments.map((segment, index) => {
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
          <filter id={`ringGlow-${uid}`} x="-25%" y="-25%" width="150%" height="150%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(126, 166, 236, 0.11)"
            strokeWidth={stroke}
          />
          <g filter={`url(#ringGlow-${uid})`}>{arcs}</g>
        </g>
      </svg>
      <div className={styles.ringCenter}>
        <strong>{centerValue}</strong>
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

/** Multi-series area chart with a value axis and day labels. */
export function AreaChart({
  series,
  labels,
}: {
  series: AreaSeries[];
  labels: string[];
}) {
  const uid = useId().replace(/:/g, "");
  const width = 640;
  const height = 190;
  const padLeft = 34;
  const padBottom = 22;
  const plotWidth = width - padLeft - 8;
  const plotHeight = height - padBottom - 10;

  const max = Math.max(1, ...series.flatMap((entry) => entry.values));
  const ticks = [max, Math.round(max * 0.66), Math.round(max * 0.33), 0];
  const count = Math.max(...series.map((entry) => entry.values.length), 1);
  const step = count > 1 ? plotWidth / (count - 1) : 0;

  const toPath = (values: number[]) => {
    const x = (i: number) => padLeft + i * step;
    const y = (v: number) => 10 + plotHeight - (v / max) * plotHeight;
    let path = `M ${x(0)} ${y(values[0] ?? 0)}`;
    for (let i = 1; i < values.length; i += 1) {
      const px = x(i - 1);
      const py = y(values[i - 1]);
      const cx = x(i);
      const cy = y(values[i]);
      const mx = px + (cx - px) / 2;
      path += ` C ${mx} ${py} ${mx} ${cy} ${cx} ${cy}`;
    }
    return path;
  };

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
              <stop offset="0" stopColor={entry.to} stopOpacity="0.3" />
              <stop offset="1" stopColor={entry.to} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        <g stroke="rgba(126, 166, 236, 0.1)" strokeWidth="1" strokeDasharray="3 6">
          {ticks.map((_, index) => (
            <line
              key={index}
              x1={padLeft}
              x2={width - 8}
              y1={10 + (index * plotHeight) / (ticks.length - 1)}
              y2={10 + (index * plotHeight) / (ticks.length - 1)}
            />
          ))}
        </g>
        <g fill="#4e5d79" fontSize="9.5" fontFamily="IBM Plex Mono, monospace">
          {ticks.map((tick, index) => (
            <text key={index} x={padLeft - 7} y={14 + (index * plotHeight) / (ticks.length - 1)} textAnchor="end">
              {tick}
            </text>
          ))}
        </g>

        {series.map((entry, index) => (
          <path
            key={`area${index}`}
            d={`${toPath(entry.values)} L ${padLeft + (entry.values.length - 1) * step} ${10 + plotHeight} L ${padLeft} ${10 + plotHeight} Z`}
            fill={`url(#areaFill-${uid}-${index})`}
          />
        ))}
        {series.map((entry, index) => (
          <path
            key={`line${index}`}
            d={toPath(entry.values)}
            fill="none"
            stroke={`url(#areaStroke-${uid}-${index})`}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className={styles.chartLabels}>
        {labels.map((label, index) => (
          <span key={index}>{label}</span>
        ))}
      </div>
    </div>
  );
}

/** Horizontal meter used by the status/workload/growth panels. */
export function Meter({ value, from, to }: { value: number; from: string; to: string }) {
  return (
    <div className={styles.meter} aria-hidden="true">
      <span
        style={{
          width: `${Math.max(0, Math.min(100, value))}%`,
          background: `linear-gradient(90deg, ${from}, ${to})`,
        }}
      />
    </div>
  );
}
