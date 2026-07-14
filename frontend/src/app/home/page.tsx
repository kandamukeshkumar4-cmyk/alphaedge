"use client";

// Z01 — Personalized home dashboard (backend M01, GET /api/v1/home). ONE public
// GET (optional JWT) composes the "your intelligence" landing: recent signals
// with H03 evidence, the L02 digest summary, I02/J03 model-A/B readiness, and
// active markets by recent movement. Signed in, it also renders the watchlist strip;
// anon shows an honest "sign in to personalize" for that section only. Research
// only, paper trading only — notify surfaces never trade. Fetch-on-load only
// (no poll loop).
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { PageHeader, PageShell, Panel } from "@/components/ui/kit";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import {
  buildHomeView,
  fetchHome,
  type HomeSignalRow,
  type HomeView,
} from "@/lib/home-api";

function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden className="space-y-2">
      <div className="skeleton h-4 w-1/3 rounded" />
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-12 w-full rounded-lg" />
      ))}
    </div>
  );
}

function SignalList({ rows, emptyBody }: { rows: HomeSignalRow[]; emptyBody: string }) {
  if (rows.length === 0) {
    return <p className="text-xs leading-relaxed text-muted">{emptyBody}</p>;
  }
  return (
    <ul className="space-y-3">
      {rows.map((row, i) => (
        <li key={row.id}>
          <MotionReveal delay={Math.min(i, 6) * 0.04} className="rounded-lg border border-border/60 bg-surface-2/40 p-3">
            <div className="flex items-center gap-2">
              <Link
                href={marketHref(row.slug)}
                className="min-w-0 flex-1 truncate font-mono text-xs font-semibold text-text hover:text-accent-bright"
              >
                {row.slug}
              </Link>
              <span className="shrink-0 rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-accent-bright">
                {row.familyLabel}
              </span>
              <span className="shrink-0 text-[10px] text-muted-2">{row.timeLabel}</span>
            </div>
            {row.evidence ? <SignalEvidenceBlock evidence={row.evidence} /> : null}
          </MotionReveal>
        </li>
      ))}
    </ul>
  );
}

function WatchlistStrip({ view, authed }: { view: HomeView; authed: boolean }) {
  if (!authed) {
    return (
      <Panel title="Your watchlist" className="mb-6">
        <p className="text-sm font-semibold text-text">Sign in to personalize your home</p>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">
          Your watchlist and its alerts are saved to your account. Sign in, then track markets to
          see their count and recent signals here.
        </p>
        <Link
          href="/auth/login?next=/home"
          className="mt-4 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          Sign in
        </Link>
      </Panel>
    );
  }

  const count = view.watchlistCount ?? 0;
  return (
    <Panel
      title="Your watchlist"
      action={
        <Link href="/watchlist" className="text-[11px] font-semibold text-accent hover:underline">
          Manage →
        </Link>
      }
      className="mb-6"
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-2xl font-black tabular-nums text-text">
          <AnimatedNumber value={count} format={(n) => String(Math.round(n))} />
        </span>
        <span className="text-xs text-muted">market{count === 1 ? "" : "s"} tracked</span>
      </div>
      <div className="mt-4">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
          Recent watchlist alerts
        </p>
        <SignalList
          rows={view.watchlistAlerts}
          emptyBody={
            count === 0
              ? "You are not tracking any markets yet. Track markets to scope alerts to what you care about."
              : "No recent alerts on the markets you track. Nothing is fabricated — check back as the pipeline flags new signals."
          }
        />
      </div>
    </Panel>
  );
}

