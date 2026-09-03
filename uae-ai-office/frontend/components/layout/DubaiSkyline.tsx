// Dubai skyline atmosphere for the approved dashboard design: Burj Khalifa
// (drawn with its real stepped setbacks), the Museum of the Future torus, and
// a Burj Al Arab sail, over a low-rise block cluster and a water bloom.
//
// Hand-authored SVG rather than an image so it stays crisp at any width, adds
// no network request, and carries no text -- it never needs mirroring or
// translation, so it is safe in both LTR and RTL. Purely decorative: it is
// aria-hidden and pointer-events:none at the call site.
import { useId } from "react";

export type SkylineVariant = "panorama" | "sidebar";

export function DubaiSkyline({ variant, className }: { variant: SkylineVariant; className?: string }) {
  // useId keeps the gradient/filter ids unique when the panorama and the
  // sidebar crop are both mounted at once, so neither steals the other's fills.
  const uid = useId().replace(/:/g, "");
  const tower = `sky-tower-${uid}`;
  const block = `sky-block-${uid}`;
  const haze = `sky-haze-${uid}`;
  const motf = `sky-motf-${uid}`;
  const soft = `sky-soft-${uid}`;
  const soft2 = `sky-soft2-${uid}`;

  const defs = (
    <defs>
      <linearGradient id={tower} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#a8ddff" stopOpacity="0.9" />
        <stop offset="0.42" stopColor="#5f8cff" stopOpacity="0.4" />
        <stop offset="1" stopColor="#141c58" stopOpacity="0.14" />
      </linearGradient>
      <linearGradient id={block} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#2a3a90" stopOpacity="0.5" />
        <stop offset="1" stopColor="#060b22" stopOpacity="0.9" />
      </linearGradient>
      <linearGradient id={haze} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#6d4dff" stopOpacity="0.34" />
        <stop offset="0.55" stopColor="#2b3ba8" stopOpacity="0.14" />
        <stop offset="1" stopColor="#04070f" stopOpacity="0" />
      </linearGradient>
      <linearGradient id={motf} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#35d9f2" />
        <stop offset="0.55" stopColor="#7f6bff" />
        <stop offset="1" stopColor="#e05ad0" />
      </linearGradient>
      <filter id={soft} x="-25%" y="-25%" width="150%" height="150%">
        <feGaussianBlur stdDeviation="7" />
      </filter>
      <filter id={soft2} x="-25%" y="-25%" width="150%" height="150%">
        <feGaussianBlur stdDeviation="3" />
      </filter>
    </defs>
  );

  if (variant === "sidebar") {
    return (
      <svg
        className={className}
        viewBox="0 0 274 340"
        preserveAspectRatio="xMidYMax slice"
        aria-hidden="true"
        focusable="false"
      >
        {defs}
        <rect width="274" height="340" fill={`url(#${haze})`} />
        <g fill={`url(#${block})`} stroke="#4d8dff" strokeOpacity="0.24" strokeWidth="1">
          <rect x="6" y="210" width="26" height="130" />
          <rect x="38" y="238" width="20" height="102" />
          <rect x="212" y="220" width="24" height="120" />
          <rect x="242" y="252" width="26" height="88" />
        </g>
        <g>
          <path d="M148 34 h4 l3 52 h-10 z" fill={`url(#${tower})`} />
          <path d="M143 86 h14 l3 44 h-20 z" fill={`url(#${tower})`} />
          <path d="M137 130 h26 l4 46 h-34 z" fill={`url(#${tower})`} />
          <path d="M129 176 h42 l4 52 h-50 z" fill={`url(#${tower})`} />
          <path d="M120 228 h60 l5 112 h-70 z" fill={`url(#${tower})`} />
          <g stroke="#a8ddff" strokeOpacity="0.3" strokeWidth="0.9">
            <path d="M150 40 v46" />
            <path d="M146 90 v38" />
            <path d="M154 90 v38" />
          </g>
          <circle cx="150" cy="32" r="2" fill="#8de8ff" />
        </g>
        <g transform="rotate(-13 70 258)">
          <ellipse cx="70" cy="258" rx="52" ry="36" fill="none" stroke={`url(#${motf})`} strokeWidth="7.5" strokeOpacity="0.68" />
          <ellipse cx="70" cy="258" rx="20" ry="14" fill="#04070f" stroke="#a56bff" strokeWidth="2" strokeOpacity="0.7" />
        </g>
        <ellipse cx="137" cy="336" rx="150" ry="20" fill="#4d8dff" opacity="0.14" filter={`url(#${soft})`} />
      </svg>
    );
  }

  return (
    <svg
      className={className}
      viewBox="0 0 1400 560"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      {defs}
      <rect width="1400" height="560" fill={`url(#${haze})`} opacity="0.85" />
      <g fill={`url(#${block})`} stroke="#4d8dff" strokeOpacity="0.24" strokeWidth="1">
        <rect x="60" y="392" width="56" height="168" />
        <rect x="128" y="434" width="42" height="126" />
        <rect x="182" y="364" width="48" height="196" />
        <rect x="242" y="446" width="62" height="114" />
        <rect x="318" y="410" width="40" height="150" />
        <rect x="1006" y="422" width="50" height="138" />
        <rect x="1068" y="376" width="44" height="184" />
        <rect x="1124" y="440" width="64" height="120" />
        <rect x="1200" y="400" width="48" height="160" />
        <rect x="1258" y="440" width="42" height="120" />
        <rect x="1310" y="414" width="52" height="146" />
      </g>
      <g opacity="0.7">
        <path d="M888 344 L896 344 L900 560 L884 560 Z" fill={`url(#${block})`} stroke="#7fb6ff" strokeOpacity="0.26" />
        <path d="M896 348 C934 408 954 486 960 560 L896 560 Z" fill="#080e30" stroke="#7fb6ff" strokeOpacity="0.28" />
      </g>
      <g>
        <path d="M694 62 h6 l4 74 h-14 z" fill={`url(#${tower})`} />
        <path d="M686 136 h22 l4 62 h-30 z" fill={`url(#${tower})`} />
        <path d="M676 198 h42 l5 64 h-52 z" fill={`url(#${tower})`} />
        <path d="M664 262 h66 l6 68 h-78 z" fill={`url(#${tower})`} />
        <path d="M650 330 h94 l7 74 h-108 z" fill={`url(#${tower})`} />
        <path d="M634 404 h126 l8 156 h-142 z" fill={`url(#${tower})`} />
        <g stroke="#a8ddff" strokeOpacity="0.28" strokeWidth="1">
          <path d="M697 68 v66" />
          <path d="M691 140 v56" />
          <path d="M703 140 v56" />
          <path d="M684 202 v58" />
          <path d="M697 202 v58" />
          <path d="M710 202 v58" />
        </g>
        <circle cx="697" cy="60" r="2.8" fill="#8de8ff" />
      </g>
      <g transform="rotate(-13 424 452)">
        <ellipse cx="424" cy="452" rx="112" ry="76" fill="none" stroke={`url(#${motf})`} strokeWidth="13" strokeOpacity="0.6" />
        <ellipse cx="424" cy="452" rx="112" ry="76" fill="none" stroke="#8de8ff" strokeWidth="1.1" strokeOpacity="0.34" />
        <ellipse cx="424" cy="452" rx="44" ry="30" fill="#050a15" stroke="#a56bff" strokeWidth="2.6" strokeOpacity="0.62" />
      </g>
      <path d="M344 560 q80 -38 160 0 z" fill="#060c22" stroke="#4d8dff" strokeOpacity="0.18" />
      <ellipse cx="700" cy="556" rx="600" ry="46" fill="#4d8dff" opacity="0.1" filter={`url(#${soft})`} />
      <ellipse cx="424" cy="548" rx="130" ry="16" fill="#35d9f2" opacity="0.12" filter={`url(#${soft2})`} />
    </svg>
  );
}
