"use client";

// R01: opportunity scanner — a ranked, READ-ONLY "biggest edges right now" view
// from GET /api/v1/opportunities (backend N01). Analysis only: this is NOT an
// order feed and never presents a bet/execute CTA. Each row deep-links to the
// market detail (where the existing trade panel lives) as a paper-trade path.
import { useEffect, useMemo, useState } from "react";
import {
  buildOpportunitiesView,
  fetchOpportunities,
  type DirectionFilter,
  type OpportunitiesResponse,
} from "@/lib/opportunities-api";
import { OpportunityCard } from "@/components/OpportunityCard";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { PageHeader, PageShell, SegTabs, StatRow, StatTile } from "@/components/ui/kit";

const DIRECTION_OPTIONS: { value: DirectionFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "YES", label: "YES lean" },
  { value: "NO", label: "NO lean" },
];

const LIQUIDITY_STEPS: { value: number; label: string }[] = [
  { value: 0, label: "Any" },
  { value: 1_000, label: "1K+" },
  { value: 10_000, label: "10K+" },
  { value: 100_000, label: "100K+" },
];

// Loop110: the backend funnel now reports an ``after_signal_gate`` stage (the
// Loop107 CLV gate, between with_market_p and after_min_liquidity) that the
// lib type predates — widen it locally so every pipeline stage renders, in
// pipeline order, so an honest empty stays explainable stage by stage.
type FunnelCounts = NonNullable<OpportunitiesResponse["funnel"]> & {
  after_signal_gate: number;
};

const FUNNEL_STAGES: { key: keyof FunnelCounts; label: string }[] = [
  { key: "candidates_scanned", label: "scanned" },
  { key: "candidates_open", label: "open" },
  { key: "with_model_p", label: "with predictions" },
  { key: "with_market_p", label: "with market price" },
  { key: "after_signal_gate", label: "passed validation gate" },
  { key: "after_min_liquidity", label: "past min liquidity" },
  { key: "after_direction", label: "past direction filter" },
  { key: "returned", label: "returned" },
];

const intFmt = (n: number) => String(Math.round(n));
const ptsFmt = (n: number) => `${(n * 100).toFixed(1)} pts`;

export default function OpportunitiesPage() {
  const [raw, setRaw] = useState<OpportunitiesResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [direction, setDirection] = useState<DirectionFilter>("all");
  const [minLiquidity, setMinLiquidity] = useState(0);

  async function load() {
    setLoaded(false);
    const data = await fetchOpportunities({ limit: 50 });
    setRaw(data);
    setLoaded(true);
  }

  useEffect(() => {
    // Fetch-on-load only; direction + min-liquidity filter the fetched set
    // client-side (no extra requests, no poll loop).
    void load();
  }, []);

  const view = useMemo(
    () => buildOpportunitiesView(raw, { direction, minLiquidity }),
    [raw, direction, minLiquidity],
  );

  const topEdge = view.rows[0]?.edge ?? 0;

  // Loop110: compact one-line pipeline funnel for the empty state — plain text
  // like "97 open → 50 with predictions → 0 passed validation gate", null when
  // the backend didn't report funnel counts.
  const funnel = (raw?.funnel ?? null) as FunnelCounts | null;
  const funnelLine = funnel
    ? FUNNEL_STAGES.map((s) => `${funnel[s.key]} ${s.label}`).join(" → ")
    : null;

  // DIAGNOSIS106-OPPS: the honest empty explains ITSELF — branch on the
  // backend's machine-stable empty_reason, keeping the unreachable and
  // client-filter fallbacks. Copy never implies fabricated edges.
  function emptyStateBody(): string {
    if (raw === null) {
      return "The scanner is unreachable — live edges need the backend API.";
    }
    switch (raw.empty_reason) {
      case "no_model_predictions":
        return "No open market has a stored forecast probability yet. Edges are ranked only from real PredictionLog rows — never fabricated. The forecast-vs-market scanner stays empty until predictions are written for live markets.";
      case "no_validated_edge":
        return "No validated edges right now. Model predictions exist, but none currently beat the closing line out-of-sample. This board only lists edges that survive validation — an empty list is the model being honest, not the app being broken.";
      case "no_open_candidates":
        return "No open markets are in the current candidate set (top volume slice). Resolved or locked markets are not ranked as live edges.";
      case "no_market_prices":
        return "Model probabilities exist, but no market price (book or odds snapshot) is available to form an edge.";
      case "filtered_by_min_liquidity":
        return "Edges exist, but all are below the current min-liquidity control. Lower the floor to see more.";
      case "filtered_by_direction":
        return "Edges exist, but none match the YES/NO direction filter. Choose All to see every ranked edge.";
      default:
        return view.totalBeforeFilter === 0
          ? "No open market currently has both a model probability and a market price to rank — edges appear only from real predictions, never fabricated."
          : "Every ranked edge was filtered out by the current direction / min-liquidity controls. Loosen a filter to see more.";
    }
  }

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Opportunity scanner"
        title="Biggest edges right now"
        subtitle="Markets ranked by how far the model's probability sits from the market price. Ranked read-only analysis — this is NOT an order feed; open a market to reach its paper-trade panel."
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
          label="Ranked edges"
          value={loaded ? <AnimatedNumber value={view.totalBeforeFilter} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Shown after filter"
          value={loaded ? <AnimatedNumber value={view.count} format={intFmt} /> : "—"}
          accent
        />
        <StatTile
          label="Top edge"
          value={loaded && view.rows.length > 0 ? <AnimatedNumber value={topEdge} format={ptsFmt} /> : "—"}
        />
      </StatRow>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">
            Direction lean
          </span>
          <SegTabs
            value={direction}
            onChange={setDirection}
            options={DIRECTION_OPTIONS}
            size="sm"
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">
            Min liquidity
          </span>
          <SegTabs
            value={String(minLiquidity)}
            onChange={(v) => setMinLiquidity(Number(v))}
            options={LIQUIDITY_STEPS.map((s) => ({ value: String(s.value), label: s.label }))}
            size="sm"
          />
        </div>
      </div>

      {!loaded ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl border border-border bg-surface" />
          ))}
        </div>
      ) : view.rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">No opportunities meet the filter right now.</p>
          <p className="mt-1">{emptyStateBody()}</p>
          {funnelLine !== null && (
            <p className="mt-2 text-xs text-muted-2">{funnelLine}</p>
          )}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {view.rows.map((row, i) => (
            <MotionReveal key={row.slug} delay={Math.min(i * 0.04, 0.24)}>
              <OpportunityCard row={row} />
            </MotionReveal>
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-muted-2">{view.disclaimer}</p>
    </PageShell>
  );
}
