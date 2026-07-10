// TASK 1 part 2 + TASK 4: Playwright against the DEPLOYED frontend.
// TASK 1 part 2: count WebSocket connections + poll frequency on homepage
//   (Plan 007: one multiplexed WS /api/v1/ws/feed, slow slug-scoped polling —
//   NOT 1s full-catalog polling).
// TASK 4: iPhone viewport — homepage, market detail, portfolio render without
//   horizontal overflow and with tappable trade buttons.
import { chromium, devices } from "playwright";

const FE = "https://alphaedge-frontend-three.vercel.app";
const MKT = "pm-will-morocco-win-the-2026-fifa-world-cup-464";

async function task1NetworkAnalysis() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ ...devices["Desktop Chrome"] });
  const page = await context.newPage();

  const wsConns = [];
  const catalogPolls = [];
  const pricePolls = [];
  const allRequests = [];

  page.on("request", (req) => {
    const url = req.url();
    const type = req.resourceType();
    allRequests.push({ url, type, ts: Date.now() });
    if (type === "websocket" || url.startsWith("ws://") || url.startsWith("wss://")) {
      wsConns.push(url);
    }
    // full-catalog poll = GET /api/v1/markets (no slug) — the BAD old pattern
    if (/\/api\/v1\/markets(\?|$)/.test(url) && !/\/markets\/[^/]+/.test(url)) {
      catalogPolls.push({ url, ts: Date.now() });
    }
    // slug-scoped poll = GET /api/v1/markets/{slug}/prices/latest — the Plan 007 pattern
    if (/\/api\/v1\/markets\/[^/]+\/prices\/latest/.test(url)) {
      pricePolls.push({ url, ts: Date.now() });
    }
  });

  await page.goto(`${FE}/`, { waitUntil: "domcontentloaded", timeout: 45000 });
  // Observe network for 18s to capture poll cadence + WS.
  await page.waitForTimeout(18000);

  // Unique WS endpoints (dedup reconnects to the same URL).
  const uniqueWs = [...new Set(wsConns)];
  // Compute poll intervals for slug-scoped polls.
  const priceIntervals = [];
  for (let i = 1; i < pricePolls.length; i++) {
    priceIntervals.push(pricePolls[i].ts - pricePolls[i - 1].ts);
  }
  const minInterval = priceIntervals.length ? Math.min(...priceIntervals) : null;
  const catalogCount = catalogPolls.length;
  const feedWs = uniqueWs.filter((u) => u.includes("/api/v1/ws/feed"));

  console.log("\n=== TASK 1 part 2: deployed frontend network behavior ===");
  console.log(`WebSocket connections opened: ${wsConns.length}`);
  console.log(`Unique WS endpoints: ${uniqueWs.length}`);
  console.log(`  /api/v1/ws/feed multiplexed WS: ${feedWs.length}`);
  uniqueWs.forEach((u) => console.log(`  WS: ${u}`));
  console.log(`Full-catalog polls (/api/v1/markets): ${catalogCount}`);
  console.log(`Slug-scoped price polls (/markets/{slug}/prices/latest): ${pricePolls.length}`);
  console.log(`Slug-scoped min poll interval: ${minInterval}ms (Plan 007 expects ~5000ms, NOT 1000ms)`);
  console.log(`Sample price poll URLs (first 3):`);
  pricePolls.slice(0, 3).forEach((p) => console.log(`  ${p.url}`));

  const plan007Ok =
    feedWs.length >= 1 &&
    catalogCount <= 2 && // initial SSR fetch is allowed; no repeated 1s catalog polling
    (minInterval === null || minInterval >= 3000); // slug-scoped, not 1s
  console.log(`\nPLAN_007_VERDICT: ${plan007Ok ? "PASS" : "FAIL"} — 1 multiplexed WS + slow slug-scoped polling confirmed deployed`);

  await browser.close();
  return { plan007Ok, wsCount: feedWs.length, catalogCount, pricePollCount: pricePolls.length, minInterval };
}

async function task4MobilePass() {
  const browser = await chromium.launch();
  const iphone = devices["iPhone 13"];
  const context = await browser.newContext({ ...iphone });
  const results = [];

  async function checkSurface(name, url, opts = {}) {
    const page = await context.newPage();
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(3000);
      const vw = page.viewportSize();
      const dims = await page.evaluate(() => ({
        scrollW: document.documentElement.scrollWidth,
        clientW: document.documentElement.clientWidth,
        body: document.body ? document.body.scrollWidth : 0,
      }));
      const overflow = dims.scrollW - vw.width;
      const noOverflow = overflow <= 1; // 1px tolerance for rounding

      let tradeTappable = null;
      if (opts.tradeButtonSelector) {
        const btn = await page.$(opts.tradeButtonSelector);
        tradeTappable = btn ? await btn.isVisible() : false;
      }

      // Take a screenshot for evidence.
      await page.screenshot({ path: `E:\\polymarket clone\\frontend\\mobile-${name}.png`, fullPage: false });

      results.push({ name, overflow, noOverflow, vw: vw.width, scrollW: dims.scrollW, tradeTappable });
      console.log(
        `${noOverflow ? "PASS" : "FAIL"}  mobile-${name} — viewport=${vw.width} scrollW=${dims.scrollW} overflow=${overflow}px` +
          (tradeTappable !== null ? ` tradeBtn=${tradeTappable}` : ""),
      );
    } catch (e) {
      results.push({ name, overflow: -1, noOverflow: false, error: String(e).slice(0, 150) });
      console.log(`FAIL  mobile-${name} — error=${String(e).slice(0, 150)}`);
    } finally {
      await page.close();
    }
  }

  console.log("\n=== TASK 4: iPhone viewport mobile pass ===");
  await checkSurface("homepage", `${FE}/`);
  await checkSurface("market-detail", `${FE}/markets/${MKT}`, { tradeButtonSelector: 'button:has-text("Buy YES"), a:has-text("YES")' });
  await checkSurface("portfolio", `${FE}/portfolio`);

  const allOk = results.every((r) => r.noOverflow && (r.tradeTappable === null || r.tradeTappable === true));
  console.log(`\nMOBILE_SUMMARY: ${results.filter((r) => r.noOverflow).length}/${results.length} surfaces no horizontal overflow; overall=${allOk ? "PASS" : "FAIL"}`);

  await browser.close();
  return { allOk, results };
}

async function main() {
  const t1 = await task1NetworkAnalysis();
  const t4 = await task4MobilePass();
  console.log("\n=== OVERALL ===");
  console.log(`TASK1 part2 (Plan 007): ${t1.plan007Ok ? "PASS" : "FAIL"}`);
  console.log(`TASK4 mobile: ${t4.allOk ? "PASS" : "FAIL"}`);
  process.exit(t1.plan007Ok && t4.allOk ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
