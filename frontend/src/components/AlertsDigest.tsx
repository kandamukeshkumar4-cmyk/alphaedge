"use client";

// Y02 — Alerts digest card (backend L02, GET /api/v1/alerts/digest?window=).
// Per-family counts + top-moved markets over a 24h/7d window toggle. PUBLIC GET,
// read-only, notify only — a digest of signal activity, never a trade. Honest
// empty + unreachable states; nothing is fabricated. Fetches once per window
// change (abort on change), no raw poll loop.
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import {
  buildAlertsDigestView,
  DIGEST_WINDOWS,
  digestFamilyLabel,
  digestWindowLabel,
  fetchAlertsDigest,
  type AlertsDigestView,
  type DigestWindow,
} from "@/lib/alerts-digest-api";

function WindowToggle({
  window,
  onChange,
}: {
  window: DigestWindow;
  onChange: (w: DigestWindow) => void;
}) {
  return (
    <div className="flex gap-1" role="group" aria-label="Digest window">
      {DIGEST_WINDOWS.map((w) => (
        <button
          key={w}
          type="button"
          aria-pressed={w === window}
          aria-label={digestWindowLabel(w)}
          onClick={() => onChange(w)}
          className={cn(
            "rounded-lg px-2.5 py-1 font-mono text-[11px] font-bold uppercase transition",
            w === window
              ? "bg-accent text-bg"
              : "border border-border text-muted hover:text-text",
          )}
        >
          {w}
        </button>
      ))}
    </div>
  );
}

function DigestSkeleton() {
  return (
    <div aria-hidden>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton h-7 w-28 rounded-lg" />
        ))}
      </div>
      <div className="skeleton mt-4 h-12 w-full rounded" />
    </div>
  );
}

function DigestBody({ view }: { view: AlertsDigestView }) {
  if (!view.reachable) {
    return (
      <p className="text-xs text-muted">
        The digest API did not answer — start the backend or set NEXT_PUBLIC_API_URL to see the
        window summary.
      </p>
    );
  }
  if (view.empty) {
    return (
      <p className="text-xs text-muted">
        No alerts fired in this window. Nothing is fabricated — switch to a wider window or check
        back as the pipeline flags new signals.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="list" aria-label="Alert counts by family">
        {view.familyRows.map((row) => (
          <span
            key={row.key}
            role="listitem"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-2/60 px-2.5 py-1"
          >
            <span className="text-[11px] font-semibold text-text">{row.label}</span>
            <span className="rounded bg-accent-dim px-1.5 py-0.5 font-mono text-[10px] font-black text-accent-bright">
              <AnimatedNumber value={row.count} format={(n) => String(Math.round(n))} />
            </span>
          </span>
        ))}
      </div>

      {view.movers.length > 0 ? (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
            Top movers
          </p>
          <ul className="mt-2 space-y-1.5">
            {view.movers.map((m) => (
              <li
                key={m.slug}
                className="flex items-center gap-2 rounded-lg border border-border/60 bg-surface-2/40 px-3 py-1.5"
              >
                <Link
                  href={marketHref(m.slug)}
                  className="min-w-0 flex-1 truncate font-mono text-xs font-semibold text-text hover:text-accent-bright"
                >
                  {m.slug}
                </Link>
                {m.families.map((fam) => (
                  <span
                    key={fam}
                    className="hidden shrink-0 rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-bold uppercase text-muted-2 sm:inline"
                  >
                    {digestFamilyLabel(fam)}
                  </span>
                ))}
                <span className="shrink-0 rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] font-black text-muted">
                  <AnimatedNumber value={m.signalCount} format={(n) => String(Math.round(n))} />
                  <span className="ml-1 font-sans font-semibold text-muted-2">
                    signal{m.signalCount === 1 ? "" : "s"}
                  </span>
                </span>
                {m.lastLabel ? (
                  <span className="hidden shrink-0 text-[10px] text-muted-2 sm:inline">
                    {m.lastLabel}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </div>
  );
}

export function AlertsDigest() {
  const [window, setWindow] = useState<DigestWindow>("24h");
  const [view, setView] = useState<AlertsDigestView | null>(null);

  useEffect(() => {
    let dead = false;
    const ctrl = new AbortController();
    setView(null);
    void fetchAlertsDigest(window, { top: 5, signal: ctrl.signal }).then((raw) => {
      if (dead || ctrl.signal.aborted) return;
      setView(buildAlertsDigestView(raw));
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [window]);

  return (
    <section aria-label="Alerts digest" className="mb-6">
      <MotionReveal className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-black tracking-tight text-text">Digest</h2>
          {view && view.reachable && !view.empty ? (
            <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] font-bold text-muted">
              <AnimatedNumber value={view.total} format={(n) => String(Math.round(n))} /> alert
              {view.total === 1 ? "" : "s"}
            </span>
          ) : null}
          <div className="ml-auto">
            <WindowToggle window={window} onChange={setWindow} />
          </div>
        </div>
        {view === null ? <DigestSkeleton /> : <DigestBody view={view} />}
      </MotionReveal>
    </section>
  );
}
