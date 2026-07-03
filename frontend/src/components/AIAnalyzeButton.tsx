"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { AITakePanel } from "./AITakePanel";

type Props = {
  slug: string;
  title?: string;
  /** Compact variant for use inside cards; full-width for panels. */
  variant?: "card" | "panel";
  className?: string;
};

/**
 * On-demand "AI Analyze" trigger. Opens the existing AITakePanel (model vs
 * market, edge, confidence, news signals) in a modal so it works from any
 * surface — including the market listing cards, which otherwise show no AI take.
 */
export function AIAnalyzeButton({ slug, title, variant = "card", className }: Props) {
  const [open, setOpen] = useState(false);

  const openModal = useCallback((e: React.MouseEvent) => {
    // Cards wrap the whole tile in a <Link>; don't navigate when analyzing.
    e.preventDefault();
    e.stopPropagation();
    setOpen(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={openModal}
        aria-label="AI analyze this market"
        className={cn(
          "inline-flex items-center justify-center gap-1.5 rounded-lg border border-accent/40 bg-accent/10 font-bold text-accent transition hover:bg-accent/20",
          variant === "card" ? "px-2.5 py-1 text-[11px]" : "w-full px-4 py-2.5 text-sm",
          className,
        )}
      >
        <span aria-hidden className="text-[13px] leading-none">✦</span>
        AI Analyze
      </button>

      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title ? `AI analysis for ${title}` : "AI analysis"}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 backdrop-blur-sm sm:items-center"
          onClick={(e) => {
            e.stopPropagation();
            setOpen(false);
          }}
        >
          <div
            className="w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="line-clamp-1 text-sm font-bold text-text">
                {title ?? "AI analysis"}
              </p>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="rounded-lg border border-border bg-surface px-2 py-1 text-xs text-muted transition hover:text-text"
              >
                Close
              </button>
            </div>
            <AITakePanel slug={slug} />
          </div>
        </div>
      ) : null}
    </>
  );
}
