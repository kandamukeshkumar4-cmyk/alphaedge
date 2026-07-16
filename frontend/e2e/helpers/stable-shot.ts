/**
 * Loop V44 — stable-shot harness.
 *
 * Mask / freeze dynamic UI so toHaveScreenshot baselines stay deterministic.
 * Zero frontend/src changes — Playwright-side masking and DOM freezes only.
 *
 * Masking rules (also documented in goals/loop-v44-visreg/STATE.md):
 * 1. Prices — mono ¢ / pts / $ figures that poll or recompute.
 * 2. Sparklines / charts — SVG sparklines + lightweight-charts canvas.
 * 3. Tickers — sticky footer live/recent signal marquee.
 * 4. Relative ages — "12s ago" / "3m ago" text frozen to "• ago".
 * 5. Motion — animations/transitions disabled; caret hidden.
 * 6. Live chrome — health banner + authed portfolio banner numerics.
 */
import type { Locator, Page } from "@playwright/test";

export type ThemeName = "dark" | "light";

export const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;
export const MOBILE_VIEWPORT = { width: 375, height: 812 } as const;

/** Kill CSS motion / caret blink before a screenshot. */
export async function freezeMotion(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
    `,
  });
}

/**
 * Replace relative-age strings in text nodes with a stable token.
 * Text nodes cannot be masked via Locator; freeze instead.
 */
export async function freezeRelativeAges(page: Page): Promise<void> {
  await page.evaluate(() => {
    const re = /\b\d+\s*[smhd]\s*ago\b/gi;
    const walk = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent ?? "";
        if (re.test(text)) {
          re.lastIndex = 0;
          node.textContent = text.replace(re, "• ago");
        }
        return;
      }
      const el = node as Element;
      // Skip script/style
      if (el.nodeType === Node.ELEMENT_NODE) {
        const tag = el.tagName;
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") return;
      }
      for (const child of Array.from(node.childNodes)) walk(child);
    };
    walk(document.body);
  });
}

/** Apply dark (default) or light (`html.light` chart/token flip) theme. */
export async function applyTheme(page: Page, theme: ThemeName): Promise<void> {
  await page.evaluate((mode) => {
    const root = document.documentElement;
    if (mode === "light") {
      root.classList.add("light");
      root.style.colorScheme = "light";
    } else {
      root.classList.remove("light");
      root.style.colorScheme = "dark";
    }
  }, theme);
}

/**
 * Locators painted pink by toHaveScreenshot({ mask }).
 * Keep selectors structural — no app data-testid additions.
 */
export function dynamicMaskLocators(page: Page): Locator[] {
  return [
    // Prices / deltas / USD (poll or recompute)
    page.locator("main .font-mono").filter({ hasText: /¢|pts|\$|%/ }),
    page.locator("main p.font-mono"),
    // Sparkline wells + chart surfaces
    page.locator("main div.h-9"),
    page.locator('main [role="img"][aria-label*="Price history" i]'),
    page.locator("main canvas"),
    page.locator("main svg[viewBox]"),
    // Sticky live ticker (desktop)
    page.locator("div.sticky.bottom-0"),
    // Health banner (API status flips) — testid already present in app
    page.getByTestId("health-banner"),
    // Authed portfolio banner (bankroll / P&L strip)
    page.locator("div.sticky.top-0").filter({ hasText: /Bankroll|Unreal/i }),
    // Header auth identity (unique signup email) + paper $ chip
    page.locator("header [title*='@']"),
    page.locator("header").getByText(/\$[\d,]+/),
  ];
}

/** Settle fonts + network, then freeze motion/ages for a stable shot. */
export async function prepareStableShot(
  page: Page,
  theme: ThemeName,
): Promise<Locator[]> {
  await page.evaluate(() => document.fonts.ready).catch(() => undefined);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  // One short beat for client pollers to paint once.
  await page.waitForTimeout(800);
  await freezeMotion(page);
  await freezeRelativeAges(page);
  await applyTheme(page, theme);
  // Re-freeze ages after theme paint (no DOM rebuild expected, but cheap).
  await freezeRelativeAges(page);
  // Scroll to top so viewport shots are deterministic.
  await page.evaluate(() => window.scrollTo(0, 0));
  return dynamicMaskLocators(page);
}

export const SHOT_OPTIONS = {
  animations: "disabled" as const,
  caret: "hide" as const,
  // Viewport-only: fullPage heights drift when lazy sections (similar markets,
  // briefs, atlas) settle differently — especially after chromium mutates the
  // shared e2e SQLite. First-screen chrome is what guards theme/spacing/overflow.
  fullPage: false,
  // Windows ClearType / AA variance; still fails on real layout breakage.
  maxDiffPixelRatio: 0.02,
};
