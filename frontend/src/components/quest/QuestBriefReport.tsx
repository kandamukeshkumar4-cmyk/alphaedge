"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { MarketTradingPanel } from "@/components/MarketTradingPanel";
import { useAtlasPanel } from "@/context/atlas-panel";
import { marketHref } from "@/lib/market-href";
import type { AnalystBrief } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

/** Split brief markdown into Key Risks / Bottom Line / body sections when present. */
function parseBriefSections(md: string) {
  const risks: string[] = [];
  let bottomLine = "";
  const other: string[] = [];
  let mode: "body" | "risks" | "bottom" = "body";

  for (const raw of md.split(/\n+/)) {
    const line = raw.trim();
    if (!line) continue;
    const lower = line.toLowerCase();
    if (/^#{1,3}\s*key\s*risks?/.test(lower) || /^key\s*risks?:?$/.test(lower)) {
      mode = "risks";
      continue;
    }
    if (/^#{1,3}\s*bottom\s*line/.test(lower) || /^bottom\s*line:?$/.test(lower)) {
      mode = "bottom";
      continue;
    }
    if (mode === "risks" && (/^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line))) {
      risks.push(line.replace(/^[-*•]\s+/, "").replace(/^\d+[.)]\s+/, ""));
      continue;
    }
    if (mode === "bottom") {
      bottomLine += (bottomLine ? " " : "") + line.replace(/^[-*•]\s+/, "");
      continue;
    }
    other.push(line);
  }

  return { risks, bottomLine, other };
}

function renderLines(lines: string[]) {
  return lines.map((t, i) => {
    if (t.startsWith("### ")) {
      return (
        <h3 key={i} className="mt-5 text-base font-semibold text-text">
          {t.slice(4)}
        </h3>
      );
    }
    if (t.startsWith("## ")) {
      return (
        <h2 key={i} className="mt-6 text-lg font-semibold text-text">
          {t.slice(3)}
        </h2>
      );
    }
    if (t.startsWith("- ")) {
      return (
        <li key={i} className="ml-5 list-disc text-sm leading-relaxed text-muted">
          {t.slice(2)}
        </li>
      );
    }
    return (
      <p key={i} className="mt-3 text-sm leading-relaxed text-muted">
        {t}
      </p>
    );
  });
}

export function QuestBriefReport({
  brief,
  claimSlot,
  evidenceSlot,
  whySlot,
}: {
  brief: AnalystBrief;
  claimSlot?: React.ReactNode;
  evidenceSlot?: React.ReactNode;
  whySlot?: React.ReactNode;
}) {
  const { openPanel } = useAtlasPanel();
  const { risks, bottomLine, other } = parseBriefSections(brief.body_markdown);
  const sources = brief.citations.slice(0, 8);

  return (
    <div className="mx-auto grid max-w-[1400px] gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_320px] sm:px-5">
      <motion.article
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="min-w-0"
      >
        <nav className="mb-4 text-xs text-muted-2" aria-label="Breadcrumb">
          <Link href="/signals" className="hover:text-text">
            Signals
          </Link>
          <span className="mx-1.5">/</span>
          <Link href={marketHref(brief.market_slug)} className="font-mono hover:text-text">
            {brief.market_slug}
          </Link>
        </nav>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          {claimSlot}
          <button
            type="button"
            onClick={() =>
              openPanel({
                mode: "analyze",
                marketSlug: brief.market_slug,
                marketTitle: brief.headline,
                seedPrompt: `Expand this brief: ${brief.headline}`,
              })
            }
            className="rounded-lg border border-primary/35 px-3 py-1.5 text-xs font-bold text-primary transition hover:bg-primary hover:text-bg"
          >
            ✦ Ask ATLAS
          </button>
        </div>

        <h1 className="text-2xl font-black leading-tight tracking-tight text-text sm:text-3xl">
          {brief.headline}
        </h1>
        <p className="mt-1 text-xs text-muted-2">
          {new Date(brief.created_at).toLocaleString()} ·{" "}
          {brief.generator === "llm" ? brief.model_version : "deterministic fallback"}
        </p>

        <div className="mt-4">{renderLines(other)}</div>

        {risks.length > 0 ? (
          <section className="mt-8">
            <h2 className="text-sm font-bold uppercase tracking-wider text-muted">Key risks</h2>
            <ol className="mt-3 space-y-3">
              {risks.map((r, i) => (
                <li key={r} className="flex gap-3 text-sm leading-relaxed text-muted">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-[11px] font-bold text-amber-300">
                    {i + 1}
                  </span>
                  <span>
                    <strong className="text-text">{r.split(/[:—-]/)[0]}</strong>
                    {r.includes(":") || r.includes("—") || r.includes("-")
                      ? ` — ${r.split(/[:—-]/).slice(1).join("—").trim()}`
                      : null}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        {bottomLine ? (
          <section className="mt-8 rounded-xl border border-primary/25 bg-primary-dim/30 p-4">
            <h2 className="text-sm font-bold uppercase tracking-wider text-primary">Bottom line</h2>
            <p className="mt-2 text-sm leading-relaxed text-text">{bottomLine}</p>
          </section>
        ) : null}

        {evidenceSlot}

        {sources.length > 0 ? (
          <section className="mt-8">
            <h2 className="text-sm font-bold uppercase tracking-wider text-muted">
              Sources ({brief.citations.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {sources.map((c, i) => (
                <li
                  key={i}
                  className="flex gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm"
                >
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 font-mono text-[10px] font-bold text-primary">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="font-semibold text-text">
                      {String(c.label ?? c.ref ?? c.kind ?? "Source")}
                    </p>
                    {c.kind ? (
                      <p className="mt-0.5 text-xs capitalize text-muted-2">{String(c.kind)}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {whySlot}
      </motion.article>

      <aside className="lg:sticky lg:top-20 lg:self-start">
        <div className="overflow-hidden rounded-2xl border border-border bg-surface">
          <div className="flex border-b border-border">
            <span className="flex-1 border-b-2 border-primary py-2.5 text-center text-xs font-bold text-primary">
              Analyze
            </span>
            <Link
              href={marketHref(brief.market_slug)}
              className="flex-1 py-2.5 text-center text-xs font-bold text-muted transition hover:text-text"
            >
              Info
            </Link>
          </div>
          <div className="p-3">
            <p className="mb-2 truncate text-sm font-bold text-text">{brief.headline}</p>
            <MarketTradingPanel
              slug={brief.market_slug}
              title={brief.headline}
              initialYesPrice={brief.market_implied ?? brief.claim?.price_at_claim ?? 0.5}
            />
          </div>
        </div>
        <p
          className={cn(
            "mt-3 rounded-xl border border-border bg-surface/60 px-3 py-2 text-[11px] leading-relaxed text-muted-2",
          )}
        >
          Paper trading simulation only. ATLAS cannot place orders — RiskService path required.
        </p>
      </aside>
    </div>
  );
}
