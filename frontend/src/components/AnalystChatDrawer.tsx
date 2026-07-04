"use client";

/**
 * U05 — AnalystChatDrawer
 *
 * Analysis-only chat drawer for market detail (right rail) and /portfolio.
 * Connects to POST /api/v1/assistant/chat.
 *
 * HARD GUARDRAIL: this component has NO order/trade controls.
 * The "Analysis only — this assistant cannot place trades." banner is
 * PERMANENT and cannot be hidden or removed.
 */

import { useRef, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CitationChip {
  source: string;
  label: string;
}

interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
  citations?: CitationChip[];
  tools_used?: string[];
}

interface AssistantChatResponse {
  reply: string;
  citations: CitationChip[];
  tools_used: string[];
  paper_trading_only: boolean;
  analysis_only_banner: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ANALYSIS_ONLY_BANNER = "Analysis only — this assistant cannot place trades.";

const SUGGESTED_PROMPTS_MARKET = [
  "Why did odds move today?",
  "What's the bear case?",
  "Explain the model reasoning.",
];

const SUGGESTED_PROMPTS_PORTFOLIO = [
  "What's my overall exposure?",
  "Where is my concentration risk?",
  "What's the bear case?",
];

// ── Source chip colours ───────────────────────────────────────────────────────

const SOURCE_COLOURS: Record<string, string> = {
  news: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  exposure: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  briefs: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  features: "bg-teal-500/15 text-teal-300 border-teal-500/30",
  agent_trace: "bg-green-500/15 text-green-300 border-green-500/30",
  default: "bg-surface-2 text-muted border-border",
};

function citationColour(source: string): string {
  return SOURCE_COLOURS[source] ?? SOURCE_COLOURS.default;
}

// ── Tool chip label ───────────────────────────────────────────────────────────

const TOOL_LABELS: Record<string, string> = {
  get_odds: "looked up: odds",
  get_features: "looked up: features",
  get_exposure: "looked up: exposure",
  get_briefs: "looked up: briefs",
  get_agent_trace: "looked up: agent trace",
};

function toolLabel(t: string): string {
  return TOOL_LABELS[t] ?? `looked up: ${t}`;
}

// ── Message renderer ──────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: AssistantMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-accent text-white"
            : "bg-surface-2 text-text border border-border"
        }`}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>

        {/* Tool chips */}
        {!isUser && msg.tools_used && msg.tools_used.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.tools_used.map((t) => (
              <span
                key={t}
                className="inline-flex items-center rounded-md border border-border bg-surface px-1.5 py-0.5 text-[10px] font-mono text-muted"
              >
                {toolLabel(t)}
              </span>
            ))}
          </div>
        )}

        {/* Citation chips — reuses brief citation styling */}
        {!isUser && msg.citations && msg.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.citations.map((c, i) => (
              <span
                key={`${c.source}-${i}`}
                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold ${citationColour(c.source)}`}
              >
                {c.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface AnalystChatDrawerProps {
  /** If provided, scopes the chat to this market slug */
  marketSlug?: string;
  /** 'market' = suggested prompts for market page; 'portfolio' = portfolio prompts */
  context?: "market" | "portfolio";
}

export function AnalystChatDrawer({
  marketSlug,
  context = "market",
}: AnalystChatDrawerProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const suggestedPrompts =
    context === "portfolio" ? SUGGESTED_PROMPTS_PORTFOLIO : SUGGESTED_PROMPTS_MARKET;

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;
    setError(null);

    const userMsg: AssistantMessage = { role: "user", content: text.trim() };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    // Scroll to bottom
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);

    try {
      const historyPayload = nextMessages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const endpoint = API_BASE
        ? `${API_BASE}/api/v1/assistant/chat`
        : "/api/v1/assistant/chat";

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text.trim(),
          market_slug: marketSlug ?? null,
          history: historyPayload.slice(0, -1), // all but the last (current) message
        }),
      });

      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Request failed (${res.status}): ${body.slice(0, 120)}`);
      }

      const data: AssistantChatResponse = await res.json();

      const assistantMsg: AssistantMessage = {
        role: "assistant",
        content: data.reply,
        citations: data.citations,
        tools_used: data.tools_used,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed. Try again.");
    } finally {
      setLoading(false);
      setTimeout(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 50);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void sendMessage(input);
  }

  // ── Collapsed trigger ────────────────────────────────────────────────────────
  if (!open) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-3">
        {/* PERMANENT analysis-only banner — visible even when collapsed */}
        <p className="mb-2 rounded-lg bg-amber-500/10 px-2.5 py-1.5 text-[11px] font-semibold text-amber-400 border border-amber-500/20">
          {ANALYSIS_ONLY_BANNER}
        </p>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="w-full rounded-xl border border-border bg-surface-2 px-4 py-2.5 text-left text-sm text-muted transition hover:border-accent hover:text-text"
        >
          <span className="font-semibold text-text">Ask the analyst</span>
          <span className="ml-2 text-muted">→</span>
        </button>
      </div>
    );
  }

  // ── Expanded drawer ──────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-surface overflow-hidden">
      {/* Header — PERMANENT banner always at top */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <span className="text-sm font-bold text-text">Ask the analyst</span>
          {marketSlug && (
            <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-muted">
              {marketSlug}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close chat"
          className="rounded-lg p-1 text-muted transition hover:text-text"
        >
          ✕
        </button>
      </div>

      {/* PERMANENT analysis-only banner — cannot be removed */}
      <div
        data-testid="analysis-only-banner"
        className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-[11px] font-semibold text-amber-400"
      >
        {ANALYSIS_ONLY_BANNER}
      </div>

      {/* Message area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-72 min-h-[120px]">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted">Suggested questions:</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestedPrompts.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void sendMessage(p)}
                  className="rounded-xl border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted transition hover:border-accent hover:text-text"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-surface-2 border border-border px-3.5 py-2.5 text-xs text-muted animate-pulse">
              Analysing…
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2 border border-red-500/20">
            {error}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-border px-3 py-2.5 flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={loading}
          className="flex-1 rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-accent px-3 py-2 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}
