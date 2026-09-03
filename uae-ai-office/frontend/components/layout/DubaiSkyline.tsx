// Subtle Dubai skyline atmosphere for the dashboard's upper area.
//
// Deliberately NOT a literal illustration: it is a low-contrast horizon of
// slender light columns with a supertall spire, a soft Museum-of-the-Future
// arc and a horizon bloom, all sitting far behind the content at low opacity
// and masked out before it reaches the KPI row. Hand-authored SVG rather than
// an image so it stays crisp at any width, costs no network request, and
// carries no text -- it never needs mirroring or translation, so it is safe
// in both LTR and RTL. Purely decorative: aria-hidden, pointer-events:none.
import { useId } from "react";

// Slender light columns -- x, width, height (from the 320 baseline).
const COLUMNS: [number, number, number][] = [
  [40, 14, 84], [62, 9, 52], [78, 18, 118], [104, 10, 66], [122, 13, 96],
  [146, 8, 44], [162, 16, 134], [188, 11, 74], [210, 9, 108], [228, 14, 58],
  [268, 12, 92], [288, 9, 56], [306, 15, 126], [330, 10, 70], [352, 13, 100],
  [376, 8, 48], [396, 17, 142], [422, 10, 78], [444, 12, 104], [470, 9, 60],
  [508, 14, 88], [530, 10, 122], [552, 8, 50], [570, 16, 138], [596, 11, 72],
  [618, 13, 98], [644, 9, 54], [662, 15, 116], [688, 10, 68], [710, 12, 92],
  [748, 9, 46], [766, 16, 130], [792, 11, 80], [814, 13, 106], [840, 8, 52],
  [860, 14, 94], [884, 10, 64], [906, 17, 136], [934, 9, 56], [952, 12, 88],
  [990, 13, 110], [1014, 9, 50], [1032, 15, 124], [1058, 11, 76], [1080, 12, 98],
  [1106, 8, 46], [1124, 16, 132], [1150, 10, 70], [1172, 13, 102], [1198, 9, 58],
  [1232, 14, 90], [1256, 10, 118], [1278, 8, 48], [1296, 15, 128], [1322, 11, 74],
  [1344, 12, 96], [1370, 9, 52],
];

export function DubaiSkyline({ className }: { className?: string }) {
  // useId keeps the gradient/filter ids unique if more than one instance is
  // ever mounted, so neither steals the other's fills.
  const uid = useId().replace(/:/g, "");
  const column = `sky-col-${uid}`;
  const spire = `sky-spire-${uid}`;
  const haze = `sky-haze-${uid}`;
  const arc = `sky-arc-${uid}`;
  const soft = `sky-soft-${uid}`;

  return (
    <svg
      className={className}
      viewBox="0 0 1400 320"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={column} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7fb6ff" stopOpacity="0.55" />
          <stop offset="0.5" stopColor="#4d6cff" stopOpacity="0.22" />
          <stop offset="1" stopColor="#0a1338" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={spire} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bfe6ff" stopOpacity="0.8" />
          <stop offset="0.55" stopColor="#6f8dff" stopOpacity="0.3" />
          <stop offset="1" stopColor="#0a1338" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={haze} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6d4dff" stopOpacity="0" />
          <stop offset="0.6" stopColor="#3b3ec0" stopOpacity="0.16" />
          <stop offset="1" stopColor="#101a52" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id={arc} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#35d9f2" stopOpacity="0.5" />
          <stop offset="0.55" stopColor="#8b6bff" stopOpacity="0.42" />
          <stop offset="1" stopColor="#e05ad0" stopOpacity="0.36" />
        </linearGradient>
        <filter id={soft} x="-30%" y="-60%" width="160%" height="220%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>

      <rect width="1400" height="320" fill={`url(#${haze})`} />

      {/* Horizon bloom -- the city glow, not a drawn object. */}
      <ellipse cx="700" cy="318" rx="620" ry="54" fill="#4d8dff" opacity="0.16" filter={`url(#${soft})`} />
      <ellipse cx="470" cy="316" rx="180" ry="30" fill="#8b6bff" opacity="0.14" filter={`url(#${soft})`} />

      {/* Museum-of-the-Future arc, reduced to a luminous ellipse outline. */}
      <g transform="rotate(-12 470 268)" opacity="0.5">
        <ellipse cx="470" cy="268" rx="86" ry="58" fill="none" stroke={`url(#${arc})`} strokeWidth="6" />
      </g>

      <g fill={`url(#${column})`}>
        {COLUMNS.map(([x, w, h], i) => (
          <rect key={i} x={x} y={320 - h} width={w} height={h} rx={w / 3} />
        ))}
      </g>

      {/* The supertall spire anchoring the skyline's centre-left. */}
      <g>
        <path d="M694 44 h5 l3 60 h-11 z" fill={`url(#${spire})`} />
        <path d="M688 104 h17 l4 62 h-25 z" fill={`url(#${spire})`} />
        <path d="M680 166 h33 l5 68 h-43 z" fill={`url(#${spire})`} />
        <path d="M670 234 h53 l6 86 h-65 z" fill={`url(#${spire})`} />
        <circle cx="696.5" cy="40" r="2.4" fill="#bfe6ff" opacity="0.9" />
      </g>

      {/* Waterline reflection -- a single soft band, no drawn ripples. */}
      <rect x="0" y="304" width="1400" height="16" fill="#35d9f2" opacity="0.07" filter={`url(#${soft})`} />
    </svg>
  );
}
