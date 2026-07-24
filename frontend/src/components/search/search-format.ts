/**
 * Loop V91 SU2 — pure display helpers for the command palette.
 * All values are PAPER (simulated) — nothing here implies real funds.
 */

/** 0..1 probability price → integer-percent label; null → "—". */
export function formatYesPct(yesPrice: number | null): string {
  if (yesPrice === null || !Number.isFinite(yesPrice)) return "—";
  return `${Math.round(yesPrice * 100)}%`;
}

/** Compact simulated-volume label: $999 / $48.2K / $1.2M. */
export function formatSearchVolume(volume: number): string {
  if (!Number.isFinite(volume) || volume <= 0) return "$0";
  if (volume >= 1_000_000) return `$${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `$${(volume / 1_000).toFixed(1)}K`;
  return `$${Math.round(volume)}`;
}

/** "45m left" / "6h left" / "12d left"; null when unknown. */
export function formatHoursToClose(hours: number | null): string | null {
  if (hours === null || !Number.isFinite(hours) || hours < 0) return null;
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m left`;
  if (hours < 48) return `${Math.round(hours)}h left`;
  return `${Math.round(hours / 24)}d left`;
}
