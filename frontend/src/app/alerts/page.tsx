"use client";

// Alerts desk — dispatched alerts (T09) plus the raw engine-room event stream
// (diff engine, whale deltas, news arrivals, alignment triggers).
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAlerts,
  fetchSignalEvents,
  type AlertItem,
  type SignalEventItem,
} from "@/lib/activity-api";
import { cn } from "@/lib/cn";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { DEMO_ALERTS, DEMO_EVENTS } from "@/lib/demo-data";
import { DemoChip } from "@/components/quest/DemoChip";

function timeLabel(iso: string): string {
  const ts = Date.parse(iso);
  if (!ts) return "";
  const mins = Math.max(0, Math.round((Date.now() - ts) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

const EVENT_TONE: Record<string, string> = {
  price_jump: "bg-primary-dim text-primary",
  orderbook_flip: "bg-secondary-dim text-secondary",
  volume_surge: "bg-accent-dim text-accent-bright",
  whale_delta: "bg-accent-dim text-accent-bright",
  news_arrival: "bg-surface-3 text-text",
  alignment: "bg-primary-dim text-primary",
  instability_shift: "bg-danger-dim text-danger",
};

export default function AlertsPage() {
  const [tab, setTab] = useState<"alerts" | "events">("alerts");
  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [events, setEvents] = useState<SignalEventItem[] | null>(null);
  const [demo, setDemo] = useState(false);

  // Initial backfill from REST. Live updates arrive over the WS feed below,
  // so we don't re-poll on an interval — but keep a slow safety refresh for the
  // engine-room events (raw signal_events aren't on the WS feed, only alerts).
  useEffect(() => {
    let dead = false;
    const load = async () => {
      const [a, e] = await Promise.all([fetchAlerts(), fetchSignalEvents()]);
      if (dead) return;
      if (a.length === 0 && e.length === 0) {
        setAlerts(DEMO_ALERTS);
        setEvents(DEMO_EVENTS);
        setDemo(true);
      } else {
        setAlerts(a);
        setEvents(e);
        setDemo(false);
      }
    };
    void load();
    const id = setInterval(() => void fetchSignalEvents().then((e) => {
      if (!dead && e.length > 0) setEvents(e);
    }).catch(() => {}), 60_000);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, []);

  // Real-time: prepend dispatched alerts the moment they fire (no polling lag).
  useActivityFeed({
    onAlert: (frame) => {
      setDemo(false);
      setAlerts((prev) => {
        const live = (prev ?? []).filter((a) => !a.id.startsWith("demo-"));
        const item: AlertItem = {
          id: `ws-${frame.ts ?? Date.now()}-${live.length}`,
          alert_type: String(frame.type ?? "alert"),
          message: String(frame.message ?? ""),
          payload: frame as Record<string, unknown>,
          acknowledged: false,
          created_at: new Date().toISOString(),
        };
        return [item, ...live].slice(0, 100);
      });
    },
  });

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-4 py-6 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">Alerts</h1>
      <p className="mt-1 text-sm text-muted">
        Everything the pipeline flags — alignment triggers, new briefs, and the raw
        signal events behind them. Research only, paper trading only.
      </p>
      {demo && (
        <p className="mt-3 flex items-center gap-2 rounded-lg border border-secondary/30 bg-secondary-dim px-4 py-2.5 text-xs text-secondary">
          <DemoChip />
          Sample activity — live alerts stream in when the backend and workers run.
        </p>
      )}

      <div className="mt-5 flex gap-1 border-b border-border pb-px">
        {(
          [
            { id: "alerts", label: "Dispatched alerts" },
            { id: "events", label: "Engine room" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-t-lg px-4 py-2 text-sm font-semibold transition",
              tab === t.id
                ? "border-b-2 border-accent-bright text-text"
                : "text-muted hover:text-text",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "alerts" &&
        (alerts === null ? (
          <ListSkeleton />
        ) : alerts.length === 0 ? (
          <EmptyState
            title="No alerts yet"
            body="Alerts fire when ≥3 signal layers align on one market or a new brief publishes. Keep the backend and workers running and they land here automatically."
          />
        ) : (
          <ul className="mt-4 space-y-2">
            {alerts.map((a) => (
              <li key={a.id} className="rounded-xl border border-border bg-surface px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase text-accent-bright">
                    {a.alert_type.replaceAll("_", " ")}
                  </span>
                  <span className="ml-auto text-[10px] text-muted-2">
                    {timeLabel(a.created_at)}
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-text">{a.message}</p>
              </li>
            ))}
          </ul>
        ))}

      {tab === "events" &&
        (events === null ? (
          <ListSkeleton />
        ) : events.length === 0 ? (
          <EmptyState
            title="The engine room is quiet"
            body="Price jumps, order-book flips, volume surges, whale deltas and news arrivals stream in here as the diff engine detects them."
          />
        ) : (
          <ul className="mt-4 space-y-2">
            {events.map((e) => (
              <li key={e.id} className="rounded-xl border border-border bg-surface px-4 py-3">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                      EVENT_TONE[e.signal_type] ?? "bg-surface-3 text-muted",
                    )}
                  >
                    {e.signal_type.replaceAll("_", " ")}
                  </span>
                  <span className="text-[10px] uppercase text-muted-2">{e.platform}</span>
                  <span className="ml-auto text-[10px] text-muted-2">
                    {timeLabel(e.created_at)}
                  </span>
                </div>
                <Link
                  href={`/markets/${e.market_id}`}
                  className="mt-1.5 block font-mono text-sm text-text hover:text-accent-bright"
                >
                  {e.market_id}
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </main>
  );
}

function ListSkeleton() {
  return (
    <div className="mt-4 space-y-2">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="rounded-xl border border-border bg-surface px-4 py-3">
          <div className="skeleton h-3 w-24 rounded" />
          <div className="skeleton mt-2 h-4 w-2/3 rounded" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-6 rounded-xl border border-border bg-surface p-8 text-center">
      <p className="text-sm font-semibold text-text">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">{body}</p>
    </div>
  );
}
