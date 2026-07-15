/**
 * Local-stack API helpers for Loop V28 e2e journeys.
 * Never targets prod; uses the Playwright webServer ports.
 */
import { execFileSync } from "node:child_process";
import path from "node:path";
import type { Page } from "@playwright/test";

// Playwright cwd is frontend/; e2e stack SQLite lives under e2e/.data/.
const SQLITE_PATH =
  process.env.E2E_SQLITE_PATH ??
  path.join(process.cwd(), "e2e", ".data", "loop17.sqlite3");

export function localApiBase(): string {
  const port = process.env.E2E_API_PORT || "18017";
  return `http://127.0.0.1:${port}`;
}

export async function accessTokenFromPage(page: Page): Promise<string> {
  const token = await page.evaluate(() =>
    localStorage.getItem("alphaedge.accessToken"),
  );
  if (!token) {
    throw new Error("No alphaedge.accessToken in localStorage — user not signed in");
  }
  return token;
}

/** PATCH /api/v1/auth/me display_name (public trader handle). */
export async function setDisplayName(
  page: Page,
  displayName: string,
): Promise<string> {
  const token = await accessTokenFromPage(page);
  const res = await page.request.patch(`${localApiBase()}/api/v1/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    data: { display_name: displayName },
  });
  if (!res.ok()) {
    throw new Error(`PATCH /auth/me failed ${res.status()}: ${await res.text()}`);
  }
  const body = (await res.json()) as { display_name: string | null };
  if (!body.display_name) {
    throw new Error("display_name not set on response");
  }
  return body.display_name;
}

/**
 * Opt-out: set users.profile_public via the isolated e2e SQLite file.
 * No public user API exposes this flag (UI also absent) — harness-level set.
 */
export function setProfilePublicViaSqlite(
  email: string,
  profilePublic: boolean,
): void {
  const helper = path.join(
    process.cwd(),
    "e2e",
    "helpers",
    "set_profile_public.py",
  );
  // Windows uses the py launcher; POSIX runners (CI ubuntu) use python3.
  const isWin = process.platform === "win32";
  const out = execFileSync(
    isWin ? "py" : "python3",
    [
      ...(isWin ? ["-3.13"] : []),
      helper,
      SQLITE_PATH,
      email,
      profilePublic ? "1" : "0",
    ],
    { encoding: "utf8" },
  ).trim();
  if (out === "0" || out === "") {
    throw new Error(
      `setProfilePublicViaSqlite: no row updated for ${email} (db=${SQLITE_PATH})`,
    );
  }
}

export const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

/** UI paper buy on the canonical Lakers market. */
export async function paperBuyCanonical(
  page: Page,
  shares = 5,
): Promise<void> {
  await page.goto(`/markets/${CANONICAL_SLUG}`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  const buyYes = page.getByRole("button", { name: /Buy YES/i }).first();
  await buyYes.waitFor({ state: "visible", timeout: 30_000 });
  await buyYes.click();
  const sharesInput = page.locator(`#trading-shares-${CANONICAL_SLUG}`);
  await sharesInput.waitFor({ state: "visible", timeout: 10_000 });
  await sharesInput.fill(String(shares));
  const submit = page.getByRole("button", { name: /Buy YES\s*·/i });
  await submit.click();
  await page
    .getByText(/Order placed|My Position/i)
    .first()
    .waitFor({ state: "visible", timeout: 30_000 });
}
