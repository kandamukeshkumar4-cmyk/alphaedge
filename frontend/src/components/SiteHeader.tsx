"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { AlertToast } from "@/components/AlertToast";
import { ApiHealthChip } from "@/components/ApiHealthChip";
import { HeaderMoreMenu } from "@/components/HeaderMoreMenu";
import { HeaderSearch } from "@/components/HeaderSearch";
import { AlertsBell } from "@/components/AlertsBell";
import { NavIcon, type NavIconKey } from "@/components/nav-icons";
import { NotificationBell } from "@/components/NotificationBell";
import { SignalAlertBadge } from "@/components/SignalAlertBadge";
import { FEATURE_GROUPS } from "@/lib/feature-registry";
import { useAuth } from "@/hooks/useAuth";
import { useSignalAlerts } from "@/hooks/useSignalAlerts";
import { cn } from "@/lib/cn";

/*
 * QuestFlow nav: Discover | Trade | Markets | Signals | Terminal | Portfolio | Features
 * with icon+text labels (Loop V62 R1 — no icon-only mystery meat). Home and
 * Clones defer to xl to keep the 1280 row tight; Features (the full map) and
 * every secondary surface stay ≤1 click away via the grouped More menu.
 */
const NAV: { label: string; href: string; icon: NavIconKey }[] = [
  { label: "Discover", href: "/", icon: "compass" },
  { label: "Home", href: "/home", icon: "home" },
  { label: "Trade", href: "/trade", icon: "bolt" },
  { label: "Markets", href: "/markets", icon: "grid" },
  { label: "Signals", href: "/signals", icon: "signal" },
  { label: "Terminal", href: "/terminal", icon: "intel" },
  { label: "Skills", href: "/skills", icon: "intel" },
  { label: "Clones", href: "/clones", icon: "clone" },
  { label: "Portfolio", href: "/portfolio", icon: "wallet" },
  { label: "Features", href: "/features", icon: "map" },
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
        <div className="mx-auto flex h-[56px] max-w-[1600px] items-center gap-1.5 overflow-x-hidden px-3 sm:gap-2.5 sm:px-4">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2.5"
            aria-label="AE AlphaEdge home"
          >
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

          {/* sm–lg: in header; lg–xl: hidden (nav+auth tight at 1280); xl+: back. */}
          <ApiHealthChip className="hidden shrink-0 sm:inline-flex lg:hidden xl:inline-flex" />

          <nav className="hidden h-full min-w-0 items-stretch gap-0.5 self-stretch lg:flex">
            {NAV.map((item) => {
              const base = item.href.split("?")[0];
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === base || pathname.startsWith(`${base}/`);
              // PC10: at 1280, Home/Clones compete with search — defer them to
              // xl. Features lives in the More map (its own surface) so the bar
              // stays ≤8 items now that Terminal (V79 A7) is always visible.
              const deferWide = item.label === "Home" || item.label === "Clones";
              const hideInBar = item.label === "Features";
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={item.label === "Signals" ? () => markRead() : undefined}
                  className={cn(
                    "relative flex items-center gap-1.5 px-2 text-[13px] font-semibold transition",
                    deferWide && "hidden xl:flex",
                    hideInBar && "hidden",
                    active ? "text-text" : "text-muted hover:text-text",
                  )}
                >
                  <NavIcon name={item.icon} size={15} className="shrink-0" />
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

          {/* PC01 + PC10: readable search without pushing bells past 1280. */}
          <div className="ml-auto hidden min-w-[200px] flex-1 items-center md:flex lg:min-w-[220px] lg:max-w-[320px]">
            <HeaderSearch />
          </div>

          <div className="ml-auto flex min-w-0 shrink-0 items-center gap-1.5 sm:gap-2 md:ml-0">
            <Link
              href="/portfolio"
              className="hidden h-9 items-center rounded-lg bg-primary px-3 text-sm font-bold text-bg shadow-glow transition hover:brightness-110 sm:inline-flex"
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
                <span className="hidden xl:inline-flex">
                  <Button
                    label="Sign up"
                    variant="primary"
                    onClick={() => router.push("/auth/signup")}
                  />
                </span>
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
                  className="flex items-center gap-2.5 rounded-md px-2 py-2 text-muted transition hover:bg-surface-2 hover:text-text"
                >
                  <NavIcon name={item.icon} size={16} className="shrink-0 text-muted-2" />
                  <NavLabel
                    label={item.label}
                    unreadCount={item.label === "Signals" ? unreadCount : undefined}
                  />
                </Link>
              ))}
            </nav>
            <Link
              href="/features"
              onClick={() => setOpen(false)}
              className="mt-3 flex items-center gap-2.5 rounded-lg border border-border bg-surface-2/60 px-3 py-2.5 transition hover:border-primary/40"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
                <NavIcon name="map" size={15} />
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] font-black text-text">All features →</span>
                <span className="block text-[11px] text-muted-2">
                  The full map of everything AlphaEdge does.
                </span>
              </span>
            </Link>
            <nav className="mt-2 flex flex-col gap-2">
              {FEATURE_GROUPS.map((group) => (
                <div key={group.id}>
                  <p className="flex items-center gap-1.5 px-2 pb-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
                    <NavIcon name={group.icon} size={12} />
                    {group.title}
                  </p>
                  <div className="grid grid-cols-2 gap-1 text-sm font-semibold">
                    {group.features.map((item) => (
                      <Link
                        key={item.id}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className="rounded-md px-2 py-1.5 text-muted transition hover:bg-surface-2 hover:text-text"
                      >
                        {item.label}
                      </Link>
                    ))}
                  </div>
                </div>
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

