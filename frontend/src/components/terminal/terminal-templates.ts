/**
 * Loop V79 (A8) — Skills gallery templates shared by the sidebar Skills group,
 * the composer Skills chip, and the empty-state template cards.
 * Questions target the canonical paper market only — research, no execution.
 */

import { TERMINAL_CANONICAL_MARKET, TERMINAL_CANONICAL_QUESTION } from "@/lib/terminal-api";

export type TerminalTemplate = {
  id: string;
  name: string;
  /** One-line "what it does" for cards / sidebar. */
  blurb: string;
  question: string;
  /** Tailwind dot class — mint/blue/amber/gray only (never danger-red). */
  dot: string;
};

export const TERMINAL_TEMPLATES: TerminalTemplate[] = [
  {
    id: "confluence",
    name: "Full confluence scan",
    blurb: "Price, whale, news, sentiment, model — one paper verdict.",
    question: TERMINAL_CANONICAL_QUESTION,
    dot: "bg-primary",
  },
  {
    id: "whale",
    name: "Whale flow digest",
    blurb: "Large simulated flow on the board, summarized.",
    question: `Summarize the largest paper whale flow on ${TERMINAL_CANONICAL_MARKET} and what it implies.`,
    dot: "bg-gold",
  },
  {
    id: "price",
    name: "Pre-game price read",
    blurb: "Candles and drift into tip-off, in one card.",
    question: `Read the price action on ${TERMINAL_CANONICAL_MARKET} into tip-off — drift, wicks, and liquidity (paper).`,
    dot: "bg-secondary",
  },
  {
    id: "news",
    name: "News & sentiment skim",
    blurb: "Headlines plus tone, cautious reads flagged.",
    question: `Skim news and sentiment for ${TERMINAL_CANONICAL_MARKET} — anything that moves the paper read?`,
    dot: "bg-accent",
  },
  {
    id: "arb",
    name: "Arb watch",
    blurb: "Cross-venue gap check after fees.",
    question: `Check the cross-venue gap on ${TERMINAL_CANONICAL_MARKET} after fees — any paper dutching edge?`,
    dot: "bg-muted",
  },
];

/** Empty-state teaser cards: the first three templates, per UI-DIRECTION. */
export const EMPTY_STATE_TEMPLATES = TERMINAL_TEMPLATES.slice(0, 3);
