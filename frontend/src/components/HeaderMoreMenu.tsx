"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

// P04: secondary surfaces that regressed out of the primary nav. Kept in a
// "More" dropdown so the primary 6 tabs stay uncluttered while every shipped
// capability is ≤1 click from the header. Shared with the mobile menu.
export const MORE_NAV: { label: string; href: string; blurb: string }[] = [
  { label: "Opportunities", href: "/opportunities", blurb: "Biggest model-vs-market edges" },
  { label: "Research", href: "/research", blurb: "AI briefs & citations" },
  { label: "Feed", href: "/feed", blurb: "Signals activity stream" },
  { label: "Alerts", href: "/alerts", blurb: "Price & signal triggers" },
  { label: "Track record", href: "/track-record", blurb: "Calibration & CLV" },
  { label: "Resolved", href: "/resolved", blurb: "Model calls vs real outcomes" },
  { label: "Compare", href: "/compare", blurb: "Markets side by side" },
  { label: "Smart money", href: "/smart-money", blurb: "Whale flow & concentration" },
  { label: "Arb", href: "/arb", blurb: "Cross-venue matched pairs" },
  { label: "Weather", href: "/weather", blurb: "Outdoor-market edges" },
  { label: "Macro", href: "/macro", blurb: "Rates & econ context" },
  { label: "Eval", href: "/eval", blurb: "Model evaluation" },
  { label: "Backtest", href: "/backtest", blurb: "Walk-forward CLV" },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function HeaderMoreMenu() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const anyActive = MORE_NAV.some((item) => isActive(pathname, item.href));

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative flex items-center">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "relative flex items-center gap-1 px-2.5 text-[13px] font-semibold transition",
          anyActive || open ? "text-text" : "text-muted hover:text-text",
        )}
      >
        More
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          className={cn("transition-transform", open && "rotate-180")}
          aria-hidden
        >
          <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {anyActive && (
          <span className="absolute inset-x-1.5 bottom-0 h-[2px] rounded-full bg-primary shadow-[0_0_12px_rgba(45,212,191,0.75)]" />
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+8px)] z-50 w-60 overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-lift"
        >
          {MORE_NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                onClick={() => setOpen(false)}
                className={cn(
                  "flex flex-col gap-0.5 rounded-lg px-3 py-2 transition",
                  active ? "bg-surface-2" : "hover:bg-surface-2",
                )}
              >
                <span
                  className={cn(
                    "text-[13px] font-semibold",
                    active ? "text-primary" : "text-text",
                  )}
                >
                  {item.label}
                </span>
                <span className="text-[11px] text-muted-2">{item.blurb}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
