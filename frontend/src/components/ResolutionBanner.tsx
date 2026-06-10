"use client";

import { cn } from "@/lib/cn";

type ResolutionBannerProps = {
  outcome: string | null;
  resolvedAt?: string | null;
};

export function ResolutionBanner({ outcome, resolvedAt }: ResolutionBannerProps) {
  if (!outcome) {
    return null;
  }

  const normalized = outcome.toUpperCase();
  const label =
    normalized === "VOID"
      ? "Market voided — positions refunded at entry"
      : `Market resolved — ${normalized} wins`;

  return (
    <div
      className={cn(
        "mb-5 rounded-2xl border px-4 py-3 text-center text-sm font-bold",
        normalized === "YES"
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
          : normalized === "NO"
            ? "border-red-500/40 bg-red-500/10 text-red-200"
            : "border-amber-500/40 bg-amber-500/10 text-amber-200",
      )}
    >
      <p>{label}</p>
      {resolvedAt ? (
        <p className="mt-1 text-xs font-medium opacity-80">
          Resolved {new Date(resolvedAt).toLocaleString()}
        </p>
      ) : null}
    </div>
  );
}
