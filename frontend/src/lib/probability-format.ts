export function formatProbabilityAxis(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }

  return `${Math.round(value * 100)}%`;
}
