"use client";

import { useEffect, useRef, useState } from "react";
import { MARKETS } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

type Tick = {
  id: number;
  user: string;
  side: "YES" | "NO";
  shares: number;
  market: string;
  age: string;
};

const USERS = [
  "alpha_quant",
  "edgeHunter",
  "marketGuru",
  "brierBeast",
  "kelly_max",
  "lineMover",
  "sharpKing",
  "deltaOne",
];

// Deterministic seed so the first paint matches between server and client.
function seedTicks(): Tick[] {
  return MARKETS.slice(0, 6).map((m, i) => ({
    id: i,
    user: USERS[i % USERS.length],
    side: i % 2 === 0 ? "YES" : "NO",
    shares: 25 + i * 17,
    market: m.title,
    age: `${i + 1}m ago`,
  }));
}

export function LiveTicker() {
  const [ticks, setTicks] = useState<Tick[]>(seedTicks);
  const [mounted, setMounted] = useState(false);
  const idRef = useRef(1000);

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(() => {
      const m = MARKETS[Math.floor(Math.random() * MARKETS.length)];
      const next: Tick = {
        id: idRef.current++,
        user: USERS[Math.floor(Math.random() * USERS.length)],
        side: Math.random() > 0.5 ? "YES" : "NO",
        shares: Math.round(5 + Math.random() * 480),
        market: m.title,
        age: "now",
      };
      setTicks((prev) => [next, ...prev].slice(0, 7));
    }, 2600);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[12px] font-black uppercase tracking-[0.12em] text-text">
          Live trades
        </h2>
        <span className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.1em] text-muted">
          <span
            className={cn(
              "h-2 w-2 rounded-full bg-accent",
              mounted && "animate-pulse-soft",
            )}
          />
          live
        </span>
      </div>
      <ul className="mt-3 space-y-2.5">
        {ticks.map((t, i) => (
          <li
            key={t.id}
            className={cn(
              "flex items-center gap-2 text-xs",
              i === 0 && mounted && "animate-ticker-in",
            )}
          >
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-mono text-[10px] font-black",
                t.side === "YES"
                  ? "bg-primary-dim text-primary"
                  : "bg-danger-dim text-danger",
              )}
            >
              {t.side}
            </span>
            <span className="min-w-0 flex-1 truncate text-muted">
              <span className="text-text">@{t.user}</span> · {t.shares}{" "}
              <span className="truncate">{t.market}</span>
            </span>
            <span className="shrink-0 font-mono text-[10px] text-muted-2">{t.age}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
