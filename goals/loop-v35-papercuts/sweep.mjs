/**
 * U1 READ-ONLY prod papercut sweep — Loop V35.
 * Chromium only; desktop 1280 + mobile 375; dark + light (html.light).
 * Evidence only — does not mutate prod.
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

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 375, height: 812 },
];

const STATIC_ROUTES = [
  "/",
  "/markets",
  "/portfolio",
  "/leaderboard",
  "/signals",
  "/eval",
  "/alerts",
  "/feed",
];

fs.mkdirSync(EVIDENCE, { recursive: true });

function slugify(route) {
  if (route === "/") return "home";
  return route
    .replace(/^\//, "")
    .replace(/[?#].*$/, "")
    .replace(/[^a-zA-Z0-9._-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 80) || "route";
}

async function dismissChrome(page) {
  // Skip onboarding
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
  // Cookie / consent banners if any
  for (const label of [/Accept/i, /Got it/i, /Dismiss/i, /Close/i]) {
    const btn = page.getByRole("button", { name: label }).first();
    if (await btn.isVisible({ timeout: 400 }).catch(() => false)) {
      await btn.click().catch(() => {});
    }
  }
}

async function setTheme(page, theme) {
  await page.evaluate((t) => {
    const html = document.documentElement;
    if (t === "light") html.classList.add("light");
    else html.classList.remove("light");
  }, theme);
  await page.waitForTimeout(200);
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function collectObservations(page, route, viewport, theme) {
  return page.evaluate(
    ({ route, viewport, theme }) => {
      const notes = [];
      const html = document.documentElement;
      const body = document.body;

      // Horizontal overflow
      if (body.scrollWidth > html.clientWidth + 2) {
        notes.push({
          kind: "overflow-x",
          detail: `scrollWidth=${body.scrollWidth} clientWidth=${html.clientWidth}`,
        });
      }

      // Truncation candidates with ellipsis that look cut off
      const trunc = [];
      document.querySelectorAll("*").forEach((el) => {
        const s = getComputedStyle(el);
        if (
          (s.textOverflow === "ellipsis" || s.overflow === "hidden") &&
          el.scrollWidth > el.clientWidth + 4 &&
          el.textContent &&
          el.textContent.trim().length > 8 &&
          el.clientWidth > 40
        ) {
          const text = el.textContent.trim().slice(0, 80);
          if (trunc.length < 5) trunc.push(text);
        }
      });
      if (trunc.length) {
        notes.push({ kind: "truncation", detail: trunc.join(" | ") });
      }

      // Empty-ish panels with vague copy
      const emptyish = [];
      document.querySelectorAll("p, span, div, li, h2, h3").forEach((el) => {
        const t = (el.textContent || "").trim();
        if (
          /^(n\/?a|—|-|none|no data|coming soon|todo|placeholder|loading\.\.\.)$/i.test(
            t,
          ) ||
          /lorem ipsum|fake data|alpha_quant/i.test(t)
        ) {
          emptyish.push(t.slice(0, 60));
        }
      });
      if (emptyish.length) {
        notes.push({
          kind: "suspicious-empty-copy",
          detail: [...new Set(emptyish)].slice(0, 6).join(" | "),
        });
      }

      // Dead / hash-only / javascript:void links in main
      const badLinks = [];
      document.querySelectorAll("a[href]").forEach((a) => {
        const href = a.getAttribute("href") || "";
        if (
          href === "#" ||
          href === "" ||
          href.startsWith("javascript:") ||
          href === "/undefined" ||
          href.includes("null")
        ) {
          badLinks.push(`${(a.textContent || "").trim().slice(0, 40)} → ${href}`);
        }
      });
      if (badLinks.length) {
        notes.push({
          kind: "suspect-link",
          detail: badLinks.slice(0, 8).join(" ; "),
        });
      }

      // Low-contrast accent-on-accent heuristic: bg-primary/accent without text-bg
      const contrastHits = [];
      document.querySelectorAll("button, a, span, div").forEach((el) => {
        const cls = el.className?.toString?.() || "";
        if (
          /\bbg-(primary|accent|accent-bright)\b/.test(cls) &&
          !/\btext-bg\b/.test(cls) &&
          !/\btext-on-accent\b/.test(cls) &&
          !/\btext-primary\b/.test(cls) &&
          !/\btext-accent\b/.test(cls) &&
          el.clientWidth > 20 &&
          el.clientHeight > 12
        ) {
          const t = (el.textContent || "").trim().slice(0, 40);
          if (t) contrastHits.push(`${t} [${cls.slice(0, 80)}]`);
        }
      });
      if (contrastHits.length) {
        notes.push({
          kind: "accent-contrast-suspect",
          detail: [...new Set(contrastHits)].slice(0, 6).join(" ; "),
        });
      }

      // Overlapping fixed elements covering content (naive)
      const main = document.getElementById("main-content");
      const mainRect = main?.getBoundingClientRect();
      if (mainRect) {
        const blockers = [];
        document.querySelectorAll("*[class*='fixed'], *[class*='sticky']").forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.width < 8 || r.height < 8) return;
          // element covering center of main?
          const cx = mainRect.left + mainRect.width / 2;
          const cy = mainRect.top + Math.min(120, mainRect.height / 3);
          const topEl = document.elementFromPoint(cx, cy);
          if (topEl && !main.contains(topEl) && el.contains(topEl)) {
            blockers.push((el.className || el.tagName).toString().slice(0, 60));
          }
        });
        if (blockers.length) {
          notes.push({
            kind: "overlay-block",
            detail: [...new Set(blockers)].slice(0, 4).join(" | "),
          });
        }
      }

      // Visible console-visible error banners
      const errText = [];
      document.querySelectorAll("*").forEach((el) => {
        const t = (el.childNodes.length === 1 && el.textContent
          ? el.textContent.trim()
          : ""
        );
        if (/failed to (load|fetch)|something went wrong|error \d{3}/i.test(t) && t.length < 120) {
          errText.push(t);
        }
      });
      if (errText.length) {
        notes.push({
          kind: "error-banner",
          detail: [...new Set(errText)].slice(0, 4).join(" | "),
        });
      }

      // Theme toggle presence
      const themeToggle = Array.from(document.querySelectorAll("button, a")).find((el) =>
        /theme|dark|light|mode/i.test(
          `${el.getAttribute("aria-label") || ""} ${el.textContent || ""} ${el.title || ""}`,
        ),
      );
      notes.push({
        kind: "meta",
        detail: JSON.stringify({
          route,
          viewport,
          theme,
          title: document.title,
          hasLightClass: html.classList.contains("light"),
          themeToggle: themeToggle
            ? (themeToggle.getAttribute("aria-label") || themeToggle.textContent || "").trim().slice(0, 60)
            : null,
          h1: document.querySelector("h1")?.textContent?.trim()?.slice(0, 80) || null,
        }),
      });

      return notes;
    },
    { route, viewport, theme },
  );
}

async function resolveMarketAndTrader(page) {
  await page.goto(`${BASE}/markets`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissChrome(page);
  await page.waitForTimeout(1500);
  const marketHref = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[href*="/markets/"]'));
    const hit = links.find((a) => {
      const h = a.getAttribute("href") || "";
      return /\/markets\/[a-z0-9-]+/i.test(h) && !h.endsWith("/markets");
    });
    return hit?.getAttribute("href") || null;
  });

  await page.goto(`${BASE}/leaderboard`, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissChrome(page);
  await page.waitForTimeout(1500);
  const traderHref = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a[href*="/traders/"]'));
    return links[0]?.getAttribute("href") || null;
  });

  return { marketHref, traderHref };
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const findings = [];
  const consoleErrors = [];

  const probe = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await dismissChrome(probe);
  const { marketHref, traderHref } = await resolveMarketAndTrader(probe);
  await probe.close();

  const routes = [
    ...STATIC_ROUTES,
    marketHref || "/markets/nba-2025-01-15-lal-bos",
    traderHref || null,
  ].filter(Boolean);

  findings.push({
    id: "META-ROUTES",
    severity: "info",
    summary: `Resolved market=${marketHref} trader=${traderHref}`,
    evidence: [],
  });

  // Theme toggle existence check once
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await dismissChrome(page);
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1000);
    const toggle = await page.evaluate(() => {
      const els = Array.from(document.querySelectorAll("button, [role='switch'], a"));
      return els
        .filter((el) =>
          /theme|dark mode|light mode|color scheme/i.test(
            `${el.getAttribute("aria-label") || ""} ${el.textContent || ""} ${el.title || ""}`,
          ),
        )
        .map((el) => (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 80));
    });
    const shotName = "00_theme_toggle_search_desktop_dark";
    await shot(page, shotName);
    if (!toggle.length) {
      findings.push({
        id: "PC-THEME-01",
        severity: "medium",
        summary:
          "No visible theme toggle in chrome; app is dark-only (html.light only flips chart tokens). Sweep used DOM class toggle for light residual.",
        routes: ["/"],
        evidence: [`evidence/${shotName}.png`],
        impact: "Users cannot switch themes; work-order expected both themes via toggle.",
      });
    }
    await ctx.close();
  }

  for (const vp of VIEWPORTS) {
    for (const theme of ["dark", "light"]) {
      for (const route of routes) {
        const ctx = await browser.newContext({
          viewport: { width: vp.width, height: vp.height },
          isMobile: vp.name === "mobile",
          hasTouch: vp.name === "mobile",
        });
        const page = await ctx.newPage();
        page.on("pageerror", (err) => {
          consoleErrors.push({ route, vp: vp.name, theme, msg: String(err.message).slice(0, 200) });
        });
        page.on("console", (msg) => {
          if (msg.type() === "error") {
            consoleErrors.push({
              route,
              vp: vp.name,
              theme,
              msg: msg.text().slice(0, 200),
            });
          }
        });

        await dismissChrome(page);
        const url = route.startsWith("http") ? route : `${BASE}${route}`;
        let status = 0;
        try {
          const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 });
          status = resp?.status() || 0;
        } catch (e) {
          findings.push({
            id: `PC-NAV-${slugify(route)}-${vp.name}-${theme}`,
            severity: "high",
            summary: `Failed to load ${route} (${vp.name}/${theme}): ${String(e).slice(0, 120)}`,
            routes: [route],
            evidence: [],
            impact: "Route unreachable during sweep",
          });
          await ctx.close();
          continue;
        }

        await dismissChrome(page);
        await setTheme(page, theme);
        await page.waitForTimeout(1200);

        const name = `${slugify(route)}_${vp.name}_${theme}`;
        const file = await shot(page, name);
        const obs = await collectObservations(page, route, vp.name, theme);

        // Status code issues
        if (status >= 400) {
          findings.push({
            id: `PC-HTTP-${slugify(route)}`,
            severity: "high",
            summary: `${route} returned HTTP ${status} (${vp.name}/${theme})`,
            routes: [route],
            evidence: [`evidence/${name}.png`],
            impact: "Broken route",
          });
        }

        for (const o of obs) {
          if (o.kind === "meta") continue;
          if (o.kind === "overflow-x") {
            findings.push({
              id: `PC-OX-${slugify(route)}-${vp.name}-${theme}`,
              severity: vp.name === "mobile" ? "high" : "medium",
              summary: `Horizontal overflow on ${route} (${vp.name}/${theme}): ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Content clipped / sideways scroll",
            });
          } else if (o.kind === "suspect-link") {
            findings.push({
              id: `PC-LINK-${slugify(route)}-${vp.name}`,
              severity: "medium",
              summary: `Suspect links on ${route}: ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Dead or broken navigation",
            });
          } else if (o.kind === "error-banner") {
            findings.push({
              id: `PC-ERR-${slugify(route)}-${vp.name}`,
              severity: "high",
              summary: `Error/empty failure copy on ${route}: ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "User sees failure state",
            });
          } else if (o.kind === "accent-contrast-suspect" && theme === "dark" && vp.name === "desktop") {
            findings.push({
              id: `PC-CONTRAST-${slugify(route)}`,
              severity: "medium",
              summary: `Accent fill without text-bg on ${route}: ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Possible low-contrast text on accent",
            });
          } else if (o.kind === "suspicious-empty-copy" && vp.name === "desktop" && theme === "dark") {
            findings.push({
              id: `PC-EMPTY-${slugify(route)}`,
              severity: "low",
              summary: `Suspicious empty/placeholder copy on ${route}: ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Possibly dishonest or vague empty state",
            });
          } else if (o.kind === "truncation" && vp.name === "mobile") {
            findings.push({
              id: `PC-TRUNC-${slugify(route)}-${vp.name}`,
              severity: "low",
              summary: `Truncated text on ${route} (${vp.name}): ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Labels cut off at 375px",
            });
          } else if (o.kind === "overlay-block") {
            findings.push({
              id: `PC-OVERLAY-${slugify(route)}-${vp.name}`,
              severity: "medium",
              summary: `Fixed overlay may block content on ${route}: ${o.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Content hard to reach",
            });
          }
        }

        // Manual visual checks via bounding boxes: zero-height sections, overlapping CTAs
        const visual = await page.evaluate(() => {
          const issues = [];
          // Buttons smaller than 44px on mobile width
          if (window.innerWidth <= 400) {
            document.querySelectorAll("button, a.rounded-lg, [role='button']").forEach((el) => {
              const r = el.getBoundingClientRect();
              if (r.height > 0 && r.height < 36 && r.width > 40) {
                const label = (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 40);
                if (label) issues.push({ kind: "small-tap", detail: `${label} h=${Math.round(r.height)}` });
              }
            });
          }
          // Images with broken natural size
          document.querySelectorAll("img").forEach((img) => {
            if (img.complete && img.naturalWidth === 0 && img.getAttribute("src")) {
              issues.push({ kind: "broken-img", detail: img.getAttribute("src")?.slice(0, 80) });
            }
          });
          return issues.slice(0, 8);
        });
        for (const v of visual) {
          if (v.kind === "broken-img") {
            findings.push({
              id: `PC-IMG-${slugify(route)}`,
              severity: "medium",
              summary: `Broken image on ${route}: ${v.detail}`,
              routes: [route],
              evidence: [`evidence/${name}.png`],
              impact: "Missing visual asset",
            });
          }
        }

        await ctx.close();
      }
    }
  }

  // Deduplicate by id keeping first
  const seen = new Set();
  const deduped = [];
  for (const f of findings) {
    if (seen.has(f.id)) continue;
    seen.add(f.id);
    deduped.push(f);
  }

  // Unique console errors
  const uniqConsole = [];
  const cseen = new Set();
  for (const c of consoleErrors) {
    const k = `${c.route}|${c.msg}`;
    if (cseen.has(k)) continue;
    cseen.add(k);
    uniqConsole.push(c);
  }

  const out = {
    base: BASE,
    generatedAt: new Date().toISOString(),
    routes,
    marketHref,
    traderHref,
    findings: deduped,
    consoleErrors: uniqConsole.slice(0, 40),
  };
  fs.writeFileSync(path.join(__dirname, "sweep-raw.json"), JSON.stringify(out, null, 2));
  console.log(JSON.stringify({ findingCount: deduped.length, consoleErrors: uniqConsole.length, routes }, null, 2));
  await browser.close();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
