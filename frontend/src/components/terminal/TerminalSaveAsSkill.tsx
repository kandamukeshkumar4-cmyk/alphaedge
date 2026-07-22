"use client";

/**
 * Loop V83 (S3) — "Save as skill" on a completed terminal session. A mint
 * outline button opens a mini-form (name + description); on submit it POSTs
 * to the save-as-skill endpoint and shows a branded mint confirmation toast
 * (never danger-red). Paper only — saving a skill only records the recipe.
 */

import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/ToastProvider";
import { cn } from "@/lib/cn";
import { saveSessionAsSkill } from "@/lib/skills-api";

export function TerminalSaveAsSkill({ sessionId }: { sessionId: string }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function save() {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      const result = await saveSessionAsSkill(sessionId, {
        name: trimmed,
        description: description.trim() || undefined,
      });
      if (result.ok) {
        toast({
          title: "Skill saved",
          body: `“${trimmed}” is in your skills gallery.`,
          tone: "success",
        });
        setOpen(false);
        setName("");
        setDescription("");
      } else {
        toast({
          title: "Could not save skill",
          body: "The session did not save — try again.",
          tone: "error",
        });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        data-testid="terminal-save-as-skill"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary-dim/40 px-2.5 py-1.5 text-[11px] font-bold text-primary transition",
          "hover:border-primary/60 hover:bg-primary-dim/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 active:scale-95",
        )}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path
            d="M2.5 7.5 5 10l4.5-6.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Save as skill
      </button>
      {open ? (
        <div
          role="dialog"
          aria-label="Save session as a skill"
          className="absolute right-0 top-full z-30 mt-2 w-72 rounded-xl border border-border bg-surface p-3 shadow-lift"
        >
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-muted-2">
              Name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lakers pre-game scan"
              autoFocus
              maxLength={80}
              aria-label="Skill name"
              className="mt-1 w-full rounded-lg border border-border bg-bg/55 px-2.5 py-1.5 text-[12px] text-text outline-none transition placeholder:text-muted-2 hover:border-border-light focus:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/30"
            />
          </label>
          <label className="mt-2 block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-muted-2">
              Description
            </span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="One line — what this skill does."
              rows={2}
              maxLength={160}
              aria-label="Skill description"
              className="mt-1 w-full resize-none rounded-lg border border-border bg-bg/55 px-2.5 py-1.5 text-[12px] text-text outline-none transition placeholder:text-muted-2 hover:border-border-light focus:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/30"
            />
          </label>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold text-muted transition hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 active:scale-95"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="terminal-save-as-skill-submit"
              onClick={() => void save()}
              disabled={!name.trim() || saving}
              className={cn(
                "rounded-md bg-primary px-3 py-1 text-[11px] font-bold text-bg shadow-glow transition",
                "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95",
                !name.trim() || saving ? "cursor-not-allowed opacity-50" : "",
              )}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
