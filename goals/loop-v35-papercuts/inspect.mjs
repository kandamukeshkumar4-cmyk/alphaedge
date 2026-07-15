/**
 * Precise DOM inspector for U1 — extracts real text, not vision guesses.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, "../../frontend/package.json"));
const { chromium } = require("@playwright/test");
const EVIDENCE = path.join(__dirname, "evidence");
const BASE = "https://alphaedge-frontend-three.vercel.app";

async function dismiss(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("alphaedge.onboarded", "true");
    } catch {}
  });
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(EVIDENCE, `${name}.png`), fullPage: false });
}

async function inspect(page, route, vp) {
  const data = await page.evaluate(() => {
    const text = (el) => (el?.textContent || "").replace(/\s+/g, " ").trim();
    const search = document.querySelector('input[placeholder*="Search"], input[type="search"], [role="searchbox"]');
    const searchPh = search?.getAttribute("placeholder") || search?.getAttribute("aria-label") || null;

    // Notification badges while logged out
    const badges = Array.from(document.querySelectorAll("*"))
      .filter((el) => {
        const t = text(el);
        return /^(9\+|99\+|\\d+)$/.test(t) && el.getBoundingClientRect().width < 40;
      })
      .map((el) => text(el))
      .slice(0, 8);

    // Accent solid fills missing text-bg (exclude decorative dots)
    const contrast = [];
    document.querySelectorAll("a, button").forEach((el) => {
      const cls = el.className?.toString?.() || "";
      if (!/\bbg-(primary|accent|accent-bright)\b/.test(cls)) return;
      if (/-dim\b|\/\d+/.test(cls) && !/\bbg-(primary|accent|accent-bright)\s/.test(cls.replace(/\/\d+/g, ""))) {
        // allow bg-primary/15 etc
      }
      const solid =
        /\bbg-(primary|accent|accent-bright)\b/.test(cls) &&
        !/\bbg-(primary|accent|accent-bright)-(dim)\b/.test(cls) &&
        !/\bbg-(primary|accent|accent-bright)\/\d+/.test(cls);
      if (!solid) return;
      if (/\btext-bg\b/.test(cls)) return;
      const t = text(el);
      if (!t || t.length > 60) return;
      const cs = getComputedStyle(el);
      contrast.push({ t, cls: cls.slice(0, 140), color: cs.color, bg: cs.backgroundColor });
    });

    // Empty-state copy harvest
    const empties = [];
    document.querySelectorAll("h1,h2,h3,p,li,div").forEach((el) => {
      const t = text(el);
      if (t.length < 12 || t.length > 160) return;
      if (
        /no .* yet|not yet|unavailable|coming soon|no data|empty|sign in|log in to|placeholder|n\/a|failed to|404|undefined|null/i.test(
          t,
        )
      ) {
        if (el.children.length <= 2) empties.push(t);
      }
    });

    // Slug-as-label (raw pm- shown as primary title)
    const slugLabels = [];
    document.querySelectorAll("a, p, span, h1, h2, h3, td, li").forEach((el) => {
      const t = text(el);
      if (/^pm-[a-z0-9-]{20,}$/i.test(t)) slugLabels.push(t.slice(0, 80));
    });

    // Duplicate nav Portfolio
    const portfolioLinks = Array.from(document.querySelectorAll("a"))
      .filter((a) => text(a) === "Portfolio")
      .map((a) => ({ href: a.getAttribute("href"), cls: (a.className || "").toString().slice(0, 80) }));

    // Theme toggle
    const themeToggle = Array.from(document.querySelectorAll("button, a, [role='switch']")).filter((el) =>
      /theme|dark mode|light mode|color scheme/i.test(
        `${el.getAttribute("aria-label") || ""} ${text(el)} ${el.title || ""}`,
      ),
    ).length;

    // Header search overflow / truncated placeholder
    let searchMetrics = null;
    if (search) {
      const r = search.getBoundingClientRect();
      searchMetrics = {
        placeholder: searchPh,
        w: Math.round(r.width),
        scrollW: search.scrollWidth,
        value: search.value,
      };
    }

    // Bottom nav / fixed footer collision on mobile
    const bottomNav = document.querySelector('[aria-label*="Bottom"], nav.fixed, .fixed.bottom-0');
    let bottomOverlap = null;
    if (bottomNav) {
      const r = bottomNav.getBoundingClientRect();
      bottomOverlap = { h: Math.round(r.height), top: Math.round(r.top), visible: r.height > 0 };
    }

    // Page title / h1
    const h1 = text(document.querySelector("h1"));
    const title = document.title;

    // Visible error strings
    const errors = [];
    document.querySelectorAll("p, div, span, pre").forEach((el) => {
      const t = text(el);
      if (/ENSEMBLE_ENABLED|AutoLab line:|X-Admin-API-Key|Failed to load|404|stack trace/i.test(t) && t.length < 220) {
        errors.push(t);
      }
    });

    // Truncated market titles that are the ONLY content (ok) vs truncated CTAs
    const truncBad = [];
    document.querySelectorAll("button, a").forEach((el) => {
      const s = getComputedStyle(el);
      if (s.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 6) {
        const t = text(el);
        if (t && t.length < 40 && !/pm-|will /i.test(t)) truncBad.push(t);
      }
    });

    // Logged-out notification badge counts
    const notifBadges = Array.from(document.querySelectorAll("header span, header div"))
      .map((el) => text(el))
      .filter((t) => /^\d+\+?$/.test(t));

    return {
      h1,
      title,
      searchMetrics,
      themeToggle,
      portfolioLinks,
      contrast: contrast.slice(0, 12),
      empties: [...new Set(empties)].slice(0, 20),
      slugLabels: [...new Set(slugLabels)].slice(0, 12),
      errors: [...new Set(errors)].slice(0, 12),
      truncBad: [...new Set(truncBad)].slice(0, 8),
      notifBadges: [...new Set(notifBadges)],
      bottomOverlap,
      overflowX: document.body.scrollWidth > document.documentElement.clientWidth + 1,
      bodyW: document.body.scrollWidth,
      clientW: document.documentElement.clientWidth,
    };
  });
  return { route, vp, ...data };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const routes = [
    "/",
    "/markets",
    "/markets/pm-will-spain-win-the-2026-fifa-world-cup-963",
    "/portfolio",
    "/leaderboard",
    "/signals",
    "/eval",
    "/alerts",
    "/feed",
  ];
  const results = [];

  for (const vp of [
    { name: "desktop", width: 1280, height: 800 },
    { name: "mobile", width: 375, height: 812 },
  ]) {
    for (const route of routes) {
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.name === "mobile",
      });
      await dismiss(page);
      const consoleErrs = [];
      page.on("console", (m) => {
        if (m.type() === "error") consoleErrs.push(m.text().slice(0, 160));
      });
      await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.waitForTimeout(1800);
      const info = await inspect(page, route, vp.name);
      info.consoleErrs = [...new Set(consoleErrs)].slice(0, 6);

      // Cropped evidence for specific suspects
      if (route === "/" && vp.name === "desktop") {
        await shot(page, "find_home_header_desktop");
      }
      if (route === "/alerts" && vp.name === "mobile") {
        await shot(page, "find_alerts_mobile_viewport");
      }
      if (route === "/eval" && vp.name === "desktop") {
        await shot(page, "find_eval_desktop_viewport");
      }
      if (route === "/portfolio" && vp.name === "desktop") {
        await shot(page, "find_portfolio_auth_gate");
      }
      if (route === "/markets/pm-will-spain-win-the-2026-fifa-world-cup-963" && vp.name === "desktop") {
        await shot(page, "find_market_detail_desktop");
      }
      if (route === "/signals" && vp.name === "desktop") {
        await shot(page, "find_signals_desktop_viewport");
      }

      // Light theme residual check once per route on desktop
      if (vp.name === "desktop") {
        await page.evaluate(() => document.documentElement.classList.add("light"));
        await page.waitForTimeout(300);
        const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        const hasLight = await page.evaluate(() => document.documentElement.classList.contains("light"));
        info.lightResidual = { hasLight, bodyBg: lightBg };
        await shot(page, `find_${route.replace(/\W+/g, "_") || "home"}_light_residual`);
      }

      results.push(info);
      await page.close();
    }
  }

  // Try to find any trader profile URL from API via page fetch
  {
    const page = await browser.newPage();
    await dismiss(page);
    await page.goto(`${BASE}/feed`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(2500);
    const trader = await page.evaluate(async () => {
      const anchors = Array.from(document.querySelectorAll("a[href*='/traders/']")).map((a) =>
        a.getAttribute("href"),
      );
      if (anchors[0]) return anchors[0];
      // scrape usernames that might link
      return null;
    });
    results.push({ route: "/traders-resolve", trader });
    if (trader) {
      await page.goto(`${BASE}${trader}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.waitForTimeout(1500);
      await shot(page, "find_trader_desktop");
      results.push(await inspect(page, trader, "desktop"));
    } else {
      // Document honest empty: leaderboard has no traders
      results.push({
        route: "/traders/<any>",
        blocked: true,
        reason: "Leaderboard empty + feed has no /traders/ links while logged out",
      });
    }
    await page.close();
  }

  fs.writeFileSync(path.join(__dirname, "inspect.json"), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
