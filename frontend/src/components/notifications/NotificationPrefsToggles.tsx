"use client";

import { useEffect, useState } from "react";

import { useToast } from "@/components/ToastProvider";
import { cn } from "@/lib/cn";
import {
  getPrefs,
  putPrefs,
  type NotificationPrefsV90,
} from "@/lib/notifications-api";

/*
 * Loop V90 (C2) — in-dropdown notification preferences
 * (GET|PUT /api/v1/notifications/preferences -> {email_digest, in_app,
 * fired_alerts}). PUT on change with a toast confirm; mint/neutral styling
 * only — no danger-red. Preferences are a STORED setting in this paper
 * simulation: nothing is ever emailed or delivered externally.
 */

const PREF_ROWS: {
  key: keyof NotificationPrefsV90;
  label: string;
  blurb: string;
}[] = [
  {
    key: "in_app",
    label: "In-app notifications",
    blurb: "Show alerts in this notification center.",
  },
  {
    key: "fired_alerts",
    label: "Fired alerts",
    blurb: "Surface fired signal alerts here as they trigger.",
  },
  {
    key: "email_digest",
    label: "Email digest",
    blurb: "Stored in-app only — no email is ever sent (paper sim).",
  },
];

/**
 * Uses the ambient ToastProvider (mounted in src/app/layout.tsx); useToast()
 * degrades to a no-op when rendered outside one.
 */
export function NotificationPrefsToggles({
  token,
  disabled = false,
}: {
  token: string | null;
  disabled?: boolean;
}) {
  const { toast } = useToast();
  const [prefs, setPrefs] = useState<NotificationPrefsV90 | null>(null);
  const [savingKey, setSavingKey] = useState<keyof NotificationPrefsV90 | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getPrefs(token).then((result) => {
      if (!cancelled) setPrefs(result.prefs);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleToggle(key: keyof NotificationPrefsV90) {
    if (!prefs || savingKey) return;
    const previous = prefs;
    const next: NotificationPrefsV90 = { ...prefs, [key]: !prefs[key] };
    // Optimistic flip; revert on an explicit failure (client never rejects).
    setPrefs(next);
    setSavingKey(key);
    const result = await putPrefs(next, token);
    setSavingKey(null);
    if (result.ok) {
      setPrefs(result.prefs);
      toast({ title: "Preferences saved", tone: "success" });
    } else {
      setPrefs(previous);
      toast({ title: "Preferences not saved — API unavailable", tone: "info" });
    }
  }

  return (
    <div>
      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
        Preferences
      </p>
      {prefs === null ? (
        <div aria-hidden="true" className="mt-2 space-y-2">
          {[0, 1, 2].map((row) => (
            <span
              key={row}
              className="block h-4 animate-pulse rounded bg-surface-3 motion-reduce:animate-none"
            />
          ))}
        </div>
      ) : (
        <ul className="mt-1 space-y-0.5">
          {PREF_ROWS.map((row) => {
            const enabled = prefs[row.key];
            const rowLabel = `${row.label}${enabled ? " (on)" : " (off)"}`;
            return (
              <li key={row.key} className="flex items-center justify-between gap-3 py-1.5">
                <span className="min-w-0">
                  <span className="block text-[13px] font-semibold text-text">{row.label}</span>
                  <span className="block text-[11px] leading-4 text-muted-2">{row.blurb}</span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  aria-label={rowLabel}
                  disabled={disabled || savingKey !== null}
                  onClick={() => void handleToggle(row.key)}
                  className={cn(
                    "relative h-5 w-9 shrink-0 rounded-pill border transition-colors disabled:opacity-50",
                    enabled ? "border-primary/60 bg-primary/25" : "border-border-light bg-surface-3",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full transition-all",
                      enabled ? "left-[18px] bg-primary" : "left-[3px] bg-muted-2",
                    )}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
