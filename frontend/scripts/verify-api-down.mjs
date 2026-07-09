// TASK 2 verification: build with NEXT_PUBLIC_API_URL pointed at a dead port,
// then confirm every surface shows the health banner (sample-data indicator).
// Run after `NEXT_PUBLIC_API_URL=http://localhost:9999 npm run build` and
// `NEXT_PUBLIC_API_URL=http://localhost:9999 npm run start -- --port 3101`.
import { chromium } from "playwright";

const BASE = process.env.BASE_URL || "http://localhost:3101";
const SURFACES = [
  { name: "homepage", path: "/" },
  { name: "markets", path: "/markets" },
  { name: "market-detail", path: "/markets/nba-2025-01-15-lal-bos" },
  { name: "portfolio", path: "/portfolio" },
  { name: "signals", path: "/signals" },
  { name: "leaderboard", path: "/leaderboard" },
  { name: "trade", path: "/trade" },
  { name: "research", path: "/research" },
];

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const results = [];
  for (const s of SURFACES) {
    const page = await context.newPage();
    try {
      await page.goto(`${BASE}${s.path}`, { waitUntil: "networkidle", timeout: 30000 });
      // Give the client-side health probe a moment to fire + render.
      await page.waitForTimeout(2500);
      const banner = await page.$('[data-testid="health-banner"]');
      const status = banner ? await banner.getAttribute("data-status") : null;
      const text = banner ? (await banner.textContent())?.trim() : null;
      const ok = banner !== null && status === "down";
      results.push({ name: s.name, path: s.path, ok, status, text });
      console.log(`${ok ? "PASS" : "FAIL"}  ${s.name} (${s.path}) — banner=${status} text="${text}"`);
    } catch (e) {
      results.push({ name: s.name, path: s.path, ok: false, status: "error", text: String(e) });
      console.log(`FAIL  ${s.name} (${s.path}) — error=${String(e).slice(0, 120)}`);
    } finally {
      await page.close();
    }
  }
  await browser.close();
  const passed = results.filter((r) => r.ok).length;
  console.log(`\nTASK2 SUMMARY: ${passed}/${results.length} surfaces show sample-data indicator`);
  process.exit(passed === results.length ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