function DigestSummary({ view }: { view: HomeView }) {
  const d = view.digest;
  return (
    <Panel
      title="Digest"
      action={
        <Link href="/alerts" className="text-[11px] font-semibold text-accent hover:underline">
          All alerts →
        </Link>
      }
    >
      {!d.reachable ? (
        <p className="text-xs text-muted">Digest unreachable — live intelligence needs the backend API.</p>
      ) : d.empty ? (
        <p className="text-xs text-muted">
          No alerts fired in the {d.windowLabel} window. Nothing is fabricated — check back as new
          signals land.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted">
            <span className="font-mono font-bold text-text">
              <AnimatedNumber value={d.total} format={(n) => String(Math.round(n))} />
            </span>{" "}
            alert{d.total === 1 ? "" : "s"} in the {d.windowLabel} window.
          </p>
          <div className="mt-3 flex flex-wrap gap-2" role="list" aria-label="Alert counts by family">
            {d.familyRows.map((row) => (
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
        </>
      )}
    </Panel>
  );
}

function ModelStatus({ view }: { view: HomeView }) {
  const m = view.modelAb;
  return (
    <Panel
      title="Model A/B readiness"
      action={
        <Link href="/eval" className="text-[11px] font-semibold text-accent hover:underline">
          Model eval →
        </Link>
      }
    >
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="text-muted">Resolved markets</span>
        <span className="font-mono font-bold text-text">{m.resolvedLabel}</span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-3" aria-hidden>
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500"
          style={{ width: `${m.progressPct}%` }}
        />
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-muted-2">
        {m.state === "not-ready"
          ? `${m.remaining} more resolved market${m.remaining === 1 ? "" : "s"} until the walk-forward A/B is eligible. The deployed default (${m.defaultModelLabel}) is never flipped here.`
          : `Default model ${m.defaultModelLabel} — analysis only, the deployed default is unchanged.`}
      </p>
    </Panel>
  );
}

function TopMarkets({ view }: { view: HomeView }) {
  return (
    <Panel
      title="Active markets"
      action={
        <Link href="/markets" className="text-[11px] font-semibold text-accent hover:underline">
          All markets →
        </Link>
      }
    >
      {view.topMarkets.length === 0 ? (
        <p className="text-xs text-muted">
          No markets to rank yet — the catalog is empty or the API is unreachable.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {view.topMarkets.map((m) => (
            <li key={m.slug}>
              <Link
                href={marketHref(m.slug)}
                className="flex items-center gap-2 rounded-lg border border-border/60 bg-surface-2/40 px-3 py-2 transition hover:border-border-light"
              >
                <span className="min-w-0 flex-1 truncate text-sm font-semibold text-text">
                  {m.title}
                </span>
                {m.yesLabel ? (
                  <span className="shrink-0 font-mono text-xs font-black text-primary">{m.yesLabel}</span>
                ) : null}
                <span className="shrink-0 font-mono text-[11px] text-muted-2">{m.volumeLabel}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default function HomePage() {
  const { token, isReady } = useAuth();
  const [view, setView] = useState<HomeView | null>(null);

  useEffect(() => {
    if (!isReady) return;
    let dead = false;
    const ctrl = new AbortController();
    setView(null);
    void fetchHome(token, { signal: ctrl.signal }).then((raw) => {
      if (dead || ctrl.signal.aborted) return;
      setView(buildHomeView(raw));
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [token, isReady]);

  const authed = isReady && !!token;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Your intelligence"
        title="Home"
        subtitle="Your personalized read on the desk — recent signals, the alerts digest, model readiness, and active non-decided markets, in one place. Research only, paper trading only."
      />

      {view === null ? (
        <>
          <Panel title="Your watchlist" className="mb-6">
            <CardSkeleton lines={2} />
          </Panel>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Top signals">
              <CardSkeleton />
            </Panel>
            <div className="flex flex-col gap-5">
              <Panel title="Digest">
                <CardSkeleton lines={2} />
              </Panel>
              <Panel title="Model A/B readiness">
                <CardSkeleton lines={2} />
              </Panel>
            </div>
          </div>
        </>
      ) : (
        <>
          {!view.reachable ? (
            <Panel className="mb-6">
              <p className="text-sm font-semibold text-text">Home is unreachable</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                The home aggregate did not answer — start the backend or set NEXT_PUBLIC_API_URL to
                see your personalized intelligence.
              </p>
            </Panel>
          ) : null}

          <WatchlistStrip view={view} authed={authed} />

          <div className="grid gap-5 lg:grid-cols-2">
            <section aria-label="Top signals">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-base font-black tracking-tight text-text">Top signals</h2>
                <Link href="/signals" className="text-[11px] font-semibold text-accent hover:underline">
                  All signals →
                </Link>
              </div>
              <SignalList
                rows={view.signals}
                emptyBody="No recent signals — scans publish only when a real trigger fires. Nothing is fabricated."
              />
            </section>

            <div className="flex flex-col gap-5">
              <DigestSummary view={view} />
              <ModelStatus view={view} />
              <TopMarkets view={view} />
            </div>
          </div>

          <p className={cn("mt-8 text-[10px] leading-relaxed text-muted-2")}>{view.disclaimer}</p>
        </>
      )}
    </PageShell>
  );
}
