"use client";

/**
 * QuestFlow ATLAS right rail — persistent AI placement.
 * Analysis-only: never places orders. Paper-trading simulation only.
 *
 * Loop V77 A1: scroll the panel container (never window/scrollIntoView),
 * pin the newest answer at the top of the panel viewport, highlight briefly.
 * Loop V77 A2: staged in-flight thinking phases + answer skeleton + retry.
 */

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { StatusDot } from "@astryxdesign/core/StatusDot";
import { useAtlasPanel } from "@/context/atlas-panel";
import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import { getAccessToken } from "@/lib/portfolio-api";
import { useDialog } from "@/hooks/useDialog";
import { cn } from "@/lib/cn";
import {
  ATLAS_ANSWER_HIGHLIGHT_MS,
  isHighlightedAnswer,
  prefersReducedMotion,
  scrollPanelAnchorToTop,
} from "./atlas-panel-scroll";
import {
  atlasNextPhaseBoundaryMs,
  atlasThinkingPhaseAt,
  type AtlasThinkingPhase,
} from "./atlas-thinking";

const AGENT_ID = "ATLAS-9-e4c1";
const ANALYSIS_BANNER = "Analysis only — this assistant cannot place trades.";

type Msg = {
  role: "user" | "assistant";
  content: string;
  tools?: { name: string; status: "complete" | "running" | "pending"; target?: string }[];
  error?: boolean;
  retryPrompt?: string;
};

const SUGGESTIONS = [
  { label: "Find Trades", prompt: "Find the strongest paper-edge trades right now." },
  { label: "Check Positions", prompt: "Summarize my paper portfolio risk." },
  { label: "Why this market?", prompt: "Explain the key drivers for this market." },
];

