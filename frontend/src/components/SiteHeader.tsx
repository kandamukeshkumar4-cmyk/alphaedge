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
  { label: "Mirror", href: "/forecast" },
  { label: "Portfolio", href: "/portfolio" },
];

const CATEGORY_TABS = [
  { label: "All", href: "/" },
  { label: "Sports", href: "/markets?cat=Sports" },
  { label: "Politics", href: "/markets?cat=Politics" },
  { label: "Crypto", href: "/markets?cat=Crypto" },
  { label: "Culture", href: "/markets?cat=Culture" },
  { label: "Economics", href: "/markets?cat=Economics" },
  { label: "Tech", href: "/markets?cat=Tech" },
  { label: "World", href: "/markets?cat=Politics" },
  { label: "Paper trading", href: "/portfolio" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const showCategoryBar = pathname === "/" || pathname.startsWith("/markets");

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/95 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-[1440px] items-center gap-4 px-4 sm:px-5">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="AlphaEdge home">
          <span className="relative h-8 w-8 overflow-hidden rounded-md bg-primary-dim">
            <span className="absolute bottom-0 left-1 h-6 w-2 -skew-x-[28deg] bg-primary" />
            <span className="absolute bottom-0 left-3.5 h-8 w-2 -skew-x-[28deg] bg-accent" />
            <span className="absolute bottom-0 right-1 h-4 w-2 -skew-x-[28deg] bg-primary/70" />
          </span>
          <span className="text-lg font-black tracking-tight text-text">
            AlphaEdge
          </span>
        </Link>

        <nav className="hidden items-center gap-7 text-[12px] font-black uppercase tracking-[0.08em] text-muted lg:flex">
          {NAV.map((item) => {
            const base = item.href.split("?")[0];
            const isCategoryNav = item.href.includes("?cat=");
            const active =
              item.href === "/markets"
                ? pathname.startsWith("/markets")
                : !isCategoryNav && (pathname === base || pathname.startsWith(`${base}/`));
            return (
              <Link
                key={item.label}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative py-5 transition hover:text-text",
                  active && "text-primary after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-primary",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto hidden min-w-0 flex-1 items-center md:flex lg:max-w-[430px]">
          <label className="flex h-10 w-full items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-muted transition focus-within:border-border-light focus-within:bg-surface-2">
            <SearchIcon />
            <input
              className="w-full bg-transparent text-sm font-medium text-text placeholder:text-muted-2 focus:outline-none"
              placeholder="Search markets"
              aria-label="Search markets"
            />
            <span className="hidden rounded border border-border-light px-1.5 py-0.5 font-mono text-[10px] text-muted-2 xl:inline">
              /
            </span>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/auth/login"
            className="hidden h-10 items-center rounded-md border border-border px-5 text-sm font-bold text-text transition hover:border-border-light hover:bg-surface sm:inline-flex"
          >
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="inline-flex h-10 items-center rounded-md bg-primary px-5 text-sm font-black text-bg shadow-glow transition hover:bg-accent"
          >
            Sign up
          </Link>
          <button
            className="grid h-10 w-10 place-items-center rounded-md border border-border text-muted transition hover:border-border-light hover:text-text lg:hidden"
            aria-label="Menu"
            onClick={() => setOpen((v) => !v)}
          >
            <MenuIcon />
          </button>
        </div>
      </div>

      {showCategoryBar && (
        <div className="border-t border-border/70">
          <div className="no-scrollbar mx-auto flex max-w-[1440px] items-center gap-7 overflow-x-auto px-4 py-3 text-sm sm:px-5">
            {CATEGORY_TABS.map((tab, i) => (
              <Link
                key={tab.label}
                href={tab.href}
                className={cn(
                  "group relative flex shrink-0 items-center gap-2 whitespace-nowrap pb-1 font-bold text-muted transition hover:text-text",
                  i === 0 && "text-text after:absolute after:inset-x-0 after:-bottom-3 after:h-0.5 after:bg-primary",
                )}
              >
                <span
                  className={cn(
                    "h-2 w-2 rounded-sm border border-border-light transition group-hover:border-primary",
                    i === 0 ? "bg-primary" : "bg-surface-3",
                  )}
                />
                {tab.label}
              </Link>
            ))}
            <Link
              href="/markets"
              className="ml-auto hidden shrink-0 rounded-md border border-border px-4 py-2 text-xs font-black text-text transition hover:border-border-light hover:bg-surface xl:block"
            >
              View all
            </Link>
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

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
    </svg>
  );
}
