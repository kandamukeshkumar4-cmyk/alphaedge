"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { KALSHI_TOPICS, type KalshiTopicId } from "@/lib/kalshi-topics";
import { cn } from "@/lib/cn";
import { LevelChip } from "@/components/GamificationLayer";

const NAV_LINKS: Array<{ href: string; label: string; tour: string }> = [
  { href: "/markets", label: "Markets", tour: "nav-markets" },
  { href: "/research", label: "Research", tour: "nav-research" },
  { href: "/track-record", label: "Track record", tour: "nav-track-record" },
  { href: "/signals", label: "Signals", tour: "nav-signals" },
  { href: "/forecast", label: "Forecast", tour: "nav-forecast" },
  { href: "/leaderboard", label: "Leaderboard", tour: "nav-leaderboard" },
];

function topicFromPath(pathname: string, topicParam: string | null): KalshiTopicId {
  if (topicParam && KALSHI_TOPICS.some((t) => t.id === topicParam)) {
    return topicParam as KalshiTopicId;
  }
  if (pathname.startsWith("/markets")) return "trending";
  return "trending";
}

function KalshiSiteHeaderInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { token, isReady } = useAuth();
  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const [menuOpen, setMenuOpen] = useState(false);

  const activeTopic = topicFromPath(pathname, searchParams.get("topic"));

  const goTopic = useCallback(
    (id: KalshiTopicId) => {
      const params = new URLSearchParams();
      if (id !== "trending") params.set("topic", id);
      const qs = params.toString();
      router.push(qs ? `/markets?${qs}` : "/markets");
    },
    [router],
  );

  const onSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const params = new URLSearchParams(searchParams.toString());
      if (q.trim()) params.set("q", q.trim());
      else params.delete("q");
      router.push(`/markets?${params.toString()}`);
    },
    [q, router, searchParams],
  );

  if (pathname.startsWith("/admin")) {
    return null;
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-bg">
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-3 px-4 sm:px-6">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-2"
          aria-label="AlphaEdge home"
          data-tour="logo"
        >
          <span className="grid h-8 w-8 place-items-center rounded-full bg-accent font-mono text-xs font-bold text-white">
            AE
          </span>
          <span className="hidden text-base font-semibold tracking-tight text-text lg:inline">
            AlphaEdge
          </span>
        </Link>

        <nav className="hidden items-center gap-0.5 md:flex" aria-label="Primary">
          {NAV_LINKS.map((link) => {
            const active =
              pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                data-tour={link.tour}
                className={cn(
                  "rounded-pill px-3 py-1.5 text-sm font-medium transition",
                  active
                    ? "bg-surface-2 text-text"
                    : "text-muted hover:bg-surface hover:text-text",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <form onSubmit={onSearch} className="ml-auto hidden min-w-0 max-w-xs flex-1 xl:block">
          <label className="flex h-9 items-center gap-2 rounded-pill bg-surface px-3.5 text-sm text-muted-2 focus-within:ring-1 focus-within:ring-accent">
            <SearchIcon />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full bg-transparent text-sm text-text placeholder:text-muted-2 focus:outline-none"
              placeholder="Search markets"
              aria-label="Search markets"
            />
          </label>
        </form>

        <div className="ml-auto flex items-center gap-2 xl:ml-0">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("ae:tour"))}
            className="hidden rounded-pill border border-border px-3 py-1.5 text-xs font-semibold text-muted transition hover:border-accent hover:text-text sm:inline"
            title="Replay the product tour"
          >
            Tour
          </button>
          <LevelChip />
          {isReady && token ? (
            <Link
              href="/portfolio"
              data-tour="nav-portfolio"
              className="rounded-pill bg-accent px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-accent-active"
            >
              Portfolio
            </Link>
          ) : (
            <>
              <Link
                href="/auth/login"
                className="hidden rounded-pill px-3 py-1.5 text-sm font-semibold text-muted hover:text-text sm:inline"
              >
                Log in
              </Link>
              <Link
                href="/auth/signup"
                data-tour="nav-portfolio"
                className="rounded-pill bg-accent px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-accent-active"
              >
                Sign up
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-pill text-muted hover:text-text md:hidden"
            aria-label="Open menu"
            aria-expanded={menuOpen}
          >
            <MenuIcon />
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav
          className="border-t border-border bg-bg px-4 py-2 md:hidden"
          aria-label="Primary mobile"
        >
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
        </nav>
      )}

      {pathname.startsWith("/markets") && (
        <div className="border-t border-border bg-bg">
          <div className="no-scrollbar mx-auto flex max-w-[1280px] gap-1 overflow-x-auto px-4 py-2 sm:px-6">
            {KALSHI_TOPICS.map((topic) => {
              const active = activeTopic === topic.id;
              return (
                <button
                  key={topic.id}
                  type="button"
                  onClick={() => goTopic(topic.id)}
                  className={cn(
                    "shrink-0 rounded-pill px-4 py-1.5 text-sm font-semibold transition",
                    active
                      ? "bg-text text-bg"
                      : "text-muted hover:bg-surface hover:text-text",
                  )}
                >
                  {topic.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
}

export function KalshiSiteHeader() {
  return (
    <Suspense fallback={<header className="h-14 border-b border-border bg-bg" />}>
      <KalshiSiteHeaderInner />
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

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
    </svg>
  );
}