export function AtlasPanel() {
  const { open, marketSlug, marketTitle, seedPrompt, openPanel, closePanel, togglePanel } =
    useAtlasPanel();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [thinkingPhase, setThinkingPhase] = useState<AtlasThinkingPhase | null>(null);
  const [thinkingStartedAt, setThinkingStartedAt] = useState<number | null>(null);
  const [highlightIndex, setHighlightIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const answerAnchorRef = useRef<HTMLDivElement>(null);
  const thinkingAnchorRef = useRef<HTMLDivElement | null>(null);
  const seededRef = useRef<string | null>(null);
  const lastAssistantCountRef = useRef(0);
  // H-A11Y-01: trap focus in the mobile ATLAS sheet while it is open.
  const mobileSheetRef = useDialog<HTMLDivElement>(closePanel, open);

  // Desktop + mobile both mount when open; bind refs only to the visible tree.
  const bindScrollRef = (el: HTMLDivElement | null) => {
    if (el && (el.offsetParent !== null || el.getClientRects().length > 0)) {
      scrollRef.current = el;
    }
  };
  const bindAnswerAnchorRef = (el: HTMLDivElement | null) => {
    if (el && (el.offsetParent !== null || el.getClientRects().length > 0)) {
      answerAnchorRef.current = el;
    }
  };
  const bindThinkingAnchorRef = (el: HTMLDivElement | null) => {
    if (el && (el.offsetParent !== null || el.getClientRects().length > 0)) {
      thinkingAnchorRef.current = el;
    }
  };

  // A1: when a new assistant answer arrives, pin it to the top of the PANEL
  // scrollport and flash a brief highlight. Never scroll the page.
  useEffect(() => {
    const assistantCount = messages.filter((m) => m.role === "assistant").length;
    if (assistantCount <= lastAssistantCountRef.current) return;
    lastAssistantCountRef.current = assistantCount;

    const newestIdx = messages.length - 1;
    if (newestIdx < 0 || messages[newestIdx]?.role !== "assistant") return;
    setHighlightIndex(newestIdx);

    const run = () => {
      const container = scrollRef.current;
      const anchor = answerAnchorRef.current;
      if (container && anchor) scrollPanelAnchorToTop(container, anchor);
    };
    // Wait a frame so the panel (and mobile sheet) finish opening/layout.
    requestAnimationFrame(() => requestAnimationFrame(run));

    const ms = prefersReducedMotion() ? 0 : ATLAS_ANSWER_HIGHLIGHT_MS;
    if (ms === 0) {
      setHighlightIndex(null);
      return;
    }
    const t = window.setTimeout(() => setHighlightIndex(null), ms);
    return () => window.clearTimeout(t);
  }, [messages, open]);

  // A2: advance staged thinking labels by elapsed time while the request flies.
  useEffect(() => {
    if (!busy || thinkingStartedAt === null) {
      setThinkingPhase(null);
      return;
    }
    const tick = () => {
      const elapsed = Date.now() - thinkingStartedAt;
      setThinkingPhase(atlasThinkingPhaseAt(elapsed));
      const nextAt = atlasNextPhaseBoundaryMs(elapsed);
      return nextAt === null ? null : nextAt - elapsed;
    };
    const firstDelay = tick();
    if (firstDelay === null) return;
    let timer = window.setTimeout(function advance() {
      const delay = tick();
      if (delay !== null) timer = window.setTimeout(advance, delay);
    }, firstDelay);
    return () => window.clearTimeout(timer);
  }, [busy, thinkingStartedAt]);

  // A2: while thinking, keep the in-flight block at the top of the panel viewport.
  useEffect(() => {
    if (!busy || !thinkingPhase) return;
    const run = () => {
      const container = scrollRef.current;
      const anchor = thinkingAnchorRef.current;
      if (container && anchor) scrollPanelAnchorToTop(container, anchor);
    };
    requestAnimationFrame(() => requestAnimationFrame(run));
  }, [busy, thinkingPhase, open]);

  useEffect(() => {
    if (!seedPrompt || seededRef.current === seedPrompt) return;
    seededRef.current = seedPrompt;
    // Analyze entry points call openPanel; re-assert open so a collapsed rail expands.
    openPanel({ mode: "analyze" });
    void send(seedPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed once per prompt
  }, [seedPrompt]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setBusy(true);
    setThinkingStartedAt(Date.now());
    setThinkingPhase(atlasThinkingPhaseAt(0));

    try {
      const base = await ensureApiBase();
      if (!hasLiveApi(base)) {
        await new Promise((r) => setTimeout(r, 900));
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: marketTitle
              ? `**${marketTitle}**\n\nConnect \`NEXT_PUBLIC_API_URL\` for live ATLAS analysis. ${ANALYSIS_BANNER}`
              : `Ready to analyze paper markets. ${ANALYSIS_BANNER}`,
            tools: [
              { name: "read", status: "complete", target: marketSlug ?? "markets" },
            ],
          },
        ]);
        return;
      }

      const token = getAccessToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch(apiUrl("/api/v1/assistant/chat", base), {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: trimmed,
          market_slug: marketSlug,
        }),
      });
      if (!res.ok) {
        const detail =
          res.status === 429
            ? "ATLAS is rate-limited right now — try again in a minute, or sign in."
            : `Could not reach ATLAS (HTTP ${res.status}).`;
        throw new Error(detail);
      }
      const data = (await res.json()) as {
        reply?: string;
        tools_used?: string[];
        analysis_only_banner?: string;
      };
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.reply ?? "No reply.",
          tools: (data.tools_used ?? []).map((name) => ({
            name,
            status: "complete" as const,
            target: marketSlug ?? undefined,
          })),
        },
      ]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Could not reach ATLAS.";
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: detail,
          error: true,
          retryPrompt: trimmed,
        },
      ]);
    } finally {
      setBusy(false);
      setThinkingStartedAt(null);
      setThinkingPhase(null);
    }
  }

  return (
    <>
      {/* Desktop persistent rail */}
      <AnimatePresence initial={false}>
        {open ? (
          <motion.aside
            key="atlas-rail"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 320, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="relative hidden h-[calc(100vh-7.5rem)] w-[320px] shrink-0 overflow-hidden border-l border-border bg-surface lg:block"
            aria-label={`${AGENT_ID} assistant`}
          >
            <div className="flex h-full w-[320px] flex-col">
              <AtlasHeader onClose={closePanel} />
              <AtlasBody
                messages={messages}
                thinkingPhase={thinkingPhase}
                busy={busy}
                marketTitle={marketTitle}
                highlightIndex={highlightIndex}
                scrollRef={bindScrollRef}
                answerAnchorRef={bindAnswerAnchorRef}
                thinkingAnchorRef={bindThinkingAnchorRef}
                onSuggest={(p) => void send(p)}
                onRetry={(p) => void send(p)}
              />
              <AtlasComposer
                input={input}
                busy={busy}
                onChange={setInput}
                onSend={() => void send(input)}
              />
            </div>
          </motion.aside>
        ) : (
          <button
            type="button"
            onClick={() => openPanel({ mode: "chat" })}
            className="fixed right-3 top-24 z-30 hidden rounded-l-xl border border-border border-r-0 bg-surface px-2 py-3 text-[10px] font-bold uppercase tracking-wider text-primary shadow-glow lg:block"
            aria-label="Open ATLAS panel"
          >
            AI
          </button>
        )}
      </AnimatePresence>

      {/* Mobile floating toggle + sheet */}
      <button
        type="button"
        onClick={togglePanel}
        className="fixed bottom-24 right-4 z-40 grid h-12 w-12 place-items-center rounded-full bg-primary text-bg shadow-glow lg:hidden"
        aria-label="Toggle ATLAS"
      >
        <SparkIcon />
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            key="atlas-mobile"
            ref={mobileSheetRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="ATLAS assistant"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-x-0 bottom-0 z-50 flex max-h-[78vh] flex-col rounded-t-2xl border border-border bg-surface shadow-2xl focus:outline-none lg:hidden"
          >
            <AtlasHeader onClose={closePanel} />
            <AtlasBody
              messages={messages}
              thinkingPhase={thinkingPhase}
              busy={busy}
              marketTitle={marketTitle}
              highlightIndex={highlightIndex}
              scrollRef={bindScrollRef}
              answerAnchorRef={bindAnswerAnchorRef}
              thinkingAnchorRef={bindThinkingAnchorRef}
              onSuggest={(p) => void send(p)}
              onRetry={(p) => void send(p)}
            />
            <AtlasComposer
              input={input}
              busy={busy}
              onChange={setInput}
              onSend={() => void send(input)}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}

function AtlasHeader({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-3">
      <div className="flex items-center gap-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-primary to-accent text-bg">
          <SparkIcon />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-bold text-text">{AGENT_ID}</p>
            <StatusDot variant="success" label="Online" isPulsing />
          </div>
          <p className="text-[10px] text-muted-2">Paper analysis · no order path</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="grid h-8 w-8 place-items-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-text"
        aria-label="Close ATLAS"
      >
        ×
      </button>
    </div>
  );
}

function AtlasBody({
  messages,
  thinkingPhase,
  busy,
  marketTitle,
  highlightIndex,
  scrollRef,
  answerAnchorRef,
  thinkingAnchorRef,
  onSuggest,
  onRetry,
}: {
  messages: Msg[];
  thinkingPhase: AtlasThinkingPhase | null;
  busy: boolean;
  marketTitle: string | null;
  highlightIndex: number | null;
  scrollRef: (el: HTMLDivElement | null) => void;
  answerAnchorRef: (el: HTMLDivElement | null) => void;
  thinkingAnchorRef: (el: HTMLDivElement | null) => void;
  onSuggest: (prompt: string) => void;
  onRetry: (prompt: string) => void;
}) {
  const reduceMotion = prefersReducedMotion();
  return (
    <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
      <p className="rounded-lg border border-accent/25 bg-accent-dim/40 px-3 py-2 text-[11px] leading-relaxed text-accent">
        {ANALYSIS_BANNER}
      </p>

      {messages.length === 0 && !busy ? (
        <div className="space-y-4 pt-6 text-center">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full border border-border bg-surface-2">
            <SparkIcon large />
          </div>
          <div>
            <p className="text-sm font-semibold text-text">Ask {AGENT_ID}</p>
            <p className="mt-1 text-xs text-muted">
              {marketTitle ? `Context: ${marketTitle}` : "Market briefs, edge checks, risk notes."}
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => onSuggest(s.prompt)}
                className="rounded-full border border-border bg-surface-2 px-3 py-1.5 text-[11px] font-semibold text-muted transition hover:border-primary hover:text-primary"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {busy && thinkingPhase ? (
        <motion.div
          ref={thinkingAnchorRef}
          data-atlas-thinking="in-flight"
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-primary/30 bg-surface-2 px-3 py-2.5"
          aria-live="polite"
          aria-busy="true"
        >
          <p className="mb-3 flex items-center gap-2 text-[12px] font-semibold text-primary">
            <span
              className={cn(
                "inline-block h-1.5 w-1.5 rounded-full bg-primary",
                !reduceMotion && "animate-pulse",
              )}
            />
            {thinkingPhase.label}
          </p>
          <div className="space-y-2" aria-hidden>
            <div className="skeleton h-3 w-4/5 rounded" />
            <div className="skeleton h-3 w-full rounded" />
            <div className="skeleton h-3 w-3/5 rounded" />
            <div className="skeleton mt-2 h-16 w-full rounded-lg" />
          </div>
        </motion.div>
      ) : null}

      {messages.map((m, i) => {
        const isLatestAssistant =
          m.role === "assistant" && i === messages.length - 1 && !busy;
        const highlighted = isHighlightedAnswer(m.role, i, highlightIndex);
        return (
          <motion.div
            key={`${m.role}-${i}`}
            ref={isLatestAssistant ? answerAnchorRef : undefined}
            data-atlas-answer={isLatestAssistant ? "latest" : undefined}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
            className={cn(
              "rounded-xl px-3 py-2.5 text-[13px] leading-relaxed",
              m.role === "user"
                ? "ml-6 bg-primary-dim text-text"
                : m.error
                  ? "mr-2 border border-danger/40 bg-danger-dim/30 text-text"
                  : "mr-2 border border-border bg-surface-2 text-muted",
              highlighted &&
                "border-primary/50 bg-primary-dim/40 ring-2 ring-primary/35 transition-[box-shadow,background-color] duration-500",
            )}
          >
            {m.role === "assistant" && m.tools && m.tools.length > 0 ? (
              <div className="mb-2 space-y-1">
                {m.tools.map((t, idx) => (
                  <div
                    key={`${t.name}-${idx}`}
                    className="flex items-center gap-2 rounded-md border border-border bg-bg/50 px-2 py-1 font-mono text-[10px] text-muted"
                  >
                    <span className="text-primary">✓</span>
                    <span className="text-text">{t.name}</span>
                    {t.target ? <span className="truncate text-muted-2">{t.target}</span> : null}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="whitespace-pre-wrap text-text [&_strong]:font-bold [&_strong]:text-primary">
              {renderLiteMarkdown(m.content)}
            </div>
            {m.error && m.retryPrompt ? (
              <button
                type="button"
                onClick={() => onRetry(m.retryPrompt!)}
                disabled={busy}
                className="mt-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[11px] font-semibold text-primary transition hover:border-primary disabled:opacity-40"
              >
                Retry analysis
              </button>
            ) : null}
          </motion.div>
        );
      })}
    </div>
  );
}

function AtlasComposer({
  input,
  busy,
  onChange,
  onSend,
}: {
  input: string;
  busy: boolean;
  onChange: (v: string) => void;
  onSend: () => void;
}) {
  return (
    <div className="border-t border-border p-3">
      <form
        className="flex items-center gap-2 rounded-xl border border-border bg-bg px-3 py-2 focus-within:border-primary/40"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <input
          value={input}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Ask ${AGENT_ID} anything`}
          disabled={busy}
          className="min-w-0 flex-1 bg-transparent text-sm text-text placeholder:text-muted-2 focus:outline-none disabled:opacity-50"
          aria-label={`Ask ${AGENT_ID}`}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-bg transition hover:brightness-110 disabled:opacity-40"
          aria-label="Send"
        >
          ↑
        </button>
      </form>
    </div>
  );
}

function renderLiteMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function SparkIcon({ large }: { large?: boolean }) {
  const s = large ? 22 : 14;
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2l1.6 6.2L20 10l-6.4 1.8L12 18l-1.6-6.2L4 10l6.4-1.8L12 2z" />
    </svg>
  );
}
