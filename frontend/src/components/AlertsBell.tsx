"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAlertsFeed, unreadAlertCount, type AlertEventItem } from "@/lib/alerts-api";
import {
  buildNotifyPrefsView,
  fetchNotifyPrefs,
  filterItemsByPrefs,
} from "@/lib/notify-prefs-api";
import { ACCESS_TOKEN_KEY } from "@/lib/portfolio-api";

export const ALERTS_LAST_SEEN_KEY = "alphaedge.alertsLastSeenTs";
export const ALERTS_SEEN_EVENT = "alphaedge:alerts-seen";

function readLastSeen(): number {
  if (typeof window === "undefined") return 0;
  const raw = localStorage.getItem(ALERTS_LAST_SEEN_KEY);
  const n = raw ? Number.parseInt(raw, 10) : 0;
  return Number.isFinite(n) ? n : 0;
}

/**
 * W02 — header bell for the signal-alerts feed (J02). Fetches once on mount (no
 * poll loop), shows an unread-ish badge vs the localStorage "last seen" ts, and
 * links to /alerts. Notify only — never places orders.
 */
export function AlertsBell() {
  const [items, setItems] = useState<AlertEventItem[]>([]);
  const [lastSeen, setLastSeen] = useState(0);
  // Y03 — enabled families from stored notify prefs (null = no constraint / anon
  // → the bell counts every family, matching the /alerts feed behaviour).
  const [enabledFamilies, setEnabledFamilies] = useState<string[] | null>(null);

  useEffect(() => {
    setLastSeen(readLastSeen());
    let dead = false;
    void fetchAlertsFeed({ limit: 50 }).then((data) => {
      if (!dead) setItems(data);
    });
    // When signed in, respect the user's notify prefs so the badge and the
    // /alerts feed count the same families. Defensive: any failure = no filter.
    const token = typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
    if (token) {
      void fetchNotifyPrefs(token).then((raw) => {
        if (dead) return;
        const view = buildNotifyPrefsView(raw, true);
        setEnabledFamilies(view.reachable ? view.enabled : null);
      });
    }
    const onSeen = () => setLastSeen(readLastSeen());
    window.addEventListener(ALERTS_SEEN_EVENT, onSeen);
    return () => {
      dead = true;
      window.removeEventListener(ALERTS_SEEN_EVENT, onSeen);
    };
  }, []);

  const unread = unreadAlertCount(filterItemsByPrefs(items, enabledFamilies), lastSeen);
  // Visible badge text must appear in the accessible name (Lighthouse label-content-name-mismatch).
  const badgeLabel = unread > 9 ? "9+" : unread > 0 ? String(unread) : "";
  const ariaLabel =
    unread > 0
      ? `Signal alerts ${badgeLabel}, ${unread} unread`
      : "Signal alerts";

  return (
    <Link
      href="/alerts"
      aria-label={ariaLabel}
      className="relative grid h-9 w-9 place-items-center rounded-lg border border-border text-muted transition hover:border-border-light hover:text-text"
    >
      <BellIcon />
      {unread > 0 && (
        <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-primary px-0.5 font-mono text-[10px] font-black text-bg">
          {badgeLabel}
        </span>
      )}
    </Link>
  );
}

function BellIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
