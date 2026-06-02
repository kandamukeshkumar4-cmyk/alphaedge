"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/cn";

const NAV = [
  { label: "Markets", href: "/markets" },
  { label: "Sports", href: "/markets?cat=Sports" },
  { label: "Politics", href: "/markets?cat=Politics" },
  { label: "Crypto", href: "/markets?cat=Crypto" },
  { label: "Culture", href: "/markets?cat=Culture" },
  { label: "Portfolio", href: "/portfolio" },
];

const CATEGORY_TABS = [
  "Trending",
  "Sports",
  "Politics",
  "Crypto",
  "Culture",
  "Economics",
  "Commodities",
  "Tech",
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const showCategoryBar = pathname === "/" || pathname.startsWith("/markets");

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-4 sm:gap-5">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-sm font-black text-white">
            α
          </span>
          <span className="text-base font-black tracking-tight text-text">
            Alpha<span className="text-primary">Edge</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-5 text-sm font-semibold text-muted lg:flex">
          {NAV.map((item) => {
            const active =
              item.href === pathname ||
              (item.href !== "/markets" && pathname.startsWith(item.href.split("?")[0]) && item.href !== "/");
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "transition hover:text-text",
                  active && "text-primary",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto hidden min-w-0 flex-1 items-center md:flex lg:max-w-md">
          <div className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-muted transition focus-within:border-accent">
            <SearchIcon />
            <input
              className="w-full bg-transparent text-text placeholder:text-muted-2 focus:outline-none"
              placeholder="Trade on anything…"
              aria-label="Search markets"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2 md:ml-3">
          <button
            className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted transition hover:border-border-light hover:text-text"
            aria-label="Notifications"
          >
            <BellIcon />
          </button>
          <Link
            href="/auth/login"
            className="hidden rounded-lg border border-border px-3 py-2 text-sm font-semibold text-text transition hover:border-border-light sm:block"
          >
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="rounded-lg bg-primary px-3.5 py-2 text-sm font-bold text-white transition hover:bg-accent"
          >
            Sign up
          </Link>
          <button
            className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted lg:hidden"
            aria-label="Menu"
            onClick={() => setOpen((v) => !v)}
          >
            <MenuIcon />
          </button>
        </div>
      </div>

      {showCategoryBar && (
        <div className="border-t border-border/60">
          <div className="no-scrollbar mx-auto flex max-w-[1400px] items-center gap-4 overflow-x-auto px-4 py-2 text-sm">
            {CATEGORY_TABS.map((tab, i) => (
              <Link
                key={tab}
                href={tab === "Trending" ? "/" : `/markets?cat=${tab}`}
                className={cn(
                  "whitespace-nowrap font-semibold transition",
                  i === 0
                    ? "border-b-2 border-primary pb-1 text-text"
                    : "text-muted hover:text-text",
                )}
              >
                {tab}
              </Link>
            ))}
          </div>
        </div>
      )}

      {open && (
        <div className="border-t border-border bg-surface px-4 py-3 lg:hidden">
          <nav className="flex flex-col gap-1 text-sm font-semibold">
            {NAV.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-md px-2 py-2 text-muted transition hover:bg-surface-2 hover:text-text"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" strokeLinecap="round" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
    </svg>
  );
}
