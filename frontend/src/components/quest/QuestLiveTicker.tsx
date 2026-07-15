"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchSignalEvents } from "@/lib/activity-api";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { marketHref } from "@/lib/market-href";
import {
  buildSignalRailRows,
  tickerFreshnessWindowMs,
  type SignalRailRow,
} from "@/lib/signal-rail";

// Global recent-signal ticker. Every row is a persisted event with its actual
// direction, magnitude, and age. Quiet periods render fewer rows without
// replaying or fabricating activity.

export function QuestLiveTicker() {
  const [rows, setRows] = useState<SignalRailRow[]>([]);

  useEffect(() => {
    let dead = false;
    let timer: ReturnType<typeof setInterval>;

    const load = async () => {
      try {
        const [events, markets] = await Promise.all([
          fetchSignalEvents({ limit: 48, dedupeWindowMinutes: 10 }),
          fetchMarkets({}),
        ]);
        if (dead) return;
        setRows(buildSignalRailRows(events, markets, {
          limit: 12,
          maxAgeMs: tickerFreshnessWindowMs(process.env.NEXT_PUBLIC_TICKER_MAX_AGE_HOURS),
        }));
      } catch {
        /* keep last good rows */
      }
    };

    void load();
    timer = setInterval(load, 15000);
    return () => {
      dead = true;
      clearInterval(timer);
    };
  }, []);

  if (rows.length === 0) return null;

  return (
    <div className="sticky bottom-0 z-30 hidden border-t border-border bg-bg/95 backdrop-blur lg:block">
      <div className="group flex items-center gap-2 overflow-hidden py-1.5">
        <span className="shrink-0 pl-4 pr-2 font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
          ● Recent
        </span>
        <div className="flex min-w-0 flex-1 overflow-hidden">
          <div className="flex min-w-0 items-center gap-8 overflow-hidden whitespace-nowrap px-2">
            {rows.map((r) => {
              const inner = (
                <span className="inline-flex items-center gap-1.5 text-[11px]">
                  <span
                    className={
                      r.direction === "UP"
                        ? "font-mono font-semibold text-primary"
                        : r.direction === "DOWN"
                          ? "font-mono font-semibold text-danger"
                          : "font-mono font-semibold text-muted"
                    }
                  >
                    {r.direction} {r.value}
                  </span>
                  <span className="max-w-[220px] truncate font-medium text-text">{r.title}</span>
                  <span className="text-muted">· {r.label}</span>
                  <span className="font-mono text-muted-2">· {r.age}</span>
                </span>
              );
              return (
                <Link key={r.key} href={marketHref(r.slug)} className="transition hover:opacity-80">
                  {inner}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 border-l border-border px-3 text-muted-2">
          <a
            href="https://x.com"
            target="_blank"
            rel="noreferrer"
            aria-label="X"
            className="grid h-7 w-7 place-items-center rounded-md transition hover:bg-surface-2 hover:text-text"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.727-8.924L1.254 2.25H8.08l4.259 5.632 5.905-5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
          </a>
          <a
            href="https://t.me"
            target="_blank"
            rel="noreferrer"
            aria-label="Telegram"
            className="grid h-7 w-7 place-items-center rounded-md transition hover:bg-surface-2 hover:text-text"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M9.78 15.44 9.5 19.2c.4 0 .57-.17.78-.37l1.87-1.8 3.88 2.85c.71.39 1.22.19 1.41-.66l2.56-12.02c.23-1.05-.38-1.46-1.07-1.2L3.3 10.1c-1.02.4-.98.95-.17 1.2l4.6 1.44 10.68-6.73c.5-.3.96-.14.58.19z" />
            </svg>
          </a>
          <a
            href="https://discord.com"
            target="_blank"
            rel="noreferrer"
            aria-label="Discord"
            className="grid h-7 w-7 place-items-center rounded-md transition hover:bg-surface-2 hover:text-text"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M20.317 4.37a19.8 19.8 0 0 0-4.885-1.515.07.07 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.3 18.3 0 0 0-5.487 0 12.6 12.6 0 0 0-.617-1.25.08.08 0 0 0-.079-.037A19.7 19.7 0 0 0 3.677 4.37a.09.09 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.08.08 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.08.08 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.08.08 0 0 0-.041-.111 13.1 13.1 0 0 1-1.872-.892.08.08 0 0 1-.008-.127c.126-.094.252-.192.373-.291a.08.08 0 0 1 .078-.01c3.928 1.793 8.18 1.793 12.062 0a.08.08 0 0 1 .079.01c.12.098.247.198.373.291a.08.08 0 0 1-.006.127 12.3 12.3 0 0 1-1.873.892.08.08 0 0 0-.041.112c.36.698.772 1.362 1.225 1.993a.08.08 0 0 0 .084.028 19.8 19.8 0 0 0 6.002-3.03.08.08 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.06.06 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}
