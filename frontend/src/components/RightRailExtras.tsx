"use client";

import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/cn";

// Promo card (mirrors Kalshi's "Intro to…" card) — our own paper-trading copy.
export function PromoCard() {
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="relative h-28 bg-[radial-gradient(120%_120%_at_50%_-20%,rgba(47,107,255,0.55),rgba(8,8,12,0.1))]">
        <button
          onClick={() => setClosed(true)}
          className="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-md bg-black/30 text-muted transition hover:text-text"
          aria-label="Dismiss"
        >
          ✕
        </button>
        <div className="absolute inset-0 opacity-40 [background-image:repeating-linear-gradient(90deg,transparent,transparent_7px,rgba(77,141,255,0.25)_8px)]" />
      </div>
      <div className="p-4 text-center">
        <h3 className="text-sm font-black text-text">Intro to AlphaEdge</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Practice AI-priced prediction markets with $100,000 in paper money.
        </p>
        <Link
          href="/auth/signup"
          className="mt-3 inline-block w-full rounded-lg bg-primary py-2 text-sm font-bold text-white transition hover:bg-accent"
        >
          Get started
        </Link>
      </div>
    </div>
  );
}

const BANNERS: { label: string; icon: string; href: string; gradient: string }[] = [
  {
    label: "Pro Basketball Playoffs",
    icon: "🏀",
    href: "/markets?cat=Sports",
    gradient: "from-[#3a2a0e] to-[#1a1208]",
  },
  {
    label: "Election Center 2026",
    icon: "🗳️",
    href: "/markets?cat=Politics",
    gradient: "from-[#0e1a33] to-[#0a1020]",
  },
  {
    label: "Crypto Markets",
    icon: "₿",
    href: "/markets?cat=Crypto",
    gradient: "from-[#2a0e13] to-[#160a0c]",
  },
];

export function CategoryBanners() {
  return (
    <div className="space-y-2.5">
      {BANNERS.map((b) => (
        <Link
          key={b.label}
          href={b.href}
          className={cn(
            "flex items-center gap-3 rounded-xl border border-border bg-gradient-to-r px-4 py-3 transition hover:border-border-light",
            b.gradient,
          )}
        >
          <span className="text-xl">{b.icon}</span>
          <span className="flex-1 text-sm font-bold text-text">{b.label}</span>
          <span className="text-muted">›</span>
        </Link>
      ))}
    </div>
  );
}

const VIEWS = ["Prediction", "Sports", "Trader"] as const;

export function CustomizeView() {
  const [view, setView] = useState<(typeof VIEWS)[number]>("Prediction");
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-black text-text">Customize your view</h3>
        <button
          onClick={() => setClosed(true)}
          className="text-muted transition hover:text-text"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
      <div className="mt-3 flex rounded-lg border border-border bg-bg p-0.5">
        {VIEWS.map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={cn(
              "flex-1 rounded-md py-1.5 text-xs font-semibold transition",
              view === v ? "bg-surface-3 text-text" : "text-muted hover:text-text",
            )}
          >
            {v}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-2">
        Switch between prediction, sports, and trader layouts anytime in settings.
      </p>
    </div>
  );
}
