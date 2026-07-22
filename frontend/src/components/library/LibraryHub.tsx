"use client";

/**
 * Loop V85 (L3) — /library hub. Unified cards across skills + scanners, with
 * tabs All | Skills | Scanners | Subscribed. Each card exposes Run (skill) /
 * View (scanner) + Subscribe toggle + Fork (toast confirmation, branded).
 *
 * Data: listSkills + listScanners + listSubscriptions (all live-first, mock
 * fallback). Fork delegates to community-api (forkSkill/forkScanner) and
 * refreshes the relevant catalog + subscriptions. Paper trading only.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { LibraryCard, type LibraryEntry, type LibraryEntryKind } from "@/components/library/LibraryCard";
import { useToast } from "@/components/ToastProvider";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  addSubscription,
  forkScanner,
  forkSkill,
  isSubscribed,
  listSubscriptions,
  removeSubscription,
  type Subscription,
} from "@/lib/community-api";
import {
  scheduleLabel,
  listScanners,
  type Scanner,
} from "@/lib/scanners-api";
import { listSkills, runSkill, type Skill } from "@/lib/skills-api";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";

type Tab = "all" | "skills" | "scanners" | "subscribed";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "skills", label: "Skills" },
  { id: "scanners", label: "Scanners" },
  { id: "subscribed", label: "Subscribed" },
];

const SKELETON_COUNT = 6;

function skillToEntry(s: Skill): LibraryEntry {
  return {
    kind: "skill",
    id: s.id,
    name: s.name,
    description: s.description,
    icon: s.icon,
    meta: `${s.run_count} ${s.run_count === 1 ? "run" : "runs"}`,
    private: !s.is_public,
    href: "/skills",
  };
}

function scannerToEntry(s: Scanner): LibraryEntry {
  return {
    kind: "scanner",
    id: s.id,
    name: s.name,
    description: s.description ?? "Compiled from a plain-English request.",
    icon: "📡",
    meta: `${scheduleLabel(s.spec)} · ${s.status}`,
    private: !s.is_public,
    href: `/scanners/${s.id}`,
  };
}

export function LibraryHub() {
  const router = useRouter();
  const { token, isReady } = useAuth();
  const { toast } = useToast();

  const [skills, setSkills] = useState<Skill[]>([]);
  const [scanners, setScanners] = useState<Scanner[]>([]);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [forkId, setForkId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [sk, scn, sub] = await Promise.all([
        listSkills(isReady ? token : null),
        listScanners(isReady ? token : null),
        listSubscriptions(isReady ? token : null),
      ]);
      setSkills(sk.skills);
      setScanners(scn.scanners);
      setSubs(sub.subscriptions);
    } finally {
      setLoading(false);
    }
  }, [isReady, token]);

  useEffect(() => {
    if (!isReady) return;
    void refresh();
  }, [isReady, refresh]);

  const skillEntries = useMemo(() => skills.map(skillToEntry), [skills]);
  const scannerEntries = useMemo(() => scanners.map(scannerToEntry), [scanners]);

  // Subscribed tab: resolve each subscription to a catalog entry when possible.
  const subscribedEntries = useMemo<LibraryEntry[]>(() => {
    return subs.map((sub) => {
      if (sub.ref_type === "scanner") {
        const found = scanners.find((s) => s.id === sub.ref_id);
        return found
          ? scannerToEntry(found)
          : {
              kind: "scanner",
              id: sub.ref_id,
              name: sub.name,
              description: "Subscribed scanner — not in the current catalog.",
              icon: "📡",
              meta: "subscribed",
              href: `/scanners/${sub.ref_id}`,
            };
      }
      const found = skills.find((s) => s.id === sub.ref_id);
      return found
        ? skillToEntry(found)
        : {
            kind: "skill",
            id: sub.ref_id,
            name: sub.name,
            description: "Subscribed skill — not in the current catalog.",
            icon: "✦",
            meta: "subscribed",
            href: "/skills",
          };
    });
  }, [subs, scanners, skills]);

  const entriesForTab = useMemo<LibraryEntry[]>(() => {
    switch (tab) {
      case "skills":
        return skillEntries;
      case "scanners":
        return scannerEntries;
      case "subscribed":
        return subscribedEntries;
      case "all":
      default:
        return [...skillEntries, ...scannerEntries];
    }
  }, [tab, skillEntries, scannerEntries, subscribedEntries]);

  const onToggleSubscribe = useCallback(
    async (entry: LibraryEntry) => {
      const kind = entry.kind as LibraryEntryKind;
      const wasSubscribed = isSubscribed(subs, kind, entry.id);
      setBusyId(entry.id);
      try {
        if (wasSubscribed) {
          const { subscriptions } = await removeSubscription(
            kind,
            entry.id,
            isReady ? token : null,
          );
          setSubs(subscriptions);
          toast({
            title: "Unsubscribed",
            body: `${entry.name} removed from your library.`,
            tone: "info",
          });
        } else {
          const { subscriptions } = await addSubscription(
            kind,
            entry.id,
            isReady ? token : null,
          );
          setSubs(subscriptions);
          toast({
            title: "Subscribed",
            body: `${entry.name} added to your library.`,
            tone: "success",
          });
        }
      } finally {
        setBusyId(null);
      }
    },
    [isReady, subs, token, toast],
  );

  const onFork = useCallback(
    async (entry: LibraryEntry) => {
      setForkId(entry.id);
      const tok = isReady ? token : null;
      try {
        if (entry.kind === "skill") {
          const result = await forkSkill(entry.id, tok);
          if (!result.ok) {
            toast({
              title: "Could not fork",
              body:
                result.reason === "not_found"
                  ? `${entry.name} is no longer available to fork.`
                  : "The community service is offline — try again.",
              tone: "error",
            });
            return;
          }
          toast({
            title: "Forked",
            body: `“${result.skill.name}” copied into your library.`,
            tone: "success",
          });
        } else {
          const result = await forkScanner(entry.id, tok);
          if (!result.ok) {
            toast({
              title: "Could not fork",
              body:
                result.reason === "not_found"
                  ? `${entry.name} is no longer available to fork.`
                  : "The community service is offline — try again.",
              tone: "error",
            });
            return;
          }
          toast({
            title: "Forked",
            body: `“${result.scanner.name}” copied into your library.`,
            tone: "success",
          });
        }
        // A fork creates a private copy — refresh so it appears in the catalog.
        void refresh();
      } finally {
        setForkId(null);
      }
    },
    [isReady, token, toast, refresh],
  );

  const onRun = useCallback(
    async (entry: LibraryEntry) => {
      setBusyId(entry.id);
      try {
        const { session_id } = await runSkill(entry.id, isReady ? token : null);
        router.push(`/terminal?session=${encodeURIComponent(session_id)}`);
      } catch {
        toast({
          title: "Could not start skill",
          body: `${entry.name} did not start — try again.`,
          tone: "error",
        });
      } finally {
        setBusyId(null);
      }
    },
    [isReady, router, toast, token],
  );

  return (
    <div data-testid="library-hub">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-text sm:text-3xl">
            Library
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Skills, scanners, and what you follow — one hub. Fork a copy, subscribe
            for updates, or run a recipe now. {PAPER_TRADING_DISCLAIMER}
          </p>
        </div>
      </div>

      {/* Tab bar */}
      <div
        role="tablist"
        aria-label="Library sections"
        className="flex flex-wrap gap-1 border-b border-border"
      >
        {TABS.map((t) => {
          const count =
            t.id === "skills"
              ? skillEntries.length
              : t.id === "scanners"
                ? scannerEntries.length
                : t.id === "subscribed"
                  ? subscribedEntries.length
                  : skillEntries.length + scannerEntries.length;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={active}
              data-testid={`library-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "relative -mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] font-bold transition",
                active
                  ? "border-primary text-text"
                  : "border-transparent text-muted hover:text-text",
              )}
            >
              {t.label}
              <span
                className={cn(
                  "rounded-pill px-1.5 font-mono text-[10px] font-bold",
                  active ? "bg-primary-dim/55 text-primary" : "bg-bg/60 text-muted-2",
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-5">
        {loading ? (
          <SkeletonGrid />
        ) : entriesForTab.length === 0 ? (
          <EmptyState tab={tab} />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {entriesForTab.map((entry, i) => (
              <LibraryCard
                key={`${entry.kind}-${entry.id}`}
                entry={entry}
                index={i}
                subscribed={isSubscribed(subs, entry.kind as LibraryEntryKind, entry.id)}
                busy={busyId === entry.id}
                forkBusy={forkId === entry.id}
                onToggleSubscribe={onToggleSubscribe}
                onFork={onFork}
                onRun={onRun}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
      {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
        <li
          key={i}
          data-testid="library-skeleton"
          className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4"
        >
          <div className="t-skeleton h-10 w-10 rounded-xl" />
          <div className="t-skeleton h-4 w-2/3 rounded" />
          <div className="t-skeleton h-3 w-full rounded" />
          <div className="t-skeleton h-3 w-1/2 rounded" />
          <div className="t-skeleton mt-2 h-8 w-40 self-start rounded-lg" />
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ tab }: { tab: Tab }) {
  const copy =
    tab === "subscribed"
      ? "You haven't subscribed to any skills or scanners yet. Use the Subscribe toggle on a card to follow it here."
      : tab === "skills"
        ? "No skills published yet. Complete a research session and save it as a skill."
        : tab === "scanners"
          ? "No scanners yet. Compile one from the Scanner Studio."
          : "Nothing here yet — fork a skill or scanner to start your library.";
  return (
    <div
      data-testid="library-empty"
      className="flex min-h-[36dvh] flex-col items-center justify-center rounded-2xl border border-dashed border-border px-6 py-12 text-center"
    >
      <span aria-hidden className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-dim/55 text-2xl">
        📚
      </span>
      <h2 className="mt-4 text-lg font-bold text-text">Nothing here yet</h2>
      <p className="mt-1 max-w-sm text-sm text-muted">{copy}</p>
    </div>
  );
}
