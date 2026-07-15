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
await page.goto(`${BASE}/?cb=${Date.now()}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(2500);

const info = await page.evaluate(() => {
  const html = document.documentElement;
  const body = document.body;
  const offenders = [];
  document.querySelectorAll("*").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.right <= html.clientWidth + 1) return;
    if (r.width < 8 || r.height < 8) return;
    // skip fully clipped ancestors
    let p = el.parentElement;
    let clipped = false;
    while (p) {
      const s = getComputedStyle(p);
      if ((s.overflowX === "hidden" || s.overflow === "hidden") && p.clientWidth <= html.clientWidth + 1) {
        clipped = true;
        break;
      }
      p = p.parentElement;
    }
    offenders.push({
      tag: el.tagName,
      right: Math.round(r.right),
      w: Math.round(r.width),
      clipped,
      cls: (el.className || "").toString().slice(0, 90),
    });
  });
  offenders.sort((a, b) => b.right - a.right);
  return {
    scrollWidth: body.scrollWidth,
    clientWidth: html.clientWidth,
    unclipped: offenders.filter((o) => !o.clipped).slice(0, 15),
    clippedTop: offenders.filter((o) => o.clipped).slice(0, 5),
  };
});
console.log(JSON.stringify(info, null, 2));
await browser.close();
