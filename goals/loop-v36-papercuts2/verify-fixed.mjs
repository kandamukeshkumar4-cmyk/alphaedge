/**
 * Confirm V35 PC01–PC07 still clean on LOCAL stack after V36 Q1.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, "../../frontend/package.json"));
const { chromium } = require("@playwright/test");

const BASE =
  process.env.PLAYWRIGHT_BASE_URL?.trim() || "http://127.0.0.1:31017";
const OUT = path.join(__dirname, "evidence", "q2-pc-verify.json");

async function dismiss(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("alphaedge.onboarded", "true");
    } catch {
      /* ignore */
    }
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await dismiss(page);
  const results = [];

  // PC01 — search width
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1200);
  const search = await page.evaluate(() => {
    const el = document.querySelector(
      'input[placeholder*="Search"], input[type="search"], [role="searchbox"]',
    );
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      placeholder: el.getAttribute("placeholder"),
      w: Math.round(r.width),
      clipped: el.scrollWidth > el.clientWidth + 4,
    };
  });
  results.push({
    id: "PC01",
    // Original crush was ~117–165px with clipped placeholder; require readable
    // width + no clipping (PC10 also keeps page scrollWidth == viewport).
    ok: !!search && search.w >= 165 && !search.clipped && !/ \(/.test(search.placeholder || ""),
    detail: search,
  });

  // PC03 — markets h1
  await page.goto(`${BASE}/markets`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1500);
  const marketsH1 = await page.locator("h1").first().textContent().catch(() => null);
  results.push({
    id: "PC03",
    ok: /markets/i.test(marketsH1 || ""),
    detail: { h1: marketsH1 },
  });

  // PC02 — alerts no raw pm- as group heading
  await page.goto(`${BASE}/alerts`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1500);
  const alertSlugs = await page.evaluate(() => {
    const hits = [];
    document.querySelectorAll("h1,h2,h3,button,a,p,span").forEach((el) => {
      const t = (el.textContent || "").trim();
      if (/^pm-[a-z0-9-]{20,}$/i.test(t)) hits.push(t.slice(0, 60));
    });
    return [...new Set(hits)].slice(0, 8);
  });
  results.push({ id: "PC02", ok: alertSlugs.length === 0, detail: { alertSlugs } });

  // PC04 — eval no harness dump
  await page.goto(`${BASE}/eval`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1500);
  const evalBody = await page.locator("body").innerText();
  const harness =
    /ENSEMBLE_ENABLED|AutoLab line:|X-Admin-API-Key/i.test(evalBody);
  results.push({
    id: "PC04",
    ok: !harness,
    detail: { harnessDump: harness },
  });

  // PC05 — portfolio login next=
  await page.goto(`${BASE}/portfolio`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(2000);
  const url = page.url();
  const hasNext =
    !/\/auth\/login/i.test(url) || /[?&]next=/.test(url);
  results.push({ id: "PC05", ok: hasNext, detail: { url } });

  // PC06 — market title humanize fallback
  await page.goto(`${BASE}/markets/pm-will-spain-win-the-2026-fifa-world-cup-963`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.waitForTimeout(1500);
  const title = await page.title();
  results.push({
    id: "PC06",
    ok: !/^pm-[a-z0-9-]+\s*\|/i.test(title),
    detail: { title },
  });

  // PC07 — markets empty copy not thin one-liner only
  await page.goto(`${BASE}/markets`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1500);
  // click a sparse filter if present
  const emptyCopy = await page.evaluate(() => {
    const texts = [];
    document.querySelectorAll("p").forEach((p) => {
      const t = (p.textContent || "").trim();
      if (/no markets/i.test(t)) texts.push(t);
    });
    return texts.slice(0, 6);
  });
  results.push({
    id: "PC07",
    ok: !emptyCopy.some((t) => /^No markets in this filter\.?$/i.test(t)),
    detail: { emptyCopy },
  });

  // PC08 — color-scheme dark, no theme toggle
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(800);
  const theme = await page.evaluate(() => ({
    colorScheme: getComputedStyle(document.documentElement).colorScheme,
    toggle: Array.from(document.querySelectorAll("button,a")).some((el) =>
      /^(theme|dark mode|light mode)$/i.test(
        (el.getAttribute("aria-label") || el.textContent || "").trim(),
      ),
    ),
  }));
  results.push({
    id: "PC08",
    ok: theme.colorScheme === "dark" && !theme.toggle,
    detail: theme,
  });

  // PC09 — leaderboard honest empty CTAs
  await page.goto(`${BASE}/leaderboard`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.waitForTimeout(2000);
  const lb = await page.evaluate(() => {
    const body = document.body.innerText;
    return {
      honest: /No ranked traders yet/i.test(body),
      browse: !!document.querySelector('a[href="/markets"]'),
      invented: /quant_kestrel|edge_seeker/i.test(body) && /No ranked/i.test(body),
    };
  });
  results.push({
    id: "PC09",
    ok: lb.honest && !lb.invented,
    detail: lb,
  });

  const summary = {
    base: BASE,
    at: new Date().toISOString(),
    allOk: results.every((r) => r.ok),
    results,
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
  await browser.close();
  if (!summary.allOk) process.exit(2);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
