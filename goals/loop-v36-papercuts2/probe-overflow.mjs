import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, "../../frontend/package.json"));
const { chromium } = require("@playwright/test");

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:31017";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.addInitScript(() => localStorage.setItem("alphaedge.onboarded", "true"));
await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(1500);
const info = await page.evaluate(() => {
  const html = document.documentElement;
  const body = document.body;
  const before = html.scrollLeft;
  html.scrollLeft = 9999;
  const after = html.scrollLeft;
  html.scrollLeft = before;
  return {
    bodyScrollWidth: body.scrollWidth,
    clientWidth: html.clientWidth,
    pageCanScrollX: after > 0,
  };
});
console.log(JSON.stringify(info));
await browser.close();
