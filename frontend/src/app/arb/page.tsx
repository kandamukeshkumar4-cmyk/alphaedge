"use client";

// F03: dedicated cross-venue arb view. Matched Polymarket ↔ Kalshi pairs from
// GET /api/v1/arb/opportunities (reuses arb-api.ts): per-leg breakdown,
// confidence + spread_bps chips, stale flag, reasoned empty. Signal-only —
// no order is ever placed here.
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  arbEmptyReason,
  fetchArbOpportunities,
  type ArbOpportunitiesPage,
  type ArbOpportunity,
} from "@/lib/arb-api";
import { cn } from "@/lib/cn";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { PageHeader, PageShell, StatRow, StatTile } from "@/components/ui/kit";

const intFmt = (n: number) => String(Math.round(n));

function Chip({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "accent" | "warn";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-mono text-[11px] font-bold",
        tone === "accent"
          ? "border-accent/40 bg-accent/12 text-accent"
          : tone === "warn"
            ? "border-gold/40 bg-gold/10 text-gold"
            : "border-border bg-surface-2 text-muted",
      )}
    >
      <span className="uppercase tracking-[0.06em] text-muted-2">{label}</span>
      {value}
    </span>
  );
}

function ArbCard({ opp }: { opp: ArbOpportunity }) {
  const confidence = opp.confidence ?? opp.match_confidence;
  return (
    <article
      className={cn(
        "rounded-2xl border border-border bg-surface p-4 sm:p-5",
        opp.stale && "opacity-70",
      )}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.06em] text-accent">
          Polymarket ↔ Kalshi
        </span>
        {opp.stale ? (
          <span className="rounded-full border border-gold/40 bg-gold/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.06em] text-gold">
            Stale
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.06em] text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Fresh
          </span>
        )}
        <span className="ml-auto rounded-full border border-border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-muted-2">
          Signal only
        </span>
      </div>

      <p className="text-sm font-bold text-text">{opp.pm_title}</p>
      <p className="text-xs text-muted">{opp.kalshi_title}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip label="Edge" value={opp.theoretical_edge} tone="accent" />
        <Chip label="Spread" value={`${opp.spread_bps} bps`} />
        <Chip
          label="Conf"
          value={`${Math.round(confidence * 100)}%`}
          tone={confidence >= 0.8 ? "accent" : "neutral"}
        />
      </div>

      {/* D04: overflow-x-auto (was overflow-hidden) so the leg table scrolls
          instead of clipping at 390px. */}
      {opp.legs.length > 0 ? (
        <div className="mt-3 overflow-x-auto rounded-xl border border-border/70">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-2 text-[10px] uppercase tracking-[0.06em] text-muted-2">
              <tr>
                <th className="px-3 py-1.5 font-bold">Venue</th>
                <th className="px-3 py-1.5 font-bold">Leg</th>
                <th className="px-3 py-1.5 text-right font-bold">Price</th>
                <th className="px-3 py-1.5 text-right font-bold">Fee</th>
              </tr>
            </thead>
            <tbody>
              {opp.legs.map((leg, i) => (
                <tr key={`${leg.platform}-${leg.market_id}-${i}`} className="border-t border-border/60">
                  <td className="px-3 py-1.5 font-semibold capitalize text-text">{leg.platform}</td>
                  <td className="px-3 py-1.5 font-mono text-muted">{leg.outcome}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-text">{leg.price}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-muted-2">{leg.fee}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-2">No per-leg breakdown on this observation.</p>
      )}

      <div className="mt-3 flex flex-wrap gap-3 text-xs">
        <Link
          href={`/markets/view?slug=${encodeURIComponent(opp.pm_market_id)}`}
          className="font-semibold text-accent hover:underline"
        >
          PM market
        </Link>
        <Link
          href={`/markets/view?slug=${encodeURIComponent(opp.kalshi_market_id)}`}
          className="font-semibold text-accent hover:underline"
        >
          Kalshi market
        </Link>
      </div>
    </article>
  );
}

export default function ArbPage() {
  const [page, setPage] = useState<ArbOpportunitiesPage | null>(null);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    setLoaded(false);
    const data = await fetchArbOpportunities(24);
    setPage(data);
    setLoaded(true);
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Cross-venue arb"
        title="Fee-aware arb monitor"
        subtitle="Entity- and date-aligned Polymarket ↔ Kalshi pairs with per-leg pricing. Signal-only — nothing is ever auto-traded."
        actions={
          <button
            type="button"
            onClick={() => void load()}
            disabled={!loaded}
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {loaded ? "Refresh" : "Refreshing…"}
          </button>
        }
      />

      <StatRow cols={3} className="mb-6">
        <StatTile
          label="Matched pairs"
          value={page ? <AnimatedNumber value={page.total} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Fresh"
          value={page ? <AnimatedNumber value={page.fresh_count} format={intFmt} /> : "—"}
          accent
        />
        <StatTile
          label="Stale"
          value={page ? <AnimatedNumber value={page.stale_count} format={intFmt} /> : "—"}
        />
      </StatRow>

      {!loaded ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-52 animate-pulse rounded-2xl border border-border bg-surface" />
          ))}
        </div>
      ) : !page || page.opportunities.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">No cross-venue arb signal right now.</p>
          <p className="mt-1">{arbEmptyReason(page)}</p>
          <p className="mt-2 text-xs text-muted-2">
            A matched pair must be entity- and date-aligned, clear the confidence bar, and have a
            fresh quote to surface here. Signal only — no order is ever placed.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {page.opportunities.map((opp, i) => (
            <MotionReveal key={opp.id} delay={Math.min(i * 0.05, 0.3)}>
              <ArbCard opp={opp} />
            </MotionReveal>
          ))}
        </div>
      )}

      {page?.note ? <p className="mt-4 text-xs text-muted">{page.note}</p> : null}
    </PageShell>
  );
}
