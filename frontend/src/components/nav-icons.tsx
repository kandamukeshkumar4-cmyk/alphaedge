import type { ReactElement, SVGProps } from "react";

/*
 * Loop V62 (R1) — shared inline-SVG icon set for navigation and the /features
 * map. No icon library is added (guardrail: no new UI deps); every glyph is a
 * hand-written stroke SVG matching the existing BottomNav/SiteHeader style.
 * Keys are referenced by string from the pure-data feature registry so the
 * registry itself stays JSX-free.
 */

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 16, strokeWidth = 1.8, ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor",
    strokeWidth,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    ...props,
  };
}

export type NavIconKey =
  | "compass"
  | "home"
  | "bolt"
  | "grid"
  | "signal"
  | "clone"
  | "wallet"
  | "map"
  | "trade"
  | "intel"
  | "proof"
  | "social"
  | "account"
  | "system"
  | "radar";

const ICONS: Record<NavIconKey, (props: IconProps) => ReactElement> = {
  compass: (p) => (
    <svg {...base(p)}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2z" />
    </svg>
  ),
  home: (p) => (
    <svg {...base(p)}>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1v-9.5z" />
    </svg>
  ),
  bolt: (p) => (
    <svg {...base(p)}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />
    </svg>
  ),
  grid: (p) => (
    <svg {...base(p)}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </svg>
  ),
  signal: (p) => (
    <svg {...base(p)}>
      <path d="M4 14v-2m4 4V8m4 10V5m4 13V9m4 5v-3" />
    </svg>
  ),
  clone: (p) => (
    <svg {...base(p)}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </svg>
  ),
  wallet: (p) => (
    <svg {...base(p)}>
      <rect x="3" y="6" width="18" height="13" rx="2.5" />
      <path d="M3 10h18M16 14.5h1.5" />
    </svg>
  ),
  map: (p) => (
    <svg {...base(p)}>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  ),
  trade: (p) => (
    <svg {...base(p)}>
      <path d="M4 17h16M4 17l3-3M20 7H4m16 0-3 3" />
    </svg>
  ),
  intel: (p) => (
    <svg {...base(p)}>
      <path d="M12 3a6 6 0 0 0-3 11.2V17h6v-2.8A6 6 0 0 0 12 3zM9.5 20h5M10.5 22h3" />
    </svg>
  ),
  proof: (p) => (
    <svg {...base(p)}>
      <path d="M9 12.5 11 14.5 15.5 10M12 3l7 3v5c0 4.4-3 7.7-7 9-4-1.3-7-4.6-7-9V6l7-3z" />
    </svg>
  ),
  social: (p) => (
    <svg {...base(p)}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20a6 6 0 0 1 12 0M16 5a3 3 0 0 1 0 6M18 20a5.6 5.6 0 0 0-2.5-4.4" />
    </svg>
  ),
  account: (p) => (
    <svg {...base(p)}>
      <circle cx="12" cy="8" r="4" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </svg>
  ),
  system: (p) => (
    <svg {...base(p)}>
      <path d="M3 12h4l2 5 4-12 2 7h6" />
    </svg>
  ),
  radar: (p) => (
    <svg {...base(p)}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 12l6.4-6.4" />
      <circle cx="15.2" cy="8.8" r="0.4" fill="currentColor" stroke="none" />
    </svg>
  ),
};

/** Render a shared nav/feature icon by key. Returns null for unknown keys. */
export function NavIcon({ name, ...props }: { name: NavIconKey } & IconProps) {
  const Glyph = ICONS[name];
  return Glyph ? <Glyph {...props} /> : null;
}
