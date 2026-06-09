"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import type { SignalFeedItem } from "@/lib/signals-dashboard-api";

const LAST_SIGNAL_TS_KEY = "alphaedge.lastSignalTs";
const POLL_INTERVAL_MS = 30_000;

export type SignalAlert = {
  id: string;
  signalType: string;
  marketTitle: string;
  confidencePct: number | null;
  createdAt: string;
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
    marketTitle: item.market_name,
    confidencePct:
      item.implied_edge === null ? null : Math.round(item.implied_edge * 100),
    createdAt: item.created_at,
  };
}

function isUnread(item: SignalFeedItem, lastTs: string | null): boolean {
  if (!lastTs) {
    return true;
  }
  return new Date(item.created_at).getTime() > new Date(lastTs).getTime();
}

async function fetchSignalFeed(): Promise<SignalFeedItem[]> {
  if (!API_BASE) {
    return [];
  }
  const response = await fetch(`${API_BASE}/api/v1/signals/feed`, {
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
    const unread = signals.filter((item) => isUnread(item, lastTs)).map(toAlert);
    setAlerts(unread);
    setUnreadCount(unread.length);
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
