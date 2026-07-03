import { cn } from "@/lib/cn";
import type { BriefClaim } from "@/lib/polyscout-api";

const STATUS_STYLE: Record<string, string> = {
  correct: "text-up border-up/40 bg-primary-dim",
  incorrect: "text-down border-down/40 bg-danger-dim",
  void: "text-muted border-border bg-surface-2",
  pending: "text-accent border-accent/40 bg-accent-dim",
};

export function claimLabel(claim: BriefClaim): string {
  const dir = claim.direction.replace(/_/g, " ");
  const h = claim.horizon_minutes >= 60
    ? `${Math.round(claim.horizon_minutes / 60)}h`
    : `${claim.horizon_minutes}m`;
  return `${dir} · ${h}`;
}

export function ClaimBadge({ claim, showStatus = true }: { claim: BriefClaim; showStatus?: boolean }) {
  const style = STATUS_STYLE[claim.status] ?? STATUS_STYLE.pending;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-0.5 font-mono text-[11px] font-semibold",
        style,
      )}
      title={`Claim: ${claim.direction} within ${claim.horizon_minutes} minutes — ${claim.status}`}
    >
      {claimLabel(claim)}
      {showStatus && <span className="uppercase tracking-wide">{claim.status}</span>}
    </span>
  );
}
