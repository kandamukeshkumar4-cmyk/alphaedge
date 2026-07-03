"use client";

// First-visit guided tour. Spotlights each tab in the header, explains what it
// does, awards XP per step, and ends with a confetti celebration. Re-launchable
// from the header ("Tour"). Keyboard: Esc to exit, arrows to move.
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useGamification } from "@/lib/gamification";

const TOUR_KEY = "ae_tour_done_v1";

type TourStep = {
  target: string; // data-tour id
  title: string;
  body: string;
  href?: string;
};

const STEPS: TourStep[] = [
  {
    target: "logo",
    title: "Welcome to AlphaEdge",
    body: "A paper-trading prediction market desk with a real AI research analyst behind it. Everything here uses simulated funds — the data and the AI are real, the money is not. Let's take 60 seconds to see what each tab does.",
  },
  {
    target: "ai-desk",
    title: "The AI desk",
    body: "This is the desk itself: the analyst's latest briefs, the signal pipeline that triggers them, and the public scoreboard where every call gets graded. It updates as the desk works.",
    href: "/",
  },
  {
    target: "nav-markets",
    title: "Markets",
    body: "Live prediction markets mirrored from Kalshi and Polymarket over real-time WebSocket feeds. Prices update live — watch a number flash when it moves.",
    href: "/markets",
  },
  {
    target: "nav-research",
    title: "Research",
    body: "Every brief here is written by the AI analyst when real signals align — price jumps, whale wallets moving, breaking news the market hasn't priced. Each brief cites its evidence and stakes a falsifiable claim.",
    href: "/research",
  },
  {
    target: "nav-track-record",
    title: "Track record",
    body: "Every claim the analyst makes gets graded against what the market actually did — no lookahead, misses shown next to wins. This is the AI's public scoreboard.",
    href: "/track-record",
  },
  {
    target: "nav-signals",
    title: "Signals",
    body: "The raw signal feed: smart-money wallets, price dislocations, and news-lag events before they become research briefs.",
    href: "/signals",
  },
  {
    target: "nav-forecast",
    title: "Forecast",
    body: "The ML model's probability vs the market price. When they disagree past a threshold, that's an edge — and the analyst gets triggered.",
    href: "/forecast",
  },
  {
    target: "nav-portfolio",
    title: "Portfolio",
    body: "Your paper positions, PnL, and order history. You start with $100,000 in simulated funds — every trade earns XP and builds your streak.",
    href: "/portfolio",
  },
  {
    target: "level",
    title: "Your level",
    body: "Trade, explore, and check in daily to earn XP and keep your streak alive. Finishing this tour earns your first bonus — enjoy the desk.",
  },
];

type Rect = { top: number; left: number; width: number; height: number };

function measure(target: string): Rect | null {
  const el = document.querySelector<HTMLElement>(`[data-tour="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

export function OnboardingTour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const { awardXp, celebrate, markTourDone } = useGamification();

  // Auto-open on first visit (never inside admin).
  useEffect(() => {
    if (pathname.startsWith("/admin") || pathname.startsWith("/auth")) return;
    try {
      if (!window.localStorage.getItem(TOUR_KEY)) {
        const t = setTimeout(() => setOpen(true), 900);
        return () => clearTimeout(t);
      }
    } catch {
      // storage unavailable — skip auto tour
    }
  }, [pathname]);

  // Allow the header button to relaunch the tour.
  useEffect(() => {
    const onLaunch = () => {
      setStep(0);
      setOpen(true);
    };
    window.addEventListener("ae:tour", onLaunch);
    return () => window.removeEventListener("ae:tour", onLaunch);
  }, []);

  const current = STEPS[step];

  // Measure the spotlight target (re-measure on resize/scroll while open).
  useEffect(() => {
    if (!open || !current) return;
    const update = () => setRect(measure(current.target));
    update();
    const t = setTimeout(update, 350); // after nav/layout settle
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, current, pathname]);

  const finish = useCallback(
    (completed: boolean) => {
      setOpen(false);
      try {
        window.localStorage.setItem(TOUR_KEY, "1");
      } catch {
        // fine — tour will re-offer next visit
      }
      markTourDone();
      if (completed) {
        awardXp(120, "Tour complete");
        celebrate();
      }
    },
    [awardXp, celebrate, markTourDone],
  );

  const go = useCallback(
    (dir: 1 | -1) => {
      const next = step + dir;
      if (next >= STEPS.length) {
        finish(true);
        return;
      }
      if (next < 0) return;
      const target = STEPS[next];
      if (dir === 1) awardXp(15, target.title);
      setStep(next);
      if (target.href && target.href !== pathname) router.push(target.href);
    },
    [step, pathname, router, awardXp, finish],
  );

  // Keyboard support.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish(false);
      if (e.key === "ArrowRight" || e.key === "Enter") go(1);
      if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, go, finish]);

  const spotlight = useMemo(() => {
    if (!rect) return null;
    const pad = 6;
    return {
      top: rect.top - pad,
      left: rect.left - pad,
      width: rect.width + pad * 2,
      height: rect.height + pad * 2,
    };
  }, [rect]);

  if (!open || !current) return null;

  const cardTop = spotlight ? Math.min(spotlight.top + spotlight.height + 14, window.innerHeight - 220) : 96;
  const cardLeft = spotlight
    ? Math.max(16, Math.min(spotlight.left, window.innerWidth - 356))
    : Math.max(16, window.innerWidth / 2 - 170);

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label="Product tour">
      {/* Scrim with spotlight cutout */}
      {spotlight ? (
        <div
          className="absolute rounded-xl transition-all duration-300"
          style={{
            top: spotlight.top,
            left: spotlight.left,
            width: spotlight.width,
            height: spotlight.height,
            boxShadow: "0 0 0 9999px rgba(3,4,6,0.78)",
            border: "1.5px solid rgba(0,82,255,0.9)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-bg/80" />
      )}

      {/* Step card */}
      <div
        className="absolute w-[340px] max-w-[calc(100vw-32px)] rounded-2xl border border-border bg-surface p-5 shadow-lift"
        style={{ top: cardTop, left: cardLeft }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="rounded-pill bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent">
            {step + 1} / {STEPS.length}
          </span>
          <button
            type="button"
            onClick={() => finish(false)}
            className="rounded-pill px-2 py-0.5 text-xs text-muted hover:text-text"
          >
            Skip
          </button>
        </div>
        <h3 className="text-base font-semibold text-text">{current.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-muted">{current.body}</p>

        {/* Progress dots */}
        <div className="mt-4 flex items-center gap-1.5" aria-hidden>
          {STEPS.map((s, i) => (
            <span
              key={s.target}
              className={`h-1.5 rounded-pill transition-all duration-300 ${
                i <= step ? "w-5 bg-accent" : "w-1.5 bg-border-light"
              }`}
            />
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={() => go(-1)}
            disabled={step === 0}
            className="rounded-pill border border-border px-4 py-2 text-sm font-semibold text-muted enabled:hover:text-text disabled:opacity-40"
          >
            Back
          </button>
          <button
            type="button"
            onClick={() => go(1)}
            className="rounded-pill bg-accent px-5 py-2 text-sm font-semibold text-white transition hover:bg-accent-active"
          >
            {step === STEPS.length - 1 ? "Finish · +120 XP" : "Next · +15 XP"}
          </button>
        </div>
      </div>
    </div>
  );
}
