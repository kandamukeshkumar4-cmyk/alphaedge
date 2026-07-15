/**
 * Canvas-safe color resolution for chart libraries (lightweight-charts).
 *
 * Canvas 2D color strings cannot contain CSS `var()` references — passing
 * "rgb(var(--color-primary))" to a canvas gradient/fill throws or silently
 * fails. These helpers resolve the computed value off <html> at runtime and
 * fall back to the concrete design-token value when the variable is missing
 * (or when running server-side).
 *
 * Chart chrome tokens (`--chart-text` / `--chart-grid` / `--chart-border`)
 * flip under `html.light` (see globals.css) so LWC re-themes with the rest
 * of the app when the theme class toggles.
 */

/** Concrete token fallbacks (see src/app/globals.css palette comment). */
export const CHART_COLOR_FALLBACKS = {
  primary: "0, 232, 176", // #00E8B0 mint
  danger: "255, 90, 95", // #FF5A5F
  secondary: "75, 158, 255", // #4B9EFF
  /** Dark-theme chrome (muted / border) — used when CSS vars are absent. */
  text: "143, 168, 160",
  grid: "28, 44, 40",
  border: "28, 44, 40",
} as const;

export type LwcChartTheme = {
  text: string;
  grid: string;
  border: string;
  accent: string;
  accentSoft: string;
  accentFade: string;
  up: string;
  down: string;
  volUp: string;
  volDown: string;
  model: string;
};

/**
 * Read a CSS custom property expected to hold an "R, G, B"-style triplet
 * (or any concrete color channels). Returns `fallback` when the variable is
 * undefined, empty, still contains `var(`, or when there is no DOM.
 */
export function cssColorTriplet(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (!raw || raw.includes("var(")) return fallback;
  const hex = hexToTriplet(raw);
  if (hex) return hex;
  if (!/^[\d\s,%.]+$/.test(raw)) return fallback;
  return raw.split(/[\s,]+/).filter(Boolean).join(", ");
}

/** Convert #rgb / #rrggbb to an "R, G, B" triplet; null when not hex. */
export function hexToTriplet(value: string): string | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (!m) return null;
  let hex = m[1]!;
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const n = parseInt(hex, 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

/** Build a canvas-safe `rgb()` string from a variable + concrete fallback. */
export function chartRgb(name: string, fallback: string): string {
  return `rgb(${cssColorTriplet(name, fallback)})`;
}

/** Build a canvas-safe `rgba()` string from a variable + concrete fallback. */
export function chartRgba(
  name: string,
  fallback: string,
  alpha: number,
): string {
  return `rgba(${cssColorTriplet(name, fallback)}, ${alpha})`;
}

/** Resolve the full lightweight-charts theme from live CSS tokens. */
export function readLwcChartTheme(): LwcChartTheme {
  const text = cssColorTriplet("--chart-text", CHART_COLOR_FALLBACKS.text);
  const grid = cssColorTriplet("--chart-grid", CHART_COLOR_FALLBACKS.grid);
  const border = cssColorTriplet("--chart-border", CHART_COLOR_FALLBACKS.border);
  const primary = cssColorTriplet(
    "--color-primary",
    CHART_COLOR_FALLBACKS.primary,
  );
  const danger = cssColorTriplet("--color-danger", CHART_COLOR_FALLBACKS.danger);
  const secondary = cssColorTriplet(
    "--color-secondary",
    CHART_COLOR_FALLBACKS.secondary,
  );
  return {
    text: `rgb(${text})`,
    grid: `rgba(${grid}, 0.55)`,
    border: `rgb(${border})`,
    accent: `rgb(${primary})`,
    accentSoft: `rgba(${primary}, 0.28)`,
    accentFade: `rgba(${primary}, 0.0)`,
    up: `rgb(${primary})`,
    down: `rgb(${danger})`,
    volUp: `rgba(${primary}, 0.45)`,
    volDown: `rgba(${danger}, 0.45)`,
    model: `rgb(${secondary})`,
  };
}

/** Observe `html` class changes (`.light` toggle) and invoke `onTheme`. */
export function observeChartTheme(
  onTheme: () => void,
): MutationObserver | null {
  if (typeof MutationObserver === "undefined" || typeof document === "undefined") {
    return null;
  }
  const observer = new MutationObserver(onTheme);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return observer;
}
