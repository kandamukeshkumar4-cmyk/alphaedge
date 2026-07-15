/**
 * Supplemental U1 probe — traders + clean market detail + visual QA notes.
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
  const skip = page.getByRole("button", { name: /^Skip$/i }).first();
  if (await skip.isVisible({ timeout: 1000 }).catch(() => false)) await skip.click().catch(() => {});
}

async function capture(page, name) {
  const file = path.join(EVIDENCE, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return name;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const notes = [];

  // Resolve trader from leaderboard API-backed page with longer wait
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await dismiss(page);
    await page.goto(`${BASE}/leaderboard`, { waitUntil: "networkidle", timeout: 90_000 }).catch(async () => {
      await page.goto(`${BASE}/leaderboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    });
    await page.waitForTimeout(3000);
    await capture(page, "leaderboard_resolve_desktop_dark");
    const bodyText = await page.locator("body").innerText();
    const traderHref = await page.evaluate(() => {
      const a = document.querySelector('a[href*="/traders/"]');
      return a?.getAttribute("href") || null;
    });
    notes.push({
      page: "/leaderboard",
      traderHref,
      emptyLike: /no traders|empty|sign in|log in to see/i.test(bodyText),
      snippet: bodyText.slice(0, 500),
    });

    if (traderHref) {
      await page.goto(`${BASE}${traderHref}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.waitForTimeout(2000);
      await capture(page, "traders_detail_desktop_dark");
      await page.setViewportSize({ width: 375, height: 812 });
      await page.waitForTimeout(500);
      await capture(page, "traders_detail_mobile_dark");
      notes.push({ page: traderHref, ok: true });
    } else {
      // Try feed for trader links
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(`${BASE}/feed`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.waitForTimeout(2500);
      const fromFeed = await page.evaluate(() => {
        const a = document.querySelector('a[href*="/traders/"]');
        return a?.getAttribute("href") || null;
      });
      notes.push({ page: "/feed-trader-search", fromFeed });
      if (fromFeed) {
        await page.goto(`${BASE}${fromFeed}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
        await page.waitForTimeout(2000);
        await capture(page, "traders_detail_desktop_dark");
        await page.setViewportSize({ width: 375, height: 812 });
        await page.waitForTimeout(500);
        await capture(page, "traders_detail_mobile_dark");
      }
    }
    await page.close();
  }

  // Clean market detail path
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await dismiss(page);
    await page.goto(`${BASE}/markets`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(2500);
    const slug = await page.evaluate(() => {
      const anchors = Array.from(document.querySelectorAll("a[href]"));
      for (const a of anchors) {
        const href = a.getAttribute("href") || "";
        const m = href.match(/\/markets\/([a-z0-9][a-z0-9-]{8,})/i);
        if (m && !href.includes("view")) return m[1];
        try {
          const u = new URL(href, location.origin);
          const s = u.searchParams.get("slug");
          if (s) return s;
        } catch {}
      }
      return null;
    });
    notes.push({ marketSlug: slug });
    if (slug) {
      for (const pathSuffix of [`/markets/${slug}`, `/markets/view?slug=${slug}`]) {
        await page.setViewportSize({ width: 1280, height: 900 });
        const resp = await page.goto(`${BASE}${pathSuffix}`, {
          waitUntil: "domcontentloaded",
          timeout: 60_000,
        });
        await page.waitForTimeout(2500);
        const name = pathSuffix.includes("view")
          ? "market_view_desktop_dark"
          : "market_slug_desktop_dark";
        await capture(page, name);
        notes.push({
          path: pathSuffix,
          status: resp?.status(),
          title: await page.title(),
          h1: await page.locator("h1").first().textContent().catch(() => null),
        });
        await page.setViewportSize({ width: 375, height: 812 });
        await page.waitForTimeout(600);
        await capture(
          page,
          pathSuffix.includes("view") ? "market_view_mobile_dark" : "market_slug_mobile_dark",
        );
      }

      // Light residual on market detail
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(`${BASE}/markets/${slug}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.evaluate(() => document.documentElement.classList.add("light"));
      await page.waitForTimeout(800);
      await capture(page, "market_slug_desktop_light");
    }
    await page.close();
  }

  // Targeted visual QA pages with annotations
  const targets = [
    { route: "/", name: "qa_home" },
    { route: "/portfolio", name: "qa_portfolio" },
    { route: "/signals", name: "qa_signals" },
    { route: "/eval", name: "qa_eval" },
    { route: "/alerts", name: "qa_alerts" },
    { route: "/feed", name: "qa_feed" },
  ];
  for (const t of targets) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await dismiss(page);
    const consoleMsgs = [];
    page.on("console", (m) => {
      if (m.type() === "error") consoleMsgs.push(m.text().slice(0, 180));
    });
    await page.goto(`${BASE}${t.route}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(2000);
    await capture(page, `${t.name}_desktop_dark`);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(600);
    await capture(page, `${t.name}_mobile_dark`);

    // Collect visible CTA classes that violate text-bg on accent fills
    const contrast = await page.evaluate(() => {
      const hits = [];
      document.querySelectorAll("a, button, span").forEach((el) => {
        const cls = el.className?.toString?.() || "";
        if (!/\bbg-(primary|accent|accent-bright)(?:\/|\b)/.test(cls)) return;
        if (/\btext-bg\b|\btext-on-accent\b/.test(cls)) return;
        // dim backgrounds are intentionally tinted
        if (/\bbg-(primary|accent)-dim\b/.test(cls) && !/\bbg-(primary|accent)\b/.test(cls.replace(/-dim/g, ""))) {
          // still check solid bg-primary without -dim
        }
        if (/\bbg-(primary|accent|accent-bright)\b/.test(cls) && !/-dim/.test(cls)) {
          const cs = getComputedStyle(el);
          hits.push({
            text: (el.textContent || "").trim().slice(0, 50),
            cls: cls.slice(0, 120),
            color: cs.color,
            bg: cs.backgroundColor,
          });
        }
      });
      return hits.slice(0, 10);
    });

    // Layout metrics
    const layout = await page.evaluate(() => {
      const html = document.documentElement;
      const body = document.body;
      const header = document.querySelector("header");
      const bottom = document.querySelector("nav, [class*='BottomNav']");
      return {
        overflowX: body.scrollWidth > html.clientWidth + 1,
        scrollWidth: body.scrollWidth,
        clientWidth: html.clientWidth,
        headerH: header?.getBoundingClientRect().height || 0,
      };
    });

    notes.push({
      route: t.route,
      consoleMsgs: [...new Set(consoleMsgs)].slice(0, 5),
      contrast,
      layout,
    });
    await page.close();
  }

  fs.writeFileSync(path.join(__dirname, "sweep-notes.json"), JSON.stringify(notes, null, 2));
  console.log(JSON.stringify(notes, null, 2));
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
