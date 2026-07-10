"use client";

// W02 — Alerts feed (backend J02, GET /api/v1/alerts). Recent signal events
// grouped by market with news/catalyst evidence and family filter pills. Uses
// the JWT session (watchlist-scoped) when signed in, the public stream when
// anon. Research only, paper trading only — alerts NOTIFY, they never trade.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { PageHeader, PageShell } from "@/components/ui/kit";
import { ALERTS_LAST_SEEN_KEY, ALERTS_SEEN_EVENT } from "@/components/AlertsBell";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import {
  alertFamilies,
  buildAlertGroups,
  familyLabel,
  fetchAlertsFeed,
  newestAlertTs,
  type AlertEventItem,
} from "@/lib/alerts-api";
import type { SignalCategory } from "@/lib/signals-dashboard-view-model";

export default function AlertsPage() {
  const { token, isReady } = useAuth();
  const [items, setItems] = useState<AlertEventItem[] | null>(null);
  const [filter, setFilter] = useState<SignalCategory | "all">("all");

  useEffect(() => {
    let dead = false;
    void fetchAlertsFeed({ limit: 60 }).then((data) => {
      if (dead) return;
      setItems(data);
      // Mark everything currently visible as seen so the header bell clears.
      const newest = newestAlertTs(data);
      if (newest > 0 && typeof window !== "undefined") {
        localStorage.setItem(ALERTS_LAST_SEEN_KEY, String(newest));
        window.dispatchEvent(new Event(ALERTS_SEEN_EVENT));
      }
    });
    return () => {
      dead = true;
    };
  }, []);

  const families = useMemo(() => (items ? alertFamilies(items) : []), [items]);
  const groups = useMemo(() => (items ? buildAlertGroups(items, filter) : []), [items, filter]);

  const scopeNote =
    isReady && token
      ? "Scoped to your watchlist."
      : "Public signal stream — sign in to scope alerts to your watchlist.";

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Alerts"
        title="Signal alerts"
        subtitle={`Model mispricings, unusual flow, screener and cross-venue signals grouped by market. ${scopeNote} Research only — notify only, never trades.`}
      />

      {items === null ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          title="No alerts yet"
          body="Alerts land here as the pipeline flags model mispricings, unusual flow, and screener hits. Track markets on your watchlist to scope them to what you care about."
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter alerts by family">
            <FilterPill label="All" active={filter === "all"} onClick={() => setFilter("all")} />
            {families.map((fam) => (
              <FilterPill
                key={fam}
                label={familyLabel(fam)}
                active={filter === fam}
                onClick={() => setFilter(fam)}
              />
            ))}
          </div>

          {groups.length === 0 ? (
            <EmptyState title="Nothing in this family" body="No alerts match the selected filter right now." />
          ) : (
            <ul className="space-y-3">
              {groups.map((group) => (
                <li key={group.slug} className="rounded-xl border border-border bg-surface p-4">
                  <div className="flex items-center gap-2">
                    <Link
                      href={marketHref(group.slug)}
                      className="min-w-0 flex-1 truncate font-mono text-sm font-semibold text-text hover:text-accent-bright"
                    >
                      {group.slug}
                    </Link>
                    <span className="shrink-0 rounded bg-surface-3 px-1.5 py-0.5 text-[10px] font-bold text-muted">
                      {group.count} alert{group.count === 1 ? "" : "s"}
                    </span>
                    <span className="shrink-0 text-[10px] text-muted-2">{group.latestLabel}</span>
                  </div>

                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {group.families.map((fam) => (
                      <span
                        key={fam}
                        className="rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-accent-bright"
                      >
                        {familyLabel(fam)}
                      </span>
                    ))}
                  </div>

                  <ul className="mt-3 space-y-3">
                    {group.rows.map((row) => (
                      <li key={row.id} className="border-t border-border/60 pt-3 first:border-0 first:pt-0">
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="font-semibold text-text">{row.typeLabel}</span>
                          <span className="ml-auto text-muted-2">{row.timeLabel}</span>
                        </div>
                        {row.evidence ? <SignalEvidenceBlock evidence={row.evidence} /> : null}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </PageShell>
  );
}

function FilterPill({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-semibold transition",
        active
          ? "border-primary/40 bg-primary-dim text-primary"
          : "border-border text-muted hover:border-border-light hover:text-text",
      )}
    >
      {label}
    </button>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="rounded-xl border border-border bg-surface p-4">
          <div className="skeleton h-4 w-1/2 rounded" />
          <div className="skeleton mt-2 h-3 w-24 rounded" />
          <div className="skeleton mt-3 h-12 w-full rounded" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-8 text-center">
      <p className="text-sm font-semibold text-text">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">{body}</p>
    </div>
  );
}
