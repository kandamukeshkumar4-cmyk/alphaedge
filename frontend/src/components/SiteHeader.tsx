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
 * QuestFlow nav: Discover | Analyze | Markets | Signals | Clones
 * (History / research log stays reachable at /portfolio; Leaderboard from Discover.)
 */
const NAV = [
  { label: "Discover", href: "/" },
  { label: "Analyze", href: "/trade" },
  { label: "Markets", href: "/markets" },
  { label: "Signals", href: "/signals" },
  { label: "Clones", href: "/clones" },
];

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
  const { token, email, logout, isReady } = useAuth();
  const [open, setOpen] = useState(false);
  const { alerts, unreadCount, markRead } = useSignalAlerts();
  const catalogSlugs = useMemo(() => MARKETS.map((m) => m.slug), []);
  const isLoggedIn = isReady && !!token;
  const onSignalsNav = pathname === "/signals" || pathname.startsWith("/signals/");

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-bg/95 backdrop-blur-xl">
        <div className="mx-auto flex h-[56px] max-w-[1600px] items-center gap-3 px-3 sm:px-5">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="AlphaEdge home">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-primary to-accent font-mono text-xs font-black text-bg shadow-glow">
              AE
            </span>
            <span className="flex items-center gap-2">
              <span className="text-[15px] font-black tracking-tight text-text">AlphaEdge</span>
              <span className="hidden rounded border border-primary/25 bg-primary-dim/55 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-primary xl:inline">
                Research
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
          </nav>

          <div className="ml-auto hidden min-w-0 flex-1 items-center md:flex lg:max-w-[380px]">
            <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm text-muted transition focus-within:border-primary/45 focus-within:bg-surface-2">
              <SearchIcon />
              <input
                className="w-full bg-transparent text-sm font-medium text-text placeholder:text-muted-2 focus:outline-none"
                placeholder="Search markets or clones..."
                aria-label="Search markets or clones"
              />
            </label>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/signals"
              className="hidden h-9 items-center rounded-lg bg-primary px-3.5 text-sm font-bold text-bg shadow-glow transition hover:brightness-110 sm:inline-flex"
              aria-label="Open signals"
              title="Browse live signals"
            >
              Signals
            </Link>
            {isLoggedIn ? (
              <>
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
            <NotificationBell slugs={catalogSlugs} />
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
              <Link
                href="/portfolio"
                onClick={() => setOpen(false)}
                className="rounded-md px-2 py-2 text-muted-2 transition hover:bg-surface-2 hover:text-text"
              >
                Research history
              </Link>
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
