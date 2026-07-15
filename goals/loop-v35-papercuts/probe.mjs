import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, "../../frontend/package.json"));
const { chromium } = require("@playwright/test");

const BASE = "https://alphaedge-frontend-three.vercel.app";

async function main() {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await p.addInitScript(() => localStorage.setItem("alphaedge.onboarded", "true"));
  await p.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await p.waitForTimeout(1500);
  const info = await p.evaluate(() => {
    const input = document.querySelector('input[aria-label="Search markets"]');
    const label = input?.closest("label");
    const wrap = input?.closest(".relative");
    const parent = wrap?.parentElement;
    const c = document.createElement("canvas");
    const ctx = c.getContext("2d");
    ctx.font = "14px Figtree, sans-serif";
    return {
      inputW: Math.round(input?.getBoundingClientRect().width || 0),
      labelW: Math.round(label?.getBoundingClientRect().width || 0),
      wrapW: Math.round(wrap?.getBoundingClientRect().width || 0),
      parentW: Math.round(parent?.getBoundingClientRect().width || 0),
      parentCls: parent?.className,
      placeholder: input?.placeholder,
      placeholderPx: Math.round(ctx.measureText(input?.placeholder || "").width),
    };
  });

  await p.goto(BASE + "/alerts", { waitUntil: "domcontentloaded", timeout: 60000 });
  await p.waitForTimeout(2000);
  const alertDom = await p.evaluate(() =>
    Array.from(document.querySelectorAll("a"))
      .filter((a) => (a.getAttribute("href") || "").includes("/markets"))
      .slice(0, 8)
      .map((a) => ({ text: (a.textContent || "").trim().slice(0, 90), href: a.getAttribute("href") })),
  );

  const apiSample = await p.evaluate(async () => {
    const bases = [
      "https://mukeshkumar007-alphaedge-api.hf.space",
      "https://alphaedge-api-production-b9db.up.railway.app",
    ];
    for (const base of bases) {
      try {
        const r = await fetch(base + "/api/v1/alerts?limit=2");
        if (r.ok) {
          const data = await r.json();
          return { base, item: data.items?.[0] || data[0] || data };
        }
      } catch {}
    }
    return null;
  });

  // markets page h1 check + mobile header overflow
  await p.setViewportSize({ width: 375, height: 812 });
  await p.goto(BASE + "/markets", { waitUntil: "domcontentloaded", timeout: 60000 });
  await p.waitForTimeout(1500);
  const mobileMarkets = await p.evaluate(() => {
    const header = document.querySelector("header");
    const hr = header?.getBoundingClientRect();
    return {
      overflowX: document.body.scrollWidth > document.documentElement.clientWidth + 1,
      bodyW: document.body.scrollWidth,
      headerScrollW: header?.scrollWidth,
      headerClientW: header?.clientWidth,
      hasH1: !!document.querySelector("h1"),
      h1: document.querySelector("h1")?.textContent?.trim()?.slice(0, 80) || null,
    };
  });

  // portfolio auth gate URL
  await p.goto(BASE + "/portfolio", { waitUntil: "domcontentloaded", timeout: 60000 });
  await p.waitForTimeout(1500);
  const portfolio = { url: p.url(), h1: await p.locator("h1").first().textContent().catch(() => null) };

  // eval 404 resource
  const failed = [];
  p.on("response", (r) => {
    if (r.status() >= 400) failed.push({ url: r.url().slice(0, 120), status: r.status() });
  });
  await p.setViewportSize({ width: 1280, height: 800 });
  await p.goto(BASE + "/eval", { waitUntil: "networkidle", timeout: 90000 }).catch(() => {});
  await p.waitForTimeout(1000);

  console.log(JSON.stringify({ info, alertDom, apiSample, mobileMarkets, portfolio, failed: failed.slice(0, 10) }, null, 2));
  await b.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
