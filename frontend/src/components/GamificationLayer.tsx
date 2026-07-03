"use client";

// Visual layer for gamification: confetti bursts, XP reward toasts, and the
// header level ring. Respects prefers-reduced-motion (confetti disabled).
import { useEffect, useMemo, useState } from "react";
import { useGamification } from "@/lib/gamification";

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

const CONFETTI_COLORS = ["#0052ff", "#05b169", "#f4b000", "#ffffff", "#a8acb3"];

type Particle = {
  left: number;
  delay: number;
  duration: number;
  color: string;
  drift: number;
  size: number;
  spin: number;
};

function makeParticles(seed: number): Particle[] {
  // Deterministic per burst so React strict-mode double render stays stable.
  const out: Particle[] = [];
  let s = seed * 2654435761 + 1;
  const rand = () => {
    s = (s * 1103515245 + 12345) % 2147483648;
    return s / 2147483648;
  };
  for (let i = 0; i < 28; i++) {
    out.push({
      left: rand() * 100,
      delay: rand() * 0.25,
      duration: 1 + rand() * 0.9,
      color: CONFETTI_COLORS[Math.floor(rand() * CONFETTI_COLORS.length)],
      drift: (rand() - 0.5) * 160,
      size: 6 + rand() * 6,
      spin: 360 + rand() * 540,
    });
  }
  return out;
}

function ConfettiBurst() {
  const { confettiKey } = useGamification();
  const reduced = usePrefersReducedMotion();
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (confettiKey === 0) return;
    setActive(confettiKey);
    const t = setTimeout(() => setActive(0), 2200);
    return () => clearTimeout(t);
  }, [confettiKey]);

  const particles = useMemo(() => (active ? makeParticles(active) : []), [active]);

  if (!active || reduced) return null;
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[90] overflow-hidden">
      {particles.map((p, i) => (
        <span
          key={`${active}-${i}`}
          className="absolute top-[-16px] block rounded-[2px]"
          style={{
            left: `${p.left}%`,
            width: p.size,
            height: p.size * 0.6,
            backgroundColor: p.color,
            animation: `ae-confetti ${p.duration}s cubic-bezier(0.25,0.4,0.45,1) ${p.delay}s both`,
            ["--drift" as string]: `${p.drift}px`,
            ["--spin" as string]: `${p.spin}deg`,
          }}
        />
      ))}
      <style>{`
        @keyframes ae-confetti {
          0% { transform: translate3d(0, -20px, 0) rotate(0deg); opacity: 1; }
          100% { transform: translate3d(var(--drift), 105vh, 0) rotate(var(--spin)); opacity: 0.9; }
        }
      `}</style>
    </div>
  );
}

function RewardToasts() {
  const { rewards } = useGamification();
  if (rewards.length === 0) return null;
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-20 left-1/2 z-[95] flex -translate-x-1/2 flex-col items-center gap-2"
    >
      {rewards.map((r) => (
        <div
          key={r.id}
          className="animate-xp-pop rounded-pill border border-accent/40 bg-surface px-4 py-1.5 shadow-glow-blue"
        >
          <span className="font-mono text-sm font-semibold text-accent">+{r.amount} XP</span>
          <span className="ml-2 text-xs text-muted">{r.reason}</span>
        </div>
      ))}
    </div>
  );
}

export function LevelChip() {
  const { level, progress, state } = useGamification();
  const r = 9;
  const c = 2 * Math.PI * r;
  return (
    <div
      className="flex items-center gap-2 rounded-pill border border-border bg-surface px-2.5 py-1"
      title={`Level ${level} · ${state.xp} XP · ${state.streak}-day streak`}
      data-tour="level"
    >
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <circle cx="11" cy="11" r={r} fill="none" stroke="#26292f" strokeWidth="3" />
        <circle
          cx="11"
          cy="11"
          r={r}
          fill="none"
          stroke="#0052ff"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - progress)}
          transform="rotate(-90 11 11)"
          style={{ transition: "stroke-dashoffset 0.6s cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <span className="hidden font-mono text-xs font-semibold text-text sm:inline">
        L{level}
      </span>
      {state.streak > 1 && (
        <span className="hidden items-center gap-0.5 font-mono text-xs font-semibold text-gold sm:flex">
          <FlameIcon />
          {state.streak}
        </span>
      )}
    </div>
  );
}

function FlameIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="animate-streak-flame"
      aria-hidden
    >
      <path d="M12 2c1 4-3 5-3 9a3 3 0 0 0 6 0c0-1.5-.8-2.6-.8-2.6S17 10 17 13a5 5 0 0 1-10 0c0-5 5-7 5-11z" />
    </svg>
  );
}

export function GamificationLayer() {
  return (
    <>
      <ConfettiBurst />
      <RewardToasts />
    </>
  );
}
