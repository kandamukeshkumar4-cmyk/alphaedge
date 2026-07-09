"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";

type ScheduleMarket = {
  outcome: string;
  slug: string;
  implied_yes: number;
  status?: string;
};

type ScheduleMatch = {
  fixture_id: number;
  home_team: string;
  away_team: string;
  kickoff_at: string;
  venue: string;
  stage_name: string;
  p_home_win: number;
  p_draw: number;
  p_away_win: number;
  home_score?: number | null;
  away_score?: number | null;
  markets: ScheduleMarket[];
};

type ScheduleResponse = {
  matches: ScheduleMatch[];
};

function formatKickoff(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function groupLabel(stageName: string) {
  if (stageName === "Group Stage") return "Group Stage";
  return stageName;
}

function formatCountdown(ms: number) {
  const totalHours = Math.max(0, Math.floor(ms / (60 * 60 * 1000)));
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  if (days > 0) return `${days}d ${hours}h`;
  const minutes = Math.floor((ms % (60 * 60 * 1000)) / (60 * 1000));
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function matchStatusLabel(match: ScheduleMatch, now: Date): string | null {
  const kickoff = new Date(match.kickoff_at);
  const liveEnd = new Date(kickoff.getTime() + 2 * 60 * 60 * 1000);
  const allResolved =
    match.markets.length > 0 && match.markets.every((m) => m.status === "resolved");

  if (allResolved) {
    if (match.home_score != null && match.away_score != null) {
      return `FINAL · ${match.home_score}-${match.away_score}`;
    }
    return "FINAL";
  }

  if (now >= kickoff && now <= liveEnd) {
    const minutes = Math.floor((now.getTime() - kickoff.getTime()) / 60000);
    return `LIVE · ${minutes}'`;
  }

  if (now < kickoff) {
    return `UPCOMING · ${formatCountdown(kickoff.getTime() - now.getTime())}`;
  }

  return null;
}

function statusBadgeClass(label: string) {
  if (label.startsWith("LIVE")) return "border-rose-400/40 bg-rose-400/10 text-rose-300";
  if (label.startsWith("FINAL")) return "border-muted/40 bg-muted/10 text-muted";
  return "border-gold/40 bg-gold/10 text-gold";
}

function ProbBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] text-muted">
        <span>{label}</span>
        <span className="font-mono font-bold text-text">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-border">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function WC2026Schedule() {
  const [matches, setMatches] = useState<ScheduleMatch[]>([]);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (!API_BASE) return;
    fetch(`${API_BASE}/api/v1/wc2026/schedule?days=7&stage=group`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: ScheduleResponse | null) => {
        if (data?.matches) {
          setMatches(data.matches);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  if (!matches.length) {
    return null;
  }

  return (
    <section id="wc2026-schedule" className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <h2 className="text-lg font-black tracking-tight text-text">World Cup 2026 — Next 7 Days</h2>
        <span className="text-xs font-semibold text-muted">{matches.length} fixtures</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {matches.map((match) => {
          const homeMarket = match.markets.find((m) => m.outcome === "home_win");
          const drawMarket = match.markets.find((m) => m.outcome === "draw");
          const awayMarket = match.markets.find((m) => m.outcome === "away_win");
          const statusLabel = matchStatusLabel(match, now);

          return (
            <article
              key={match.fixture_id}
              className="min-w-[280px] max-w-[280px] shrink-0 rounded-2xl border border-border bg-surface p-4 shadow-card"
            >
              <div className="mb-3 space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-black text-text">
                    {match.home_team} vs {match.away_team}
                  </p>
                  {statusLabel && (
                    <span
                      className={cn(
                        "shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide",
                        statusBadgeClass(statusLabel),
                      )}
                    >
                      {statusLabel}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted">
                  {formatKickoff(match.kickoff_at)} · {match.venue}
                </p>
                <p className="text-[11px] font-bold uppercase tracking-wide text-gold">
                  {groupLabel(match.stage_name)}
                </p>
              </div>

              <div className="mb-4 space-y-2">
                <ProbBar label="Home win" value={match.p_home_win} tone="bg-emerald-400" />
                <ProbBar label="Draw" value={match.p_draw} tone="bg-muted" />
                <ProbBar label="Away win" value={match.p_away_win} tone="bg-sky-400" />
              </div>

              <div className="flex flex-wrap gap-2">
                {homeMarket && (
                  <Link
                    href={marketHref(homeMarket.slug)}
                    className="rounded-md border border-border px-2.5 py-1 text-[11px] font-black text-text transition hover:border-accent"
                  >
                    Trade {match.home_team.split(" ").pop()}
                  </Link>
                )}
                {drawMarket && (
                  <Link
                    href={marketHref(drawMarket.slug)}
                    className="rounded-md border border-border px-2.5 py-1 text-[11px] font-black text-text transition hover:border-accent"
                  >
                    Trade Draw
                  </Link>
                )}
                {awayMarket && (
                  <Link
                    href={marketHref(awayMarket.slug)}
                    className="rounded-md border border-border px-2.5 py-1 text-[11px] font-black text-text transition hover:border-accent"
                  >
                    Trade {match.away_team.split(" ").pop()}
                  </Link>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
