// Minimal hand-rolled stroke icons (18x18) -- avoids adding an icon
// library dependency for a handful of nav glyphs.
import type { SVGProps } from "react";

function Base(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    />
  );
}

export function DashboardIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.2" />
      <rect x="9.5" y="2.5" width="6" height="4" rx="1.2" />
      <rect x="9.5" y="9" width="6" height="6.5" rx="1.2" />
      <rect x="2.5" y="11" width="6" height="4.5" rx="1.2" />
    </Base>
  );
}

export function AskIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M3 4.5h12v8H8.5L5 15.5V12.5H3z" />
      <path d="M6.2 7.6h5.6M6.2 9.8h3.6" />
    </Base>
  );
}

export function DocumentsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M5 2.5h5.5L13.5 5.5V15.5H5z" />
      <path d="M10.3 2.5V5.5H13.3" />
      <path d="M6.8 9h4.4M6.8 11.4h4.4" />
    </Base>
  );
}

export function ProjectsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 5.2 4 3.5h3l1.2 1.7H15.5v9.3h-13z" />
    </Base>
  );
}

export function BriefIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <rect x="3" y="2.5" width="12" height="13" rx="1.2" />
      <path d="M6 2.5V1.3M12 2.5V1.3" />
      <path d="M5.8 8h6.4M5.8 10.6h6.4M5.8 13.1h4" />
    </Base>
  );
}

export function SettingsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="9" cy="9" r="2.4" />
      <path d="M9 2.7v1.6M9 13.7v1.6M15.3 9h-1.6M4.3 9H2.7M13.3 4.7l-1.1 1.1M5.8 12.1l-1.1 1.1M13.3 13.3l-1.1-1.1M5.8 5.9 4.7 4.8" />
    </Base>
  );
}

export function UploadIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M9 12.5V3.5M5.5 7 9 3.5 12.5 7" />
      <path d="M3.5 14.5h11" />
    </Base>
  );
}

export function TeamIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="6.5" cy="6" r="2.2" />
      <circle cx="12.2" cy="7" r="1.8" />
      <path d="M2.5 14.5c0-2.2 1.8-3.6 4-3.6s4 1.4 4 3.6" />
      <path d="M11 11.2c1.8.1 3 1.4 3 3.3" />
    </Base>
  );
}

export function AuditIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <rect x="3" y="2.5" width="9.5" height="13" rx="1.2" />
      <path d="M5.8 6h4M5.8 8.6h4M5.8 11.2h2.5" />
      <circle cx="13.3" cy="12.8" r="2.3" />
      <path d="M14.9 14.4 16.3 15.8" />
    </Base>
  );
}

export function TasksIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <rect x="3" y="3" width="13" height="13" rx="1.5" />
      <path d="m6 9.5 2 2 3.5-4.2" />
      <path d="M6 13.5h6" />
    </Base>
  );
}

export function ReportsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M4 16V3.5a1 1 0 0 1 1-1h6l3.5 3.5V16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1Z" />
      <path d="M11 2.5V6a1 1 0 0 0 1 1h3" />
      <path d="M6.5 10h5M6.5 12.5h5M6.5 15h3" />
    </Base>
  );
}

export function ChevronRightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props} strokeWidth="1.6">
      <path d="M7 4.5 11 9l-4 4.5" />
    </Base>
  );
}

export function MenuIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 5h13M2.5 9h13M2.5 13h13" />
    </Base>
  );
}

export function CloseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M4.5 4.5l9 9M13.5 4.5l-9 9" />
    </Base>
  );
}

export function SparkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props} strokeWidth="1.3">
      <path d="M9 2.5 10.3 6.9 14.5 8.2 10.3 9.5 9 13.9 7.7 9.5 3.5 8.2 7.7 6.9Z" />
    </Base>
  );
}

export function HelpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="9" cy="9" r="6.8" />
      <path d="M6.9 7.1c.2-1.1 1.1-1.8 2.2-1.8 1.2 0 2.2.8 2.2 1.9 0 1.4-2.2 1.5-2.2 3.1" />
      <circle cx="9" cy="12.9" r="0.15" fill="currentColor" stroke="currentColor" strokeWidth="1.1" />
    </Base>
  );
}

export function MessagesIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 4.2h13v8H9l-3.5 3v-3h-3z" />
      <path d="M5.5 7.3h7M5.5 9.7h4.5" />
    </Base>
  );
}

export function TicketIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 6.5a1.5 1.5 0 0 0 0 5v0.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-0.5a1.5 1.5 0 0 1 0-5V6a1 1 0 0 0-1-1h-11a1 1 0 0 0-1 1z" />
      <path d="M7 5.5v7" strokeDasharray="1.6 1.6" />
    </Base>
  );
}


export function SearchIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="8.2" cy="8.2" r="5.2" />
      <path d="m12.2 12.2 3 3" />
    </Base>
  );
}

export function BellIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M4.6 12.4V8.2a4.4 4.4 0 0 1 8.8 0v4.2l1.1 1.6H3.5z" />
      <path d="M7.3 15.2a1.8 1.8 0 0 0 3.4 0" />
    </Base>
  );
}

export function TrendUpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props} strokeWidth="1.7">
      <path d="M3 12.2 7 8l2.6 2.6L15 5.2" />
      <path d="M11.4 5.2H15v3.6" />
    </Base>
  );
}

export function TrendDownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props} strokeWidth="1.7">
      <path d="M3 5.8 7 10l2.6-2.6L15 12.8" />
      <path d="M11.4 12.8H15V9.2" />
    </Base>
  );
}

export function InsightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M6.6 13.2a4.8 4.8 0 1 1 4.8 0v1.1H6.6z" />
      <path d="M7.2 15.9h3.6" />
    </Base>
  );
}

export function PulseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 9h3l1.8-4.4 2.6 9L11.8 9h3.7" />
    </Base>
  );
}

export function ShieldIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M9 2.4 14.6 4.6v4.2c0 3.3-2.3 5.8-5.6 6.8-3.3-1-5.6-3.5-5.6-6.8V4.6z" />
      <path d="m6.7 8.9 1.7 1.7 3-3.2" />
    </Base>
  );
}

export function GrowthIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.8 15.2h12.4" />
      <rect x="4" y="9.4" width="2.8" height="5.8" rx="0.8" />
      <rect x="8.1" y="6.2" width="2.8" height="9" rx="0.8" />
      <rect x="12.2" y="3.4" width="2.8" height="11.8" rx="0.8" />
    </Base>
  );
}

export function ClockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="9" cy="9" r="6.6" />
      <path d="M9 5.2V9l2.6 1.6" />
    </Base>
  );
}
