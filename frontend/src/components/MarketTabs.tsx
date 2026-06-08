"use client";

import { useState } from "react";
import {
  cents,
  timeAgo,
  toneClass,
  type Market,
} from "@/lib/mock-data";
import { cn } from "@/lib/cn";

type Tab = "Activity" | "Holders" | "Comments" | "About";
const TABS: Tab[] = ["Activity", "Holders", "Comments", "About"];

export function MarketTabs({ market }: { market: Market }) {
  const [tab, setTab] = useState<Tab>("Activity");

  return (
    <div className="rounded-2xl border border-border bg-surface">
      <div className="flex gap-1 border-b border-border px-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "relative px-3 py-3 text-sm font-semibold transition",
              tab === t ? "text-text" : "text-muted hover:text-text",
            )}
          >
            {t}
            {tab === t && (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />
            )}
          </button>
        ))}
      </div>

      <div className="p-4">
        {tab === "Activity" && (
          <ul className="space-y-2">
            {market.trades.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm transition hover:bg-surface-2"
              >
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                    t.side === "YES"
                      ? "bg-primary-dim text-primary"
                      : "bg-danger-dim text-danger",
                  )}
                >
                  {t.side}
                </span>
                <span className="min-w-0 flex-1 truncate text-muted">
                  <span className="font-semibold text-text">@{t.user}</span> {t.side === "YES" ? "bought" : "sold"}{" "}
                  {t.shares} {t.outcome} @ {cents(t.price)}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-muted-2">
                  {timeAgo(t.tsOffsetSec)}
                </span>
              </li>
            ))}
          </ul>
        )}

        {tab === "Holders" && (
          <ul className="space-y-2">
            {market.holders.map((h, i) => (
              <li key={`${h.user}-${i}`} className="flex items-center gap-3 text-sm">
                <span
                  className={cn(
                    "grid h-7 w-7 place-items-center rounded-full bg-surface-2 text-[11px] font-bold",
                    toneClass(h.tone),
                  )}
                >
                  {h.user.slice(0, 2).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1 truncate font-semibold text-text">
                  @{h.user}
                </span>
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                    h.side === "YES"
                      ? "bg-primary-dim text-primary"
                      : "bg-danger-dim text-danger",
                  )}
                >
                  {h.side}
                </span>
                <span className="w-24 text-right font-mono text-xs text-muted">
                  {h.shares.toLocaleString()} sh
                </span>
              </li>
            ))}
          </ul>
        )}

        {tab === "Comments" && (
          <ul className="space-y-3">
            {market.comments.map((c) => (
              <li key={c.id} className="rounded-lg border border-border bg-surface-2 p-3">
                <div className="flex items-center justify-between">
                  <span className={cn("text-sm font-bold", toneClass(c.tone))}>
                    @{c.user}
                  </span>
                  <span className="font-mono text-[11px] text-muted-2">
                    {timeAgo(c.tsOffsetSec)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-text">{c.body}</p>
                <div className="mt-2 text-xs text-muted">♥ {c.likes}</div>
              </li>
            ))}
            <li className="flex gap-2">
              <input
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text placeholder:text-muted-2 focus:border-accent focus:outline-none"
                placeholder="Add a comment…"
              />
              <button className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-semibold text-text">
                Post
              </button>
            </li>
          </ul>
        )}

        {tab === "About" && (
          <div className="space-y-4 text-sm">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-2">
                Description
              </h4>
              <p className="mt-1 leading-relaxed text-text">{market.description}</p>
            </div>
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-2">
                Resolution
              </h4>
              <p className="mt-1 leading-relaxed text-text">{market.resolution}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Volume" value={`$${market.volume.toLocaleString()}`} />
              <Stat label="Traders" value={market.traders.toLocaleString()} />
              <Stat label="Sub-markets" value={String(market.marketCount)} />
              <Stat label="Brier" value={market.forecast.brier.toFixed(3)} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2 p-2.5">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-bold text-text">{value}</div>
    </div>
  );
}
