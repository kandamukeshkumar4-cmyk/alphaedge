"use client";

import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/cn";

// Paper-trading card for the market rail.
export function PromoCard() {
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="relative p-4">
        <button
          onClick={() => setClosed(true)}
          className="absolute right-3 top-3 grid h-7 w-7 place-items-center rounded-md border border-border text-muted transition hover:border-border-light hover:text-text"
          aria-label="Dismiss"
        >
          ✕
        </button>
        <div className="text-[11px] font-black uppercase tracking-[0.14em] text-accent">
          Paper trading
        </div>
        <h3 className="mt-3 text-xl font-black tracking-tight text-text">
          Simulated funds only
        </h3>
        <p className="mt-2 max-w-[220px] text-sm leading-relaxed text-muted">
          Practice trading with real market data. No real money at stake.
        </p>

        <div className="mt-5 rounded-xl border border-border bg-bg/65 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-muted">Paper balance</span>
            <span className="font-mono text-lg font-black text-accent">$100,000</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full w-[78%] rounded-full bg-accent" />
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="h-8 rounded border border-border bg-surface-2" />
            <div className="h-8 rounded border border-border bg-surface-2" />
            <div className="h-8 rounded border border-border bg-surface-2" />
          </div>
        </div>

        <Link
          href="/auth/signup"
          className="mt-4 inline-flex h-11 w-full items-center justify-center rounded-xl bg-accent text-sm font-black text-white shadow-glow transition hover:brightness-110"
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
      <div className="mt-3 flex rounded-xl border border-border bg-bg p-0.5">
        {VIEWS.map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={cn(
              "flex-1 rounded-lg py-1.5 text-xs font-semibold transition",
              view === v ? "bg-accent text-white" : "text-muted hover:text-text",
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
