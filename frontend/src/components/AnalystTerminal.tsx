"use client";

// The analyst terminal — the app's home. You watch the AI desk work (a
// chronological feed of real briefs and graded claims) and you can put it to
// work: pick any live market and run the actual analyst pipeline on demand.
// Nothing here is scripted; every entry is a database row.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";
import {
  fetchBriefs,
  fetchTrackRecord,
  type AnalystBrief,
  type TrackRecordRow,
} from "@/lib/polyscout-api";
import { ClaimBadge } from "@/components/ClaimBadge";
import { useGamification } from "@/lib/gamification";
import { cn } from "@/lib/cn";

type LiveMarket = { slug: string; title: string; category: string; yes_price: number | null };

const PIPELINE_STAGES = [
  "reading market state",
  "gathering evidence — news · whales · model",
  "writing brief",
  "staking falsifiable claim",
] as const;

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function day(iso: string): string {
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

async function runAnalyst(slug: string): Promise<AnalystBrief | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/analyst/run?market_slug=${encodeURIComponent(slug)}`,
      { method: "POST" },
    );
    if (!res.ok) return null;
    return (await res.json()) as AnalystBrief;
  } catch {
    return null;
  }
}

function BriefEntry({ brief, fresh = false }: { brief: AnalystBrief; fresh?: boolean }) {
  return (
    <li
      className={cn(
        "relative pl-6",
        fresh && "animate-fade-up",
      )}
    >
      <span
        className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-accent bg-bg"
        aria-hidden
      />
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-mono text-[10px] text-muted-2">
          {day(brief.created_at)} {clock(brief.created_at)}
        </span>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-accent">
          brief
        </span>
        {brief.claim && <ClaimBadge claim={brief.claim} />}
      </div>
      <Link href={`/research/brief?id=${brief.id}`} className="group mt-1 block">
        <p className="text-[15px] font-medium leading-snug text-text group-hover:text-white">
          {brief.headline}
        </p>
        <p className="mt-0.5 line-clamp-2 text-[13px] leading-relaxed text-muted">
          {brief.body_markdown.replace(/[#*_>`]/g, "").slice(0, 180)}
        </p>
        <span className="mt-1 inline-block font-mono text-[11px] text-muted-2">
          {brief.citations.length} citation{brief.citations.length === 1 ? "" : "s"} ·{" "}
          {brief.generator === "llm" ? brief.model_version : "deterministic"} · open →
        </span>
      </Link>
    </li>
  );
}

function RunningEntry({ market, stage }: { market: LiveMarket; stage: number }) {
  return (
    <li className="relative pl-6">
      <span
        className="absolute left-0 top-1.5 h-2.5 w-2.5 animate-pulse-soft rounded-full bg-accent"
        aria-hidden
      />
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] text-muted-2">now</span>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-accent">
          analyzing
        </span>
      </div>
      <p className="mt-1 text-[15px] font-medium text-text">{market.title}</p>
      <div className="mt-1.5 space-y-1" aria-live="polite">
        {PIPELINE_STAGES.map((label, i) => (
          <p
            key={label}
            className={cn(
              "font-mono text-[12px] transition-colors",
              i < stage && "text-up",
              i === stage && "text-accent",
              i > stage && "text-muted-2/50",
            )}
          >
            {i < stage ? "✓" : i === stage ? "▸" : "·"} {label}
            {i === stage && <span className="animate-pulse-soft">…</span>}
          </p>
        ))}
      </div>
    </li>
  );
}

