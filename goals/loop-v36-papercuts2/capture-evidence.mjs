/**
 * Post-fix evidence shots for Loop V36 Q1 (PC08 / PC09).
 * Targets LOCAL stack via PLAYWRIGHT_BASE_URL (default 127.0.0.1:31017).
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
const EVIDENCE = path.join(__dirname, "evidence");
fs.mkdirSync(EVIDENCE, { recursive: true });

async function dismiss(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("alphaedge.onboarded", "true");
    } catch {
      /* ignore */
    }
  });
  const skip = page.getByRole("button", { name: /^Skip$/i }).first();
  if (await skip.isVisible({ timeout: 1200 }).catch(() => false)) {
    await skip.click().catch(() => {});
  }
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log("wrote", file);
  return file;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await dismiss(page);

  // PC08 — dark-only pin
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await page.waitForTimeout(1500);
  const scheme = await page.evaluate(() => ({
    colorScheme: getComputedStyle(document.documentElement).colorScheme,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    themeToggle: Array.from(document.querySelectorAll("button, a")).some((el) =>
      /theme|dark mode|light mode/i.test(
        `${el.getAttribute("aria-label") || ""} ${el.textContent || ""}`,
      ),
    ),
  }));
  console.log("PC08 meta", JSON.stringify(scheme));
  await shot(page, "PC08_dark_only_home");

  // PC09 — leaderboard empty / trader profiles
  await page.goto(`${BASE}/leaderboard`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.waitForTimeout(2500);
  await shot(page, "PC09_leaderboard_empty_or_standings");

  await page.goto(`${BASE}/traders/nobody-ranked-yet`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.waitForTimeout(2000);
  await shot(page, "PC09_trader_profile_unavailable");

  fs.writeFileSync(
    path.join(EVIDENCE, "q1-meta.json"),
    JSON.stringify({ base: BASE, scheme, at: new Date().toISOString() }, null, 2),
  );
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
