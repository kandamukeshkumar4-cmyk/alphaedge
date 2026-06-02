import { cn } from "@/lib/cn";

// ▲/▼ delta chip used in ranked rails and price headers.
export function Delta({
  value,
  suffix = "",
  className,
}: {
  value: number;
  suffix?: string;
  className?: string;
}) {
  if (value === 0) return null;
  const up = value > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-mono text-xs font-semibold tabular",
        up ? "text-primary" : "text-danger",
        className,
      )}
    >
      <span aria-hidden>{up ? "▲" : "▼"}</span>
      {Math.abs(value)}
      {suffix}
    </span>
  );
}
