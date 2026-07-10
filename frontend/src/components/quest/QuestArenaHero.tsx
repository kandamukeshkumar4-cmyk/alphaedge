"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

// Pixel-pass Traders Arena hero — matches QuestFlow video layout:
// left copy + prize badge + gold trophy bloom + AI provider strip + dots.

const PROVIDERS = [
  "Gemini",
  "Anthropic",
  "OpenAI",
  "MiniMax",
  "DeepSeek",
  "Qwen",
  "Mimo",
  "Kimi",
  "Mistral",
];

const SLIDES = [
  {
    kicker: "Compete from Jun 15 to Jul 15 across 4 rounds · Weekly winners rewarded",
    lead: "Join AlphaEdge",
    accent: "Traders Arena",
    prize: "$10,000",
    title: "Agentic World Cup",
    titleSub: "for Traders",
  },
  {
    kicker: "Featured · FIFA World Cup 2026 · Live match markets",
    lead: "World Cup",
    accent: "’26",
    prize: "$10,000",
    title: "Every Match",
    titleSub: "Every Signal",
  },
] as const;

export function QuestArenaHero() {
  const [slide, setSlide] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSlide((s) => (s + 1) % SLIDES.length), 7000);
    return () => clearInterval(id);
  }, []);
  const s = SLIDES[slide];

  return (
    <div className="relative overflow-hidden rounded-[14px] border border-border">
      <div
        className="relative grid min-h-[228px] grid-cols-1 items-center gap-5 px-5 py-6 sm:grid-cols-[1.15fr_auto_0.95fr] sm:px-8 sm:py-7"
        style={{
          background:
            "radial-gradient(70% 120% at 92% 40%, rgba(246,194,68,0.28) 0%, rgba(246,194,68,0.06) 32%, transparent 58%), radial-gradient(90% 140% at 8% 85%, rgba(0,232,176,0.22) 0%, rgba(0,201,160,0.06) 38%, transparent 65%), linear-gradient(105deg, #050908 12%, #0a1a15 55%, #0c221c 100%)",
        }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.22]"
          style={{
            background:
              "repeating-linear-gradient(118deg, transparent 0px, transparent 28px, rgba(0,232,176,0.06) 28px, rgba(0,232,176,0.06) 29px)",
          }}
        />

        <div className="relative z-10 min-w-0">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={slide}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
            >
              <p className="max-w-md text-[11px] font-medium leading-relaxed text-muted">
                {s.kicker}
              </p>
              <h1 className="mt-2 text-[28px] font-black leading-[0.95] tracking-tight text-text sm:text-[34px]">
                {s.lead} <span className="text-primary">{s.accent}</span>
              </h1>
              <div className="mt-4 inline-flex items-center gap-2 rounded-lg border border-primary/35 bg-primary-dim/70 px-3 py-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-primary">
                  Trade to win
                </span>
                <span className="font-mono text-sm font-black text-text">{s.prize}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">
                  Prize pool
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  href="/markets"
                  className="rounded-lg bg-primary px-4 py-2 text-[13px] font-bold text-bg shadow-glow transition hover:brightness-110"
                >
                  Enter the arena
                </Link>
                <Link
                  href="/leaderboard"
                  className="rounded-lg border border-border-light bg-bg/35 px-4 py-2 text-[13px] font-semibold text-text backdrop-blur transition hover:border-primary"
                >
                  View leaderboard
                </Link>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Gold trophy bloom */}
        <div className="relative mx-auto hidden h-[150px] w-[130px] sm:block">
          <div
            className="absolute inset-0 rounded-full opacity-70 blur-2xl"
            style={{
              background:
                "radial-gradient(circle, rgba(246,194,68,0.55) 0%, rgba(246,194,68,0.12) 45%, transparent 70%)",
            }}
          />
          <TrophyArt />
        </div>

        <div className="relative hidden text-right sm:block">
          <h2 className="text-[26px] font-black leading-[1.05] tracking-tight text-text sm:text-[30px]">
            {s.title}
            <span className="mt-1 block bg-gradient-to-r from-gold via-gold to-primary bg-clip-text text-transparent">
              {s.titleSub}
            </span>
          </h2>
        </div>
      </div>

      <div className="no-scrollbar flex items-center gap-3 overflow-x-auto border-t border-border/70 bg-bg/50 px-5 py-2.5 sm:px-8">
        <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-2">
          Tailored AI by
        </span>
        {PROVIDERS.map((p) => (
          <span
            key={p}
            className="shrink-0 rounded-md border border-border/80 bg-surface/60 px-2 py-0.5 text-[11px] font-semibold text-muted"
          >
            {p}
          </span>
        ))}
      </div>

      <div className="flex justify-center gap-1.5 py-2">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            type="button"
            aria-label={`Slide ${i + 1}`}
            onClick={() => setSlide(i)}
            className={
              i === slide
                ? "h-1 w-5 rounded-full bg-primary transition-all"
                : "h-1 w-1.5 rounded-full bg-surface-3 transition-all"
            }
          />
        ))}
      </div>
    </div>
  );
}

function TrophyArt() {
  return (
    <svg
      viewBox="0 0 120 140"
      className="relative z-10 h-full w-full drop-shadow-[0_8px_24px_rgba(246,194,68,0.35)]"
      aria-hidden
    >
      <defs>
        <linearGradient id="cup" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFE08A" />
          <stop offset="45%" stopColor="#F6C244" />
          <stop offset="100%" stopColor="#C4891A" />
        </linearGradient>
        <linearGradient id="stem" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F6C244" />
          <stop offset="100%" stopColor="#A56B12" />
        </linearGradient>
      </defs>
      <path
        d="M28 28h64c2 18 2 34-6 48-6 10-18 18-26 20-8-2-20-10-26-20-8-14-8-30-6-48z"
        fill="url(#cup)"
      />
      <path d="M22 34c-10 4-16 14-14 26 2 10 10 16 20 18" fill="none" stroke="#F6C244" strokeWidth="5" />
      <path d="M98 34c10 4 16 14 14 26-2 10-10 16-20 18" fill="none" stroke="#F6C244" strokeWidth="5" />
      <rect x="52" y="92" width="16" height="18" rx="2" fill="url(#stem)" />
      <path d="M38 118h44c2 6-4 12-22 12s-24-6-22-12z" fill="url(#stem)" />
      <circle cx="60" cy="48" r="8" fill="#FFF3C4" opacity="0.55" />
    </svg>
  );
}
