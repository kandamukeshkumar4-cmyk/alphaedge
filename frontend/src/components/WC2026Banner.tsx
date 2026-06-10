"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";

type ScheduleMatch = {
  fixture_id: number;
  home_team: string;
  away_team: string;
  kickoff_at: string;
  markets: { outcome: string; slug: string; implied_yes: number }[];
};

type ScheduleResponse = {
  matches: ScheduleMatch[];
};

function formatKickoffLocal(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function WC2026Banner() {
  const [matches, setMatches] = useState<ScheduleMatch[]>([]);

  useEffect(() => {
    if (!API_BASE) return;
    fetch(`${API_BASE}/api/v1/wc2026/schedule?days=1`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: ScheduleResponse | null) => {
        if (data?.matches?.length) {
          setMatches(data.matches);
        }
      })
      .catch(() => {});
  }, []);

  if (!matches.length) {
    return null;
  }

  const activeMarkets = matches.reduce((sum, m) => sum + m.markets.length, 0);
  const spotlight = matches[0];

  function scrollToSchedule() {
    document.getElementById("wc2026-schedule")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <button
      type="button"
      onClick={scrollToSchedule}
      className="w-full rounded-xl border border-gold/30 bg-gradient-to-r from-gold/10 via-surface to-surface-2 px-4 py-2.5 text-left text-sm text-text transition hover:border-gold/50"
    >
      <span className="font-black">🏆 FIFA World Cup 2026 is LIVE</span>
      <span className="text-muted">
        {" "}
        · {activeMarkets || matches.length * 3} active markets · Today: {spotlight.home_team} vs{" "}
        {spotlight.away_team} {formatKickoffLocal(spotlight.kickoff_at)}
      </span>
    </button>
  );
}
