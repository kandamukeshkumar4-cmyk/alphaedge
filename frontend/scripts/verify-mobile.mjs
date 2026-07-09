// TASK 4 mobile-only: iPhone viewport against DEPLOYED frontend.
import { chromium, devices } from "playwright";
const FE = "https://alphaedge-frontend-three.vercel.app";
const MKT = "pm-will-morocco-win-the-2026-fifa-world-cup-464";
async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices["iPhone 13"] });
  const results = [];
  for (const [name, url, sel] of [
    ["homepage", `${FE}/`, null],
    ["market-detail", `${FE}/markets/${MKT}`, 'button:has-text("AI Analyze")'],
    ["portfolio", `${FE}/portfolio`, null],
  ]) {
    const page = await ctx.newPage();
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(8000);
      const vw = page.viewportSize();
      const dims = await page.evaluate(() => ({
        scrollW: document.documentElement.scrollWidth,
        notFound: document.body?.innerText?.includes("Market not found"),
        btns: [...document.querySelectorAll("button")].map((b) => b.textContent?.trim()).filter(Boolean).slice(0, 12),
      }));
      const overflow = dims.scrollW - vw.width;
      const noOverflow = overflow <= 1;
      let trade = null;
      if (sel) {
        try { await page.waitForSelector(sel, { timeout: 10000 }); trade = true; } catch { trade = false; }
      }
      results.push({ name, noOverflow, overflow, trade });
      console.log(`${noOverflow && (trade === null || trade) ? "PASS" : "FAIL"}  mobile-${name} — vw=${vw.width} scrollW=${dims.scrollW} overflow=${overflow}px trade=${trade} notFound=${dims.notFound}` + (dims.btns ? ` btns=${JSON.stringify(dims.btns).slice(0,180)}` : ""));
    } catch (e) {
      results.push({ name, noOverflow: false, error: String(e).slice(0,100) });
      console.log(`FAIL  mobile-${name} — ${String(e).slice(0,100)}`);
    } finally { await page.close(); }
  }
  await browser.close();
  const ok = results.every(r => r.noOverflow && (r.trade === null || r.trade));
  console.log(`\nMOBILE_SUMMARY: ${results.filter(r=>r.noOverflow).length}/${results.length} no-overflow; overall=${ok?"PASS":"FAIL"}`);
  process.exit(ok ? 0 : 1);
}
main().catch(e => { console.error(e); process.exit(1); });
