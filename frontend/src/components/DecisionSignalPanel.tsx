"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import {
  buildCultSignalModel,
  type CultSignalTone,
  type SignalCheckStatus,
} from "@/lib/cult-signal-model";
import {
  fetchPaperSignalSummary,
  submitPaperSignal,
  type PaperSignalSummary,
} from "@/lib/paper-signal-api";
import type { Market } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

// Interaction patterns adapted from Cult UI choice-poll, vote-tally, timer, and
// direction-aware-tabs components. Cult UI is MIT licensed, copyright 2023 Jordan-Gilliam.
type PanelTab = "signal" | "guardrails";

const TABS: Array<{ id: PanelTab; label: string }> = [
  { id: "signal", label: "Signal" },
  { id: "guardrails", label: "Guardrails" },
];

export function DecisionSignalPanel({ market }: { market: Market }) {
  const [signalSummary, setSignalSummary] = useState<PaperSignalSummary | null>(null);
  const model = useMemo(() => buildCultSignalModel(market, signalSummary), [market, signalSummary]);
  const [activeTab, setActiveTab] = useState<PanelTab>("signal");
  const [selected, setSelected] = useState(model.poll.defaultSelection);
  const [localVotes, setLocalVotes] = useState<Record<string, number> | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const initialModel = buildCultSignalModel(market);

    setSignalSummary(null);
    setSelected(initialModel.poll.defaultSelection);
    setLocalVotes(null);
    setSubmitted(false);
    setFeedback(null);
    setActiveTab("signal");

    fetchPaperSignalSummary({ slug: market.slug }).then((summary) => {
      if (cancelled || !summary?.paper_trading_only) {
        return;
      }
      const summaryModel = buildCultSignalModel(market, summary);
      setSignalSummary(summary);
      setSelected(summaryModel.poll.defaultSelection);
      setSubmitted(Boolean(summary.selected_outcome));
    });

    return () => {
      cancelled = true;
    };
  }, [market]);

  const displayedVotes = localVotes ?? model.poll.votes;
  const totalVotes = Object.values(displayedVotes).reduce((sum, count) => sum + count, 0);

  async function submitSignal() {
    if (!selected || submitted) {
      return;
    }

    const selectedOption = model.poll.options.find((option) => option.id === selected);
    if (selectedOption?.apiOutcome) {
      const result = await submitPaperSignal({
        slug: market.slug,
        outcome: selectedOption.apiOutcome,
      });
      if (result.ok) {
        setSignalSummary(result.summary);
        setLocalVotes(null);
        setSubmitted(true);
        setFeedback("Backend paper signal recorded.");
        return;
      }
      if (result.mode === "api") {
        setFeedback(result.message);
        return;
      }
    }

    setLocalVotes((current) => ({
      ...(current ?? displayedVotes),
      [selected]: ((current ?? displayedVotes)[selected] ?? 0) + 1,
    }));
    setSubmitted(true);
    setFeedback("Local paper signal recorded.");
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-black text-text">Decision stack</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            {model.edgeVerdict} across book, model, crowd, and risk.
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-border bg-bg px-2 py-1 font-mono text-[11px] font-bold text-muted">
          {model.closeLabel}
        </span>
      </header>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {model.toolStack.map((tool) => (
          <div
            key={tool.id}
            className="min-h-[82px] rounded-lg border border-border bg-bg/45 p-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[11px] font-semibold text-muted">
                {tool.label}
              </span>
              <span className={cn("h-2 w-2 rounded-full", toneDotClass(tool.tone))} />
            </div>
            <div className={cn("mt-1 font-mono text-base font-black", toneTextClass(tool.tone))}>
              {tool.value}
            </div>
            <div className="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-2">
              {tool.detail}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 rounded-lg border border-border bg-bg p-1">
        <div className="grid grid-cols-2 gap-1" role="tablist" aria-label="Decision stack tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "relative rounded-md px-3 py-1.5 text-xs font-bold transition",
                activeTab === tab.id ? "text-white" : "text-muted hover:text-text",
              )}
            >
              {activeTab === tab.id && (
                <motion.span
                  layoutId={`decision-tab-${market.slug}`}
                  className="absolute inset-0 rounded-md bg-accent"
                  transition={{ type: "spring", bounce: 0.16, duration: 0.35 }}
                />
              )}
              <span className="relative z-10">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {activeTab === "signal" ? (
          <motion.div
            key="signal"
            className="mt-3 flex flex-col gap-2"
            initial={{ opacity: 0, x: 16, filter: "blur(3px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, x: -16, filter: "blur(3px)" }}
            transition={{ duration: 0.22 }}
          >
            {model.poll.options.map((option) => {
              const count = displayedVotes[option.id] ?? 0;
              const percentage = totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0;
              const active = selected === option.id;

              return (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={active}
                  disabled={submitted}
                  onClick={() => setSelected(option.id)}
                  className={cn(
                    "relative min-h-[58px] overflow-hidden rounded-xl border px-3 py-2 text-left transition",
                    active
                      ? "border-accent/55 bg-accent-dim text-text"
                      : "border-border bg-bg/40 text-muted hover:text-text",
                    submitted && "cursor-default",
                  )}
                >
                  {submitted && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-0 left-0 bg-accent/10 transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  )}
                  <span className="relative z-10 flex items-center gap-3">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-surface-2 text-base">
                      {option.emoji}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-bold">{option.label}</span>
                      <span className="mt-0.5 block font-mono text-[11px] text-muted-2">
                        {option.priceLabel} book
                      </span>
                    </span>
                    <span className="font-mono text-sm font-black text-text">
                      {submitted ? `${percentage}%` : count.toLocaleString()}
                    </span>
                  </span>
                </button>
              );
            })}

            <button
              type="button"
              onClick={submitSignal}
              disabled={submitted}
              className={cn(
                "mt-1 rounded-xl py-2 text-sm font-black transition",
                submitted
                  ? "border border-accent/35 bg-accent-dim text-accent"
                  : "bg-accent text-white hover:brightness-110",
              )}
            >
              {submitted ? "Signal recorded" : "Submit paper signal"}
            </button>
            {feedback ? (
              <p className="font-mono text-[11px] leading-relaxed text-muted">
                {feedback}
              </p>
            ) : null}
          </motion.div>
        ) : (
          <motion.div
            key="guardrails"
            className="mt-3 flex flex-col gap-2"
            initial={{ opacity: 0, x: -16, filter: "blur(3px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, x: 16, filter: "blur(3px)" }}
            transition={{ duration: 0.22 }}
          >
            {model.riskChecks.map((check) => (
              <div
                key={check.label}
                className="flex items-start gap-3 rounded-lg border border-border bg-bg/40 px-3 py-2.5"
              >
                <span
                  className={cn(
                    "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                    statusDotClass(check.status),
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-bold text-text">{check.label}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-muted">
                    {check.detail}
                  </span>
                </span>
              </div>
            ))}
            <div className="rounded-xl border border-accent/30 bg-accent-dim px-3 py-2 font-mono text-[11px] leading-relaxed text-accent">
              {model.executionGuardrail}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function toneTextClass(tone: CultSignalTone): string {
  switch (tone) {
    case "primary":
      return "text-primary";
    case "danger":
      return "text-danger";
    case "accent":
      return "text-accent";
    case "gold":
      return "text-gold";
    default:
      return "text-text";
  }
}

function toneDotClass(tone: CultSignalTone): string {
  switch (tone) {
    case "primary":
      return "bg-primary";
    case "danger":
      return "bg-danger";
    case "accent":
      return "bg-accent";
    case "gold":
      return "bg-gold";
    default:
      return "bg-muted-2";
  }
}

function statusDotClass(status: SignalCheckStatus): string {
  return status === "pass" ? "bg-primary shadow-glow-blue" : "bg-gold";
}
