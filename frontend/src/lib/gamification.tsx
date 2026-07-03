"use client";

// Gamification layer: XP + levels, daily streak, confetti bursts, reward
// toasts. Local-only progression (localStorage) — never touches money or the
// order path; it decorates real actions (visits, trades, tour steps).
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const STORE_KEY = "ae_gamification_v1";

export type GamificationState = {
  xp: number;
  streak: number;
  lastVisitDay: string | null;
  tradesPlaced: number;
  tourDone: boolean;
};

const DEFAULT_STATE: GamificationState = {
  xp: 0,
  streak: 0,
  lastVisitDay: null,
  tradesPlaced: 0,
  tourDone: false,
};

export function levelForXp(xp: number): number {
  return Math.max(1, Math.floor(Math.sqrt(xp / 60)) + 1);
}

export function xpForLevel(level: number): number {
  return (level - 1) * (level - 1) * 60;
}

export function levelProgress(xp: number): number {
  const level = levelForXp(xp);
  const floor = xpForLevel(level);
  const ceil = xpForLevel(level + 1);
  if (ceil === floor) return 0;
  return Math.min(1, Math.max(0, (xp - floor) / (ceil - floor)));
}

type RewardEvent = { id: number; amount: number; reason: string };

type GamificationContextValue = {
  state: GamificationState;
  level: number;
  progress: number;
  awardXp: (amount: number, reason: string) => void;
  celebrate: () => void;
  markTradePlaced: () => void;
  markTourDone: () => void;
  rewards: RewardEvent[];
  confettiKey: number;
};

const GamificationContext = createContext<GamificationContextValue | null>(null);

function loadState(): GamificationState {
  if (typeof window === "undefined") return DEFAULT_STATE;
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return DEFAULT_STATE;
    return { ...DEFAULT_STATE, ...(JSON.parse(raw) as Partial<GamificationState>) };
  } catch {
    return DEFAULT_STATE;
  }
}

function dayKey(d = new Date()): string {
  return d.toISOString().slice(0, 10);
}

export function GamificationProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GamificationState>(DEFAULT_STATE);
  const [rewards, setRewards] = useState<RewardEvent[]>([]);
  const [confettiKey, setConfettiKey] = useState(0);
  const rewardId = useRef(0);
  const hydrated = useRef(false);

  // Hydrate + daily streak check-in.
  useEffect(() => {
    const loaded = loadState();
    const today = dayKey();
    if (loaded.lastVisitDay !== today) {
      const yesterday = dayKey(new Date(Date.now() - 86_400_000));
      const streak = loaded.lastVisitDay === yesterday ? loaded.streak + 1 : 1;
      const bonus = 20 + Math.min(streak, 7) * 5;
      const next = {
        ...loaded,
        streak,
        lastVisitDay: today,
        xp: loaded.xp + bonus,
      };
      setState(next);
      rewardId.current += 1;
      setRewards((r) => [
        ...r,
        {
          id: rewardId.current,
          amount: bonus,
          reason: streak > 1 ? `Day ${streak} streak` : "Daily check-in",
        },
      ]);
    } else {
      setState(loaded);
    }
    hydrated.current = true;
  }, []);

  // Persist.
  useEffect(() => {
    if (!hydrated.current) return;
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch {
      // storage unavailable — progression just doesn't persist
    }
  }, [state]);

  // Expire reward toasts.
  useEffect(() => {
    if (rewards.length === 0) return;
    const t = setTimeout(() => setRewards((r) => r.slice(1)), 1800);
    return () => clearTimeout(t);
  }, [rewards]);

  const celebrate = useCallback(() => setConfettiKey((k) => k + 1), []);

  const awardXp = useCallback(
    (amount: number, reason: string) => {
      setState((prev) => {
        const next = { ...prev, xp: prev.xp + amount };
        if (levelForXp(next.xp) > levelForXp(prev.xp)) {
          // Level up — full celebration.
          setConfettiKey((k) => k + 1);
        }
        return next;
      });
      rewardId.current += 1;
      setRewards((r) => [...r.slice(-3), { id: rewardId.current, amount, reason }]);
    },
    [],
  );

  const markTradePlaced = useCallback(() => {
    setState((prev) => ({ ...prev, tradesPlaced: prev.tradesPlaced + 1 }));
    awardXp(40, "Paper trade placed");
    setConfettiKey((k) => k + 1);
  }, [awardXp]);

  const markTourDone = useCallback(() => {
    setState((prev) => ({ ...prev, tourDone: true }));
  }, []);

  const value = useMemo<GamificationContextValue>(
    () => ({
      state,
      level: levelForXp(state.xp),
      progress: levelProgress(state.xp),
      awardXp,
      celebrate,
      markTradePlaced,
      markTourDone,
      rewards,
      confettiKey,
    }),
    [state, awardXp, celebrate, markTradePlaced, markTourDone, rewards, confettiKey],
  );

  return (
    <GamificationContext.Provider value={value}>{children}</GamificationContext.Provider>
  );
}

const NOOP_VALUE: GamificationContextValue = {
  state: DEFAULT_STATE,
  level: 1,
  progress: 0,
  awardXp: () => {},
  celebrate: () => {},
  markTradePlaced: () => {},
  markTourDone: () => {},
  rewards: [],
  confettiKey: 0,
};

// Safe outside the provider (tests, isolated component renders) — no-ops.
export function useGamification(): GamificationContextValue {
  return useContext(GamificationContext) ?? NOOP_VALUE;
}
