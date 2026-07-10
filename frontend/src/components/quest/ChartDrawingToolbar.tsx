"use client";

/** TradingView-style left drawing toolbar stub for Trade terminal chart. */
const TOOLS = [
  { id: "cursor", label: "Cursor", path: "M4 4l8 16 2-6 6-2z" },
  { id: "cross", label: "Crosshair", path: "M11 3v16M3 11h16" },
  { id: "trend", label: "Trend line", path: "M4 18 L18 4" },
  { id: "hline", label: "Horizontal", path: "M3 12h16" },
  { id: "ray", label: "Ray", path: "M4 18 L14 8 M14 8h4" },
  { id: "fib", label: "Fibonacci", path: "M4 6h14M4 12h14M4 18h14" },
  { id: "text", label: "Text", path: "M6 6h10M11 6v12" },
  { id: "brush", label: "Brush", path: "M5 17c4-8 8-10 12-12l2 2c-2 4-4 8-12 12z" },
] as const;

export function ChartDrawingToolbar({
  active = "cursor",
  onSelect,
}: {
  active?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <div
      className="absolute left-2 top-10 z-10 flex flex-col gap-0.5 rounded-lg border border-border bg-surface/95 p-1 shadow-card backdrop-blur"
      role="toolbar"
      aria-label="Chart drawing tools"
    >
      {TOOLS.map((t) => (
        <button
          key={t.id}
          type="button"
          title={t.label}
          aria-label={t.label}
          aria-pressed={active === t.id}
          onClick={() => onSelect?.(t.id)}
          className={
            active === t.id
              ? "grid h-7 w-7 place-items-center rounded-md bg-primary-dim text-primary"
              : "grid h-7 w-7 place-items-center rounded-md text-muted transition hover:bg-surface-2 hover:text-text"
          }
        >
          <svg width="14" height="14" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d={t.path} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      ))}
    </div>
  );
}
