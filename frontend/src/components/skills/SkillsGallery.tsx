"use client";

/**
 * Loop V83 (S2) — Skills gallery grid. Fetches skills via `@/lib/skills-api`
 * (live-first, mock fallback). Skeleton shimmer while loading, empty state
 * when the catalog is empty, 40ms staggered card entrance. Run → POST run →
 * router.push /terminal?session={id}. Paper trading only.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { SkillCard } from "@/components/skills/SkillCard";
import { useToast } from "@/components/ToastProvider";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";
import { listSkills, runSkill, type Skill } from "@/lib/skills-api";

const SKELETON_COUNT = 6;

export function SkillsGallery() {
  const router = useRouter();
  const { token, isReady } = useAuth();
  const { toast } = useToast();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"live" | "mock">("mock");
  const [runningId, setRunningId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { skills: items, source: src } = await listSkills(isReady ? token : null);
      setSkills(items);
      setSource(src);
    } finally {
      setLoading(false);
    }
  }, [isReady, token]);

  useEffect(() => {
    if (!isReady) return;
    void refresh();
  }, [isReady, refresh]);

  const onRun = useCallback(
    async (skill: Skill) => {
      setRunningId(skill.id);
      try {
        const { session_id, source: src } = await runSkill(skill.id, isReady ? token : null);
        setSource(src);
        router.push(`/terminal?session=${encodeURIComponent(session_id)}`);
      } catch {
        toast({
          title: "Could not start skill",
          body: `${skill.name} did not start — try again.`,
          tone: "error",
        });
      } finally {
        setRunningId(null);
      }
    },
    [isReady, router, toast, token],
  );

  return (
    <div data-testid="skills-gallery">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-text sm:text-3xl">
            Skills
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            One-tap research recipes — each runs a full terminal session on the
            canonical paper market. {PAPER_TRADING_DISCLAIMER}
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
          {source === "live" ? "live catalog" : "local mock"}
        </span>
      </div>

      {loading ? (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <li
              key={i}
              data-testid="skills-skeleton"
              className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4"
            >
              <div className="t-skeleton h-10 w-10 rounded-xl" />
              <div className="t-skeleton h-4 w-2/3 rounded" />
              <div className="t-skeleton h-3 w-full rounded" />
              <div className="t-skeleton h-3 w-1/2 rounded" />
              <div className="t-skeleton mt-2 h-8 w-24 self-end rounded-lg" />
            </li>
          ))}
        </ul>
      ) : skills.length === 0 ? (
        <div
          data-testid="skills-empty"
          className="flex min-h-[40dvh] flex-col items-center justify-center rounded-2xl border border-dashed border-border px-6 py-12 text-center"
        >
          <span
            aria-hidden="true"
            className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-dim/55 text-2xl"
          >
            ✦
          </span>
          <h2 className="mt-4 text-lg font-bold text-text">No skills yet</h2>
          <p className="mt-1 max-w-sm text-sm text-muted">
            Complete a research session and save it as a skill, or check back
            when the catalog publishes recipes.
          </p>
        </div>
      ) : (
        <ul className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3")}>
          {skills.map((skill, i) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              index={i}
              onRun={onRun}
              busy={runningId === skill.id}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
