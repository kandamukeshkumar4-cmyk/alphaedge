"use client";

/**
 * PersonalContextChip — U13 personal context chip for DecisionCard.
 *
 * Shown on the U03 DecisionCard when a proposed bet deviates from the
 * user's historical pattern (e.g. "This bet is 3x your usual size").
 *
 * The deviation message is computed server-side from deterministic math
 * (detect_size_deviation in trader_profile_service.py). This component
 * only renders the message — it never computes or fabricates stats.
 *
 * Renders nothing when:
 *  - deviationMessage is null / undefined (no deviation, or no profile data)
 *  - The user is new (has_data=False on the profile) — honest absence
 *
 * GUARDRAIL: Read-only display only. No order surfaces.
 */

import { cn } from "@/lib/cn";

type Props = {
  /** Pre-computed deviation message from the backend, or null if no deviation. */
  deviationMessage: string | null | undefined;
  className?: string;
};

export function PersonalContextChip({ deviationMessage, className }: Props) {
  if (!deviationMessage) return null;

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-xs",
        className,
      )}
      role="note"
      aria-label="Personal context: position size deviation"
    >
      <span className="mt-0.5 text-orange-400" aria-hidden="true">
        ⚠
      </span>
      <span className="font-medium text-orange-300">{deviationMessage}</span>
    </div>
  );
}
