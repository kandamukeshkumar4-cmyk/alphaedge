"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import type { SignalFeedItem } from "@/lib/signals-dashboard-api";

const LAST_SIGNAL_TS_KEY = "alphaedge.lastSignalTs";
const POLL_INTERVAL_MS = 30_000;
// Never surface a backlog of historical price-jump rows as toasts — only the
// newest few after a reconnect / first poll with an old watermark.
const MAX_TOAST_ALERTS = 2;

export type SignalAlertOutcome = {
  name: string;
  price: number;
  imageUrl: string | null;
};

export type SignalAlert = {
  id: string;
  signalType: string;
  marketTitle: string;
  confidencePct: number | null;
  createdAt: string;
  // Loop V78 (N1) — real stored market context for the Polymarket-style card.
  // All nullable: honest omission when the market is not mirrored locally.
  marketSlug: string;
  categoryLabel: string | null;
  icon: string | null;
  imageUrl: string | null;
  volume: number | null;
  traders: number | null;
  marketCount: number | null;
  outcomes: SignalAlertOutcome[];
};

type SignalFeedResponse = {
  signals: SignalFeedItem[];
};

function readLastSignalTs(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(LAST_SIGNAL_TS_KEY);
}

function toAlert(item: SignalFeedItem): SignalAlert {
  return {
    id: item.id,
    signalType: item.signal_type,
    // Prefer the real stored market title; fall back to the payload name
    // (often a slug — the card humanizes it as a last resort).
    marketTitle: item.market_title ?? item.market_name,
    confidencePct:
      item.implied_edge === null ? null : Math.round(item.implied_edge * 100),
    createdAt: item.created_at,
    marketSlug: item.market_id,
    categoryLabel: item.category ?? null,
    icon: item.icon ?? null,
    imageUrl: item.image_url ?? null,
    volume: item.volume ?? null,
    traders: item.traders ?? null,
    marketCount: item.market_count ?? null,
    outcomes: (item.outcomes ?? []).map((outcome) => ({
      name: outcome.name,
      price: outcome.price,
      imageUrl: outcome.image_url ?? null,
    })),
  };
}

function isUnread(item: SignalFeedItem, lastTs: string | null): boolean {
  if (!lastTs) {
    return true;
  }
  return new Date(item.created_at).getTime() > new Date(lastTs).getTime();
}

async function fetchSignalFeed(): Promise<SignalFeedItem[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return [];
  }
  const response = await fetch(apiUrl("/api/v1/signals/feed", base), {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Signal feed HTTP ${response.status}`);
  }
  const payload = (await response.json()) as SignalFeedResponse;
  return payload.signals ?? [];
}

export function useSignalAlerts() {
  const [alerts, setAlerts] = useState<SignalAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const mountedRef = useRef(true);
  const seededRef = useRef(false);

  const applyFeed = useCallback((signals: SignalFeedItem[]) => {
    const lastTs = readLastSignalTs();

    if (!lastTs && !seededRef.current && signals.length > 0) {
      const latest = signals.reduce((max, item) =>
        !max || new Date(item.created_at).getTime() > new Date(max).getTime()
          ? item.created_at
          : max,
      signals[0].created_at);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LAST_SIGNAL_TS_KEY, latest);
      }
      seededRef.current = true;
      setAlerts([]);
      setUnreadCount(0);
      return;
    }

    seededRef.current = true;
    const unreadItems = signals
      .filter((item) => isUnread(item, lastTs))
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );

    // Cap toast spam: if dozens of signals arrived while offline / before the
    // watermark advanced, only toast the newest few. Advance the watermark to
    // the newest signal so a remount or next poll does not re-flood the UI.
    const toastItems = unreadItems.slice(0, MAX_TOAST_ALERTS);
    if (unreadItems.length > 0 && typeof window !== "undefined") {
      const newest = unreadItems[0];
      if (newest) {
        window.localStorage.setItem(LAST_SIGNAL_TS_KEY, newest.created_at);
      }
    }

    setAlerts(toastItems.map(toAlert));
    setUnreadCount(toastItems.length);
  }, []);

  const markRead = useCallback(() => {
    const latestTs =
      alerts.reduce<string | null>((max, alert) => {
        if (!max || new Date(alert.createdAt).getTime() > new Date(max).getTime()) {
          return alert.createdAt;
        }
        return max;
      }, null) ?? new Date().toISOString();

    if (typeof window !== "undefined") {
      window.localStorage.setItem(LAST_SIGNAL_TS_KEY, latestTs);
    }
    setAlerts([]);
    setUnreadCount(0);
  }, [alerts]);

  useEffect(() => {
    mountedRef.current = true;

    async function poll() {
      try {
        const signals = await fetchSignalFeed();
        if (mountedRef.current) {
          applyFeed(signals);
        }
      } catch {
        // Keep last known unread state when the feed is unavailable.
      }
    }

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      window.clearInterval(intervalId);
    };
  }, [applyFeed]);

  return { alerts, unreadCount, markRead };
}
