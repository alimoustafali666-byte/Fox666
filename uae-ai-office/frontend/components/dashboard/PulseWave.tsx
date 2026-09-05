// The flowing signal field behind the greeting band in the approved master.
//
// Abstract by design: interleaved smooth waves and a sparse particle drift,
// not an illustration of anything. Hand-authored SVG so it stays crisp at any
// width, costs no network request, carries no text (safe in LTR and RTL), and
// is never a screenshot or image overlay. Purely decorative: aria-hidden and
// pointer-events:none at the call site.
import { useId } from "react";

// Deterministic pseudo-random particle field -- a fixed seed keeps the layout
// identical between server and client renders.
function particles(count: number) {
  const points: { x: number; y: number; r: number; o: number }[] = [];
  let seed = 20260903;
  const next = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  for (let i = 0; i < count; i += 1) {
    const x = next() * 1200;
    const drift = Math.sin((x / 1200) * Math.PI * 1.6) * 26;
    points.push({
      x,
      y: 60 + drift + (next() - 0.5) * 54,
      r: 0.7 + next() * 1.5,
      o: 0.2 + next() * 0.6,
    });
  }
  return points;
}

const WAVES = [
  { d: "M0 74 C 180 30, 320 104, 500 62 S 840 8, 1010 56 S 1140 92, 1200 66", w: 1.6, o: 0.85 },
  { d: "M0 86 C 190 52, 340 116, 520 78 S 860 30, 1030 70 S 1150 100, 1200 80", w: 1.2, o: 0.6 },
  { d: "M0 62 C 170 22, 330 90, 480 46 S 820 -4, 990 40 S 1130 80, 1200 52", w: 1, o: 0.4 },
  { d: "M0 98 C 200 70, 360 126, 540 94 S 880 52, 1050 86 S 1160 108, 1200 94", w: 0.9, o: 0.3 },
];

export function PulseWave({ className }: { className?: string }) {
  // useId keeps the gradient ids unique if more than one instance mounts.
  const uid = useId().replace(/:/g, "");
  const stroke = `wave-stroke-${uid}`;
  const dot = `wave-dot-${uid}`;
  const fade = `wave-fade-${uid}`;

  return (
    <svg
      className={className}
      viewBox="0 0 1200 150"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={stroke} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#35d9f2" stopOpacity="0" />
          <stop offset="0.18" stopColor="#35d9f2" />
          <stop offset="0.52" stopColor="#4d8dff" />
          <stop offset="0.78" stopColor="#8b6bff" />
          <stop offset="1" stopColor="#e05ad0" stopOpacity="0.15" />
        </linearGradient>
        <radialGradient id={dot}>
          <stop offset="0" stopColor="#9fd8ff" />
          <stop offset="1" stopColor="#9fd8ff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={fade} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="0.28" stopColor="#ffffff" />
          <stop offset="0.85" stopColor="#ffffff" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <mask id={`wave-mask-${uid}`}>
          <rect width="1200" height="150" fill={`url(#${fade})`} />
        </mask>
      </defs>

      <g mask={`url(#wave-mask-${uid})`}>
        {WAVES.map((wave, index) => (
          <path
            key={index}
            d={wave.d}
            fill="none"
            stroke={`url(#${stroke})`}
            strokeWidth={wave.w}
            strokeOpacity={wave.o}
            strokeLinecap="round"
          />
        ))}
        <g>
          {particles(90).map((point, index) => (
            <circle key={index} cx={point.x} cy={point.y} r={point.r} fill={`url(#${dot})`} opacity={point.o} />
          ))}
        </g>
      </g>
    </svg>
  );
}
