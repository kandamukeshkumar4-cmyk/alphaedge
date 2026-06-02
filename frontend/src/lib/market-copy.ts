export function marketCountLabel(count: number): string {
  return `${count} ${count === 1 ? "market" : "markets"}`;
}