export function AnalystTerminal() {
  const [briefs, setBriefs] = useState<AnalystBrief[] | null>(null);
  const [record, setRecord] = useState<TrackRecordRow | null>(null);
  const [markets, setMarkets] = useState<LiveMarket[]>([]);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<LiveMarket | null>(null);
  const [running, setRunning] = useState<LiveMarket | null>(null);
  const [stage, setStage] = useState(0);
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const { awardXp, celebrate } = useGamification();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void fetchBriefs({ limit: 12 }).then((p) => setBriefs(p.items));
    void fetchTrackRecord().then((rows) =>
      setRecord(rows.find((r) => r.dimension === "overall" && r.window_days === 0) ?? null),
    );
    if (API_BASE) {
      void fetch(`${API_BASE}/api/v1/markets`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then(
          (
            d: Array<{
              slug: string;
              title: string;
              category: string;
              source?: string;
              yes_price?: number | null;
            }>,
          ) =>
            setMarkets(
              d
                .filter((m) => m.source === "kalshi" || m.source === "polymarket")
                .map((m) => ({
                  slug: m.slug,
                  title: m.title,
                  category: m.category,
                  yes_price: m.yes_price ?? null,
                })),
            ),
        )
        .catch(() => {});
    }
  }, []);

  const matches = useMemo(() => {
    if (!query.trim() || picked) return [];
    const q = query.toLowerCase();
    return markets.filter((m) => m.title.toLowerCase().includes(q)).slice(0, 6);
  }, [query, markets, picked]);

  const ask = useCallback(async () => {
    const target = picked ?? matches[0];
    if (!target || running) return;
    setError(null);
    setRunning(target);
    setPicked(null);
    setQuery("");
    setStage(0);
    // Stage ticker mirrors the real pipeline order while the request runs.
    const ticker = setInterval(() => setStage((s) => Math.min(s + 1, 3)), 700);
    const brief = await runAnalyst(target.slug);
    clearInterval(ticker);
    setStage(4);
    setRunning(null);
    if (brief) {
      setBriefs((prev) => [brief, ...(prev ?? []).filter((b) => b.id !== brief.id)]);
      setFreshIds((s) => new Set(s).add(brief.id));
      awardXp(30, "Commissioned research");
      celebrate();
    } else {
      setError(
        "The analyst couldn't complete that one — backend unreachable or market unresearchable.",
      );
    }
  }, [picked, matches, running, awardXp, celebrate]);

  return (
    <div className="mx-auto grid max-w-[1080px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_280px]">
      {/* ————— The terminal ————— */}
      <section data-tour="ai-desk">
        {/* Composer — put the analyst to work */}
        <div className="rounded-2xl border border-accent/30 bg-surface p-4 shadow-glow-blue">
          <label
            htmlFor="ask-analyst"
            className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-accent"
          >
            Ask the analyst
          </label>
          <div className="relative mt-2">
            <div className="flex gap-2">
              <input
                id="ask-analyst"
                ref={inputRef}
                value={picked ? picked.title : query}
                onChange={(e) => {
                  setPicked(null);
                  setQuery(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void ask();
                }}
                placeholder="Type any live market — “bitcoin”, “fed”, “world cup”…"
                className="h-11 w-full rounded-pill bg-surface-2 px-4 text-sm text-text placeholder:text-muted-2 focus:outline-none focus:ring-1 focus:ring-accent"
                autoComplete="off"
              />
              <button
                type="button"
                onClick={() => void ask()}
                disabled={running !== null || (!picked && matches.length === 0)}
                className="shrink-0 rounded-pill bg-accent px-5 text-sm font-semibold text-white transition enabled:hover:bg-accent-active disabled:opacity-40"
              >
                {running ? "Working…" : "Analyze"}
              </button>
            </div>
            {matches.length > 0 && (
              <ul className="absolute z-10 mt-1.5 w-full overflow-hidden rounded-2xl border border-border bg-surface-2 shadow-lift">
                {matches.map((m) => (
                  <li key={m.slug}>
                    <button
                      type="button"
                      onClick={() => {
                        setPicked(m);
                        inputRef.current?.focus();
                      }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-text hover:bg-surface-3"
                    >
                      <span className="min-w-0 flex-1 truncate">{m.title}</span>
                      {m.yes_price != null && (
                        <span className="font-mono text-xs text-muted">
                          {Math.round(m.yes_price * 100)}¢
                        </span>
                      )}
                      <span className="rounded-pill bg-surface px-2 py-0.5 text-[10px] text-muted-2">
                        {m.category}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {error && <p className="mt-2 text-xs text-down">{error}</p>}
        </div>

        {/* The feed — the desk working, newest first */}
        <ul className="mt-6 space-y-5 border-l border-border pb-8 [&>li]:-ml-[5px]">
          {running && <RunningEntry market={running} stage={stage} />}
          {briefs === null ? (
            [0, 1, 2].map((i) => (
              <li key={i} className="pl-6">
                <div className="h-16 animate-pulse rounded-xl bg-surface" />
              </li>
            ))
          ) : briefs.length === 0 && !running ? (
            <li className="pl-6 font-mono text-sm text-muted">
              desk idle — ask the analyst above, or wait for signals to align.
            </li>
          ) : (
            briefs.map((b) => <BriefEntry key={b.id} brief={b} fresh={freshIds.has(b.id)} />)
          )}
        </ul>
      </section>

      {/* ————— Right rail: the stakes ————— */}
      <aside className="space-y-3 lg:pt-1">
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-wide text-muted-2">
            Track record
          </p>
          <p className="mt-1.5 font-mono text-3xl font-semibold text-text">
            {record ? `${(record.accuracy * 100).toFixed(0)}%` : "—"}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {record
              ? `accuracy · n=${record.n}`
              : "first claims grading now — misses count too"}
          </p>
          <Link
            href="/track-record"
            className="mt-2 inline-block text-xs font-semibold text-accent hover:underline"
          >
            Full scoreboard →
          </Link>
        </div>
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-wide text-muted-2">
            Live markets
          </p>
          <p className="mt-1.5 font-mono text-3xl font-semibold text-text">
            {markets.length || "—"}
          </p>
          <p className="mt-0.5 text-xs text-muted">mirrored from Kalshi + Polymarket</p>
          <Link
            href="/markets"
            className="mt-2 inline-block text-xs font-semibold text-accent hover:underline"
          >
            Browse the board →
          </Link>
        </div>
        <p className="px-1 text-[11px] leading-relaxed text-muted-2">
          Paper trading only. Research, not financial advice.
        </p>
      </aside>
    </div>
  );
}
