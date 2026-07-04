"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { AlertToast } from "@/components/AlertToast";
import { NotificationBell } from "@/components/NotificationBell";
import { SignalAlertBadge } from "@/components/SignalAlertBadge";
import { useAuth } from "@/hooks/useAuth";
import { useSignalAlerts } from "@/hooks/useSignalAlerts";
import { cn } from "@/lib/cn";
import { MARKETS } from "@/lib/mock-data";

/*
 * QuestFlow-app nav model: a flat product-level tab row (Feed | Markets |
 * Signals | Forecast | Mirror | Leaderboard | Portfolio) with an active
 * underline indicator, plus a category chip bar on discovery pages.
 */
const NAV = [
  { label: "Feed", href: "/" },
  { label: "Markets", href: "/markets" },
  { label: "Signals", href: "/signals" },
  { label: "Forecast", href: "/forecast" },
  { label: "Mirror", href: "/mirror" },
  { label: "Leaderboard", href: "/leaderboard" },
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

function formatPaperBalance(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function truncateEmail(value: string): string {
  const at = value.indexOf("@");
  if (at <= 0 || value.length <= 20) {
    return value;
  }
  return `${value.slice(0, 6)}…${value.slice(at)}`;
}

function NavLabel({ label, unreadCount }: { label: string; unreadCount?: number }) {
  if (label !== "Signals" || unreadCount === undefined) {
    return <>{label}</>;
  }

  return (
    <span className="relative inline-flex items-center">
      {label}
      <SignalAlertBadge count={unreadCount} />
    </span>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { token, email, paperBalance, logout, isReady } = useAuth();
  const [open, setOpen] = useState(false);
  const { alerts, unreadCount, markRead } = useSignalAlerts();
  const showCategoryBar = pathname === "/" || pathname.startsWith("/markets");
  const catalogSlugs = useMemo(() => MARKETS.map((m) => m.slug), []);
  const isLoggedIn = isReady && !!token;
  const onSignalsNav = pathname === "/signals" || pathname.startsWith("/signals/");

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-bg/95 backdrop-blur-xl">
        <div className="mx-auto flex h-[60px] max-w-[1440px] items-center gap-4 px-4 sm:px-5">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="AlphaEdge home">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-primary to-accent font-mono text-sm font-black text-bg shadow-glow">
              AE
            </span>
            <span className="flex items-center gap-2">
              <span className="text-lg font-black tracking-tight text-text">AlphaEdge</span>
              <span className="hidden rounded border border-primary/25 bg-primary-dim/55 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-primary xl:inline">
                Sim
              </span>
            </span>
          </Link>

          <nav className="hidden h-full items-stretch gap-0.5 self-stretch lg:flex">
            {NAV.map((item) => {
              const base = item.href.split("?")[0];
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === base || pathname.startsWith(`${base}/`);
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={item.label === "Signals" ? () => markRead() : undefined}
                  className={cn(
                    "relative flex items-center px-3 text-[12px] font-bold uppercase tracking-[0.08em] transition",
                    active ? "text-text" : "text-muted hover:text-text",
                  )}
                >
                  <NavLabel
                    label={item.label}
                    unreadCount={item.label === "Signals" ? unreadCount : undefined}
                  />
                  {active && (
                    <span className="absolute inset-x-2 bottom-0 h-[2px] rounded-full bg-primary shadow-[0_0_12px_rgba(0,226,138,0.75)]" />
                  )}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto hidden min-w-0 flex-1 items-center md:flex lg:max-w-[430px]">
            <label className="flex h-10 w-full items-center gap-2 rounded-xl border border-border bg-surface px-3 text-sm text-muted transition focus-within:border-primary/45 focus-within:bg-surface-2">
              <SearchIcon />
              <input
                className="w-full bg-transparent text-sm font-medium text-text placeholder:text-muted-2 focus:outline-none"
                placeholder="Search markets or signals"
                aria-label="Search markets or signals"
              />
              <span className="hidden rounded border border-border-light px-1.5 py-0.5 font-mono text-[10px] text-muted-2 xl:inline">
                /
              </span>
            </label>
          </div>

          <div className="flex items-center gap-2">
            {isLoggedIn ? (
              <>
                {paperBalance !== null ? (
                  <span
                    className="hidden items-center gap-1.5 rounded-lg border border-primary/25 bg-primary-dim/55 px-2.5 py-1.5 font-mono text-sm font-bold text-primary sm:inline-flex"
                    title="Unified paper portfolio balance"
                  >
                    {formatPaperBalance(paperBalance)}
                  </span>
                ) : null}
                <span
                  className="hidden max-w-[160px] truncate text-sm font-semibold text-muted sm:inline"
                  title={email ?? undefined}
                >
                  {email ? truncateEmail(email) : "Account"}
                </span>
                <Button label="Log out" variant="ghost" onClick={logout} />
              </>
            ) : (
              <>
                <Button label="Log in" variant="ghost" onClick={() => router.push("/auth/login")} />
                <Button
                  label="Sign up"
                  variant="primary"
                  onClick={() => router.push("/auth/signup")}
                />
              </>
            )}
            <NotificationBell slugs={catalogSlugs} />
            <button
              className="grid h-10 w-10 place-items-center rounded-xl border border-border text-muted transition hover:border-border-light hover:text-text lg:hidden"
              aria-label="Menu"
              onClick={() => setOpen((v) => !v)}
            >
              <MenuIcon />
            </button>
          </div>
        </div>

        {showCategoryBar && (
          <div className="border-t border-border/70">
            <div className="no-scrollbar mx-auto flex max-w-[1440px] items-center gap-2 overflow-x-auto px-4 py-2.5 text-sm sm:px-5">
              {CATEGORY_TABS.map((tab, i) => (
                <Link
                  key={tab.label}
                  href={tab.href}
                  className={cn(
                    "flex shrink-0 items-center whitespace-nowrap rounded-full px-3.5 py-1.5 text-xs font-bold transition",
                    i === 0
                      ? "bg-primary text-bg"
                      : "border border-border bg-surface text-muted hover:border-border-light hover:text-text",
                  )}
                >
                  {tab.label}
                </Link>
              ))}
              <Link
                href="/markets"
                className="ml-auto hidden shrink-0 rounded-full border border-border px-4 py-1.5 text-xs font-black text-text transition hover:border-primary hover:text-primary xl:block"
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
                  onClick={() => {
                    if (item.label === "Signals") {
                      markRead();
                    }
                    setOpen(false);
                  }}
                  className="rounded-md px-2 py-2 text-muted transition hover:bg-surface-2 hover:text-text"
                >
                  <NavLabel
                    label={item.label}
                    unreadCount={item.label === "Signals" ? unreadCount : undefined}
                  />
                </Link>
              ))}
            </nav>
          </div>
        )}
      </header>
      {!onSignalsNav ? <AlertToast alerts={alerts} /> : null}
    </>
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
