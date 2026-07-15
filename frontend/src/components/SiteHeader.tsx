"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { AlertToast } from "@/components/AlertToast";
import { ApiHealthChip } from "@/components/ApiHealthChip";
import { HeaderMoreMenu, MORE_NAV } from "@/components/HeaderMoreMenu";
import { HeaderSearch } from "@/components/HeaderSearch";
import { AlertsBell } from "@/components/AlertsBell";
import { NotificationBell } from "@/components/NotificationBell";
import { SignalAlertBadge } from "@/components/SignalAlertBadge";
import { useAuth } from "@/hooks/useAuth";
import { useSignalAlerts } from "@/hooks/useSignalAlerts";
import { cn } from "@/lib/cn";

/*
 * QuestFlow nav: Discover | Trade | Markets | Signals | Clones | Portfolio
 * (Leaderboard stays reachable from Discover Intelligence + /leaderboard).
 */
const NAV = [
  { label: "Discover", href: "/" },
  { label: "Home", href: "/home" },
  { label: "Trade", href: "/trade" },
  { label: "Markets", href: "/markets" },
  { label: "Signals", href: "/signals" },
  { label: "Clones", href: "/clones" },
  { label: "Portfolio", href: "/portfolio" },
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
  const isLoggedIn = isReady && !!token;
  const onSignalsNav = pathname === "/signals" || pathname.startsWith("/signals/");

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-bg/95 backdrop-blur-xl">
        {/* BUG-V18-01: gap-2/gap-1.5 below 640px — the logo + auth cluster
            otherwise overflows a 375px viewport by ~6px (scrollWidth 381). */}
        <div className="mx-auto flex h-[56px] max-w-[1600px] items-center gap-2 px-3 sm:gap-3 sm:px-5">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="AlphaEdge home">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-primary to-accent font-mono text-xs font-black text-bg shadow-glow">
              AE
            </span>
            <span className="flex items-center gap-2">
              <span className="text-[15px] font-black tracking-tight text-text">AlphaEdge</span>
              <span className="hidden rounded border border-primary/25 bg-primary-dim/55 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-primary xl:inline">
                Sim
              </span>
            </span>
          </Link>

          <ApiHealthChip className="hidden shrink-0 sm:inline-flex" />

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
                    "relative flex items-center px-2.5 text-[13px] font-semibold transition",
                    active ? "text-text" : "text-muted hover:text-text",
                  )}
                >
                  <NavLabel
                    label={item.label}
                    unreadCount={item.label === "Signals" ? unreadCount : undefined}
                  />
                  {active && (
                    <span className="absolute inset-x-1.5 bottom-0 h-[2px] rounded-full bg-primary shadow-[0_0_12px_rgba(45,212,191,0.75)]" />
                  )}
                </Link>
              );
            })}
            <HeaderMoreMenu />
          </nav>

          {/* PC01: min-w so the search field is not crushed by the nav/auth
              cluster at 1280 — placeholder was clipping to "Search markets… (". */}
          <div className="ml-auto hidden min-w-[220px] flex-1 items-center md:flex lg:min-w-[280px] lg:max-w-[380px]">
            <HeaderSearch />
          </div>

          <div className="ml-auto flex min-w-0 items-center gap-1.5 sm:gap-2 md:ml-0">
            <Link
              href="/portfolio"
              className="hidden h-9 items-center rounded-lg bg-primary px-3.5 text-sm font-bold text-bg shadow-glow transition hover:brightness-110 sm:inline-flex"
              aria-label="View paper balance and portfolio"
              title="View your paper balance and positions"
            >
              Portfolio
            </Link>
            {isLoggedIn ? (
              <>
                {paperBalance !== null ? (
                  <span
                    className="hidden items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 font-mono text-sm font-bold text-text sm:inline-flex"
                    title="Unified paper portfolio balance"
                  >
                    {formatPaperBalance(paperBalance)}
                  </span>
                ) : null}
                <span
                  className="hidden max-w-[140px] truncate text-sm font-semibold text-muted sm:inline"
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
            <AlertsBell />
            <NotificationBell />
            <button
              className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted transition hover:border-border-light hover:text-text lg:hidden"
              aria-label="Menu"
              onClick={() => setOpen((v) => !v)}
            >
              <MenuIcon />
            </button>
          </div>
        </div>

        {open && (
          <div className="border-t border-border bg-surface px-4 py-3 lg:hidden">
            <div className="mb-2 flex items-center px-2 sm:hidden">
              <ApiHealthChip />
            </div>
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
            <p className="mt-3 px-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
              More
            </p>
            <nav className="mt-1 grid grid-cols-2 gap-1 text-sm font-semibold">
              {MORE_NAV.map((item) => (
                <Link
                  key={item.href}
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
      {!onSignalsNav ? <AlertToast alerts={alerts} /> : null}
    </>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
    </svg>
  );
}

