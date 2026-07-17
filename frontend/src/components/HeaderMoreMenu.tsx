"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { NavIcon } from "@/components/nav-icons";
import { ALL_FEATURES, FEATURE_GROUPS } from "@/lib/feature-registry";
import { cn } from "@/lib/cn";

/*
 * Loop V62 (R1) — the "More" menu is now a grouped feature map driven by the
 * single-source feature registry. Every shipped capability is ≤1 click from
 * the header (open More) and the full map is one click away at /features. The
 * grouping + labels + one-line blurbs kill "mystery meat" secondary nav.
 */

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function HeaderMoreMenu() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const anyActive = ALL_FEATURES.some((item) => isActive(pathname, item.href));

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
          className={cn("transition-transform duration-200", open && "rotate-180")}
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
          className="absolute right-0 top-[calc(100%+8px)] z-50 max-h-[72vh] w-[min(92vw,42rem)] overflow-y-auto rounded-xl border border-border bg-surface p-2 shadow-lift"
        >
          <Link
            href="/features"
            role="menuitem"
            onClick={() => setOpen(false)}
            className={cn(
              "mb-2 flex items-center gap-2.5 rounded-lg border px-3 py-2.5 transition",
              isActive(pathname, "/features")
                ? "border-primary/40 bg-primary-dim/40"
                : "border-border bg-surface-2/60 hover:border-primary/40",
            )}
          >
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
              <NavIcon name="map" size={17} />
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-black text-text">All features →</span>
              <span className="block text-[11px] text-muted-2">
                The full map of everything AlphaEdge does.
              </span>
            </span>
          </Link>

          <div className="grid gap-x-3 sm:grid-cols-2">
            {FEATURE_GROUPS.map((group) => (
              <div key={group.id} className="py-1">
                <p className="flex items-center gap-1.5 px-2 pb-1 pt-1 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
                  <NavIcon name={group.icon} size={13} />
                  {group.title}
                </p>
                {group.features.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.id}
                      href={item.href}
                      role="menuitem"
                      onClick={() => setOpen(false)}
                      className={cn(
                        "flex flex-col gap-0.5 rounded-lg px-2 py-1.5 transition",
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
                      <span className="text-[11px] leading-snug text-muted-2">{item.blurb}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
