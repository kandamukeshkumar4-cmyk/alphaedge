"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";

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
  markets: { outcome: string; slug: string; implied_yes: number }[];
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

          return (
            <article
              key={match.fixture_id}
              className="min-w-[280px] max-w-[280px] shrink-0 rounded-2xl border border-border bg-surface p-4 shadow-card"
            >
              <div className="mb-3 space-y-1">
                <p className="text-sm font-black text-text">
                  {match.home_team} vs {match.away_team}
                </p>
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
                    href={`/markets/${homeMarket.slug}`}
                    className="rounded-md border border-border px-2.5 py-1 text-[11px] font-black text-text transition hover:border-accent"
                  >
                    Trade {match.home_team.split(" ").pop()}
                  </Link>
                )}
                {drawMarket && (
                  <Link
                    href={`/markets/${drawMarket.slug}`}
                    className="rounded-md border border-border px-2.5 py-1 text-[11px] font-black text-text transition hover:border-accent"
                  >
                    Trade Draw
                  </Link>
                )}
                {awayMarket && (
                  <Link
                    href={`/markets/${awayMarket.slug}`}
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
