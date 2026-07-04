"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useApiHealth } from "@/hooks/useApiHealth";
import { cn } from "@/lib/cn";
import { LevelChip } from "@/components/GamificationLayer";
import { ThemeToggle } from "@/components/quest/ThemeToggle";
import { formatCompactUSD } from "@/lib/mock-data";
import { SearchCommandModal, useSearchCommandModal } from "@/components/SearchCommandModal";

function LiveBadge() {
  const health = useApiHealth();
  const live = health === "live";
  const demo = health === "demo";
  return (
    <span
      className={cn(
        "hidden items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-bold uppercase tracking-wide sm:inline-flex",
        live && "border-primary/40 bg-primary-dim text-primary",
        demo && "border-secondary/40 bg-secondary-dim text-secondary",
        health === "checking" && "border-border bg-surface text-muted-2",
      )}
      title={
        live
          ? "Connected to the AlphaEdge backend — showing live Kalshi & Polymarket data"
          : demo
            ? "Backend not reachable — showing sample data. Start it with: docker compose up"
            : "Checking backend…"
      }
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          live && "animate-pulse-soft bg-primary",
          demo && "bg-secondary",
          health === "checking" && "bg-muted-2",
        )}
      />
      {live ? "Live" : demo ? "Demo" : "…"}
    </span>
  );
}

function MoreMenu() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative" onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="px-2.5 py-1 text-[13px] font-medium text-muted transition hover:text-text"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        More ▾
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 top-full z-50 mt-1 w-40 rounded-lg border border-border bg-surface p-1 shadow-lift"
        >
          {MORE_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              role="menuitem"
              className="block rounded-md px-2.5 py-1.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

const NAV_LINKS: Array<{ href: string; label: string; tour: string }> = [
  { href: "/", label: "Discover", tour: "nav-discover" },
  { href: "/feed", label: "Feed", tour: "nav-feed" },
  { href: "/markets", label: "Trade", tour: "nav-markets" },
  { href: "/clones", label: "Clones", tour: "nav-clones" },
  { href: "/leaderboard", label: "Leaderboard", tour: "nav-leaderboard" },
  { href: "/research", label: "Research", tour: "nav-research" },
  { href: "/backtest", label: "Backtest", tour: "nav-backtest" },
  { href: "/signals", label: "Signals", tour: "nav-signals" },
  { href: "/track-record", label: "Track record", tour: "nav-track-record" },
  { href: "/forecast", label: "Forecast", tour: "nav-forecast" },
  { href: "/macro", label: "Macro", tour: "nav-macro" },
  { href: "/weather", label: "Weather", tour: "nav-weather" },
];

// Secondary destinations — desktop "More" dropdown + mobile menu.
const MORE_LINKS: Array<{ href: string; label: string }> = [
  { href: "/alerts", label: "Alerts" },
  { href: "/eval", label: "Model eval" },
  { href: "/mirror", label: "Mirror markets" },
  { href: "/portfolio", label: "Portfolio" },
];

function QuestHeaderInner() {
  const pathname = usePathname();
  const { token, isReady, paperBalance } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const { open: searchOpen, openModal: openSearch, closeModal: closeSearch } = useSearchCommandModal();

  if (pathname.startsWith("/admin")) return null;

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-bg/95 backdrop-blur">
      <div className="mx-auto flex h-10 max-w-[1600px] items-center gap-3 px-3 sm:px-4">
        <Link href="/" className="flex shrink-0 items-center gap-1.5" aria-label="AlphaEdge home" data-tour="logo">
          <span className="grid h-6 w-6 place-items-center rounded-full bg-accent-bright font-mono text-[10px] font-bold text-bg">
            AE
          </span>
        </Link>

        <nav className="hidden items-center md:flex" aria-label="Primary">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                data-tour={link.tour}
                className={cn(
                  "relative px-2.5 py-1 text-[13px] font-medium transition",
                  active ? "text-text" : "text-muted hover:text-text",
                )}
              >
                {link.label}
                {active && (
                  <span className="absolute inset-x-2.5 -bottom-[9px] h-0.5 rounded-full bg-accent-bright" />
                )}
              </Link>
            );
          })}
          <MoreMenu />
        </nav>

        {/* Header search box — clicking opens the command palette */}
        <button
          type="button"
          onClick={openSearch}
          className="mx-auto hidden w-full min-w-0 max-w-xs flex-1 cursor-pointer lg:block"
          aria-label="Open market search (Cmd+K)"
        >
          <span className="flex h-7 items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-xs text-muted-2 hover:border-accent transition">
            <SearchIcon />
            <span className="flex-1 text-left text-muted-2">Search markets…</span>
            <kbd className="hidden rounded border border-border bg-bg px-1 py-0.5 font-mono text-[9px] text-muted-2 sm:inline">
              ⌘K
            </kbd>
          </span>
        </button>

        <SearchCommandModal open={searchOpen} onClose={closeSearch} />

        <div className="ml-auto flex items-center gap-1.5 lg:ml-0">
          <LiveBadge />
          <ThemeToggle />
          <Link
            href="/alerts"
            className="grid h-7 w-7 place-items-center rounded-lg text-muted transition hover:bg-surface hover:text-text"
            aria-label="Alerts"
            title="Alerts"
          >
            <BellIcon />
          </Link>
          <LevelChip />
          {isReady && token ? (
            <>
              <Link
                href="/portfolio"
                className="hidden h-7 items-center gap-1.5 rounded-lg border border-border bg-surface px-2 font-mono text-[11px] font-semibold text-accent-bright sm:flex"
                title="Paper balance (simulated funds)"
              >
                <WalletIcon />
                {typeof paperBalance === "number" ? formatCompactUSD(paperBalance) : "…"}
              </Link>
              <Link
                href="/portfolio"
                data-tour="nav-portfolio"
                className="rounded-lg bg-accent-bright px-3 py-1 text-xs font-semibold text-bg transition hover:bg-accent"
              >
                Portfolio
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/auth/login"
                className="hidden rounded-lg px-2.5 py-1 text-xs font-semibold text-muted hover:text-text sm:inline"
              >
                Log in
              </Link>
              <Link
                href="/auth/signup"
                data-tour="nav-portfolio"
                className="rounded-lg bg-accent-bright px-3 py-1 text-xs font-semibold text-bg transition hover:bg-accent"
              >
                Get started
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:text-text md:hidden"
            aria-label="Open menu"
            aria-expanded={menuOpen}
          >
            <MenuIcon />
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav className="border-t border-border bg-bg px-4 py-2 md:hidden" aria-label="Primary mobile">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="block rounded-lg px-3 py-2.5 text-sm font-medium text-muted hover:bg-surface hover:text-text"
            >
              {link.label}
            </Link>
          ))}
          <div className="my-1 border-t border-border" />
          {MORE_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="block rounded-lg px-3 py-2.5 text-sm font-medium text-muted hover:bg-surface hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function QuestHeader() {
  return (
    <Suspense fallback={<header className="h-10 border-b border-border bg-bg" />}>
      <QuestHeaderInner />
    </Suspense>
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

function WalletIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18M16 15h2" strokeLinecap="round" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path
        d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
    </svg>
  );
}
