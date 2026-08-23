// The UAE AI Office mark: a document (the business records the product
// grounds every answer in) with two small connected accent nodes (AI /
// knowledge-graph connections) picked out in the brand gradient. Kept as
// a single hand-authored SVG rather than an icon-library asset so it is
// exact, dependency-free, and equally legible pinned small (sidebar) or
// large (auth hero) in both LTR and RTL layouts -- it carries no text, so
// it never needs mirroring or translation.
import { useId } from "react";

export function BrandMark({ size = 32 }: { size?: number }) {
  const gradientId = useId();

  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <path d="M10 8h7l4 4v12H10z" fill="#ffffff" fillOpacity="0.96" />
      <path d="M17 8 21 12 17 12Z" fill="#0a1530" fillOpacity="0.22" />
      <path
        d="M12.4 16.2h6.2M12.4 19h6.2M12.4 21.8h4"
        stroke="#2148d6"
        strokeOpacity="0.55"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M20.6 10.6 18.4 12.6" stroke="#eafcff" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M23 8.4 20.9 10.4" stroke="#eafcff" strokeOpacity="0.7" strokeWidth="1.1" strokeLinecap="round" />
      <circle cx="22.2" cy="9.3" r="2.1" fill="#eafcff" />
      <circle cx="25" cy="7.1" r="1.1" fill="#eafcff" fillOpacity="0.85" />
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#2148d6" />
          <stop offset="1" stopColor="#0eaec4" />
        </linearGradient>
      </defs>
    </svg>
  );
}

