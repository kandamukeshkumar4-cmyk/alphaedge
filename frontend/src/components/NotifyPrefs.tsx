"use client";

// Y03 — Notification preferences panel (backend L03, GET/PUT /api/v1/notify/prefs).
// Authed toggles for which alert families surface, with an optimistic PUT (the
// ONLY mutation in this loop — a stored preference, never an order). Anon shows a
// sign-in prompt. Prefs are STORED + applied in-app only: no external delivery.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { MotionReveal } from "@/components/MotionReveal";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  buildNotifyPrefsView,
  fetchNotifyPrefs,
  putNotifyPrefs,
  toggleFamily,
  type NotifyPrefsView,
} from "@/lib/notify-prefs-api";

function PrefsSkeleton() {
  return (
    <div aria-hidden>
      <div className="skeleton h-3 w-56 rounded" />
      <div className="mt-3 space-y-2">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="skeleton h-8 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

export function NotifyPrefs({
  onEnabledChange,
}: {
  onEnabledChange?: (enabled: string[] | null) => void;
}) {
  const { token, isReady } = useAuth();
  const [view, setView] = useState<NotifyPrefsView | null>(null);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the callback in a ref so the load effect doesn't depend on its identity.
  const onChangeRef = useRef(onEnabledChange);
  useEffect(() => {
    onChangeRef.current = onEnabledChange;
  });

  useEffect(() => {
    if (!isReady) return;
    if (!token) {
      setView(buildNotifyPrefsView(null, false));
      onChangeRef.current?.(null);
      return;
    }
    let dead = false;
    const ctrl = new AbortController();
    setView(null);
    void fetchNotifyPrefs(token, ctrl.signal).then((raw) => {
      if (dead || ctrl.signal.aborted) return;
      const v = buildNotifyPrefsView(raw, true);
      setView(v);
      setEnabled(v.enabled);
      // Only constrain the feed when we actually read stored prefs.
      onChangeRef.current?.(v.reachable ? v.enabled : null);
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [token, isReady]);

  function applyEnabled(next: string[], v: NotifyPrefsView): NotifyPrefsView {
    return {
      ...v,
      toggles: v.toggles.map((t) => ({ ...t, enabled: next.includes(t.key) })),
      enabled: next,
    };
  }

  function onToggle(key: string) {
    if (!view || !view.reachable || saving) return;
    const prev = enabled;
    const next = toggleFamily(prev, key);
    setEnabled(next);
    setView(applyEnabled(next, { ...view, source: "stored" }));
    onChangeRef.current?.(next);
    setError(null);
    setSaving(true);
    void putNotifyPrefs(next, token)
      .then((raw) => {
        if (raw) {
          const v = buildNotifyPrefsView(raw, true);
          setView(v);
          setEnabled(v.enabled);
          onChangeRef.current?.(v.enabled);
        } else {
          // Roll back the optimistic update on failure.
          setEnabled(prev);
          setView((cur) => (cur ? applyEnabled(prev, cur) : cur));
          onChangeRef.current?.(prev);
          setError("Could not save — reverted your change.");
        }
      })
      .finally(() => setSaving(false));
  }

  return (
    <section aria-label="Notification preferences" className="mb-6">
      <MotionReveal className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-black tracking-tight text-text">Notification preferences</h2>
          {view?.reachable ? (
            <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase text-muted-2">
              {view.source}
            </span>
          ) : null}
          {saving ? (
            <span className="font-mono text-[10px] text-muted-2" role="status">
              saving…
            </span>
          ) : null}
        </div>

        {!isReady || (token && view === null) ? (
          <PrefsSkeleton />
        ) : view && !view.authed ? (
          <div className="text-center">
            <p className="text-xs text-muted">
              Sign in to choose which alert families surface here. Preferences are stored to your
              account and applied in-app only — nothing is ever emailed or sent externally.
            </p>
            <Link
              href="/auth/login?next=/alerts"
              className="mt-3 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
            >
              Sign in to customize
            </Link>
          </div>
        ) : view && !view.reachable ? (
          <p className="text-xs text-muted">
            Could not load your preferences right now — the alerts feed is showing every family
            until they load.
          </p>
        ) : view ? (
          <>
            <p className="text-xs text-muted">
              Toggle which alert families surface on this page. Notify/read only — never trades.
            </p>
            <ul className="mt-3 space-y-1.5">
              {view.toggles.map((t) => (
                <li key={t.key}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 transition",
                      t.enabled
                        ? "border-primary/40 bg-primary-dim/40"
                        : "border-border bg-surface-2/40",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={t.enabled}
                      onChange={() => onToggle(t.key)}
                      disabled={saving}
                      aria-label={`Surface ${t.label} alerts`}
                      className="h-4 w-4 shrink-0 accent-primary"
                    />
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-text">
                      {t.label}
                    </span>
                    <span
                      className={cn(
                        "shrink-0 font-mono text-[10px] font-bold uppercase",
                        t.enabled ? "text-primary" : "text-muted-2",
                      )}
                    >
                      {t.enabled ? "on" : "off"}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            {error ? (
              <p className="mt-2 text-[11px] font-semibold text-danger" role="alert">
                {error}
              </p>
            ) : null}
            <p className="mt-3 text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
          </>
        ) : null}
      </MotionReveal>
    </section>
  );
}
