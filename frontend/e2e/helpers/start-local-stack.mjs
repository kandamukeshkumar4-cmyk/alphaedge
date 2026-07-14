/**
 * Boot the Loop V17 local stack for Playwright:
 *   1) isolated SQLite file under e2e/.data/
 *   2) real uvicorn (PAPER_TRADING_ONLY, external loops off)
 *   3) next dev pointing at that API
 *
 * Used as Playwright webServer.command. Never talks to prod Railway.
 */

import { spawn } from "node:child_process";
import { createWriteStream, mkdirSync, rmSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const __dirname = dirname(fileURLToPath(import.meta.url));
const E2E_DIR = resolve(__dirname, "..");
const FRONTEND_DIR = resolve(E2E_DIR, "..");
const REPO_ROOT = resolve(FRONTEND_DIR, "..");
const BACKEND_DIR = join(REPO_ROOT, "backend");
const DATA_DIR = join(E2E_DIR, ".data");
const DB_PATH = join(DATA_DIR, "loop17.sqlite3");
const LOG_DIR = join(DATA_DIR, "logs");

const API_PORT = Number(process.env.E2E_API_PORT || 18017);
const FE_PORT = Number(process.env.E2E_FE_PORT || 31017);
const API_BASE = `http://127.0.0.1:${API_PORT}`;
const FE_BASE = `http://127.0.0.1:${FE_PORT}`;

// Windows-friendly absolute SQLite URL (forward slashes).
const dbUrlPath = DB_PATH.replace(/\\/g, "/");
const DATABASE_URL = `sqlite+aiosqlite:///${dbUrlPath}`;
const DATABASE_URL_SYNC = `sqlite:///${dbUrlPath}`;

const children = [];
let shuttingDown = false;

function log(msg) {
  console.log(`[loop17-stack] ${msg}`);
}

function spawnLogged(name, commandLine, options) {
  // Windows: always use a single shell command string. Passing argv with
  // `shell: true` concatenates unsafely and can drop flags (DEP0190).
  mkdirSync(LOG_DIR, { recursive: true });
  const out = createWriteStream(join(LOG_DIR, `${name}.log`), { flags: "a" });
  const child = spawn(commandLine, {
    ...options,
    shell: true,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.pipe(out);
  child.stderr.pipe(out);
  child.stdout.on("data", (buf) => {
    const line = buf.toString().trim();
    if (line) log(`${name}: ${line.slice(0, 240)}`);
  });
  child.stderr.on("data", (buf) => {
    const line = buf.toString().trim();
    if (line) log(`${name}!: ${line.slice(0, 240)}`);
  });
  child.on("exit", (code, signal) => {
    if (!shuttingDown) {
      log(`${name} exited code=${code} signal=${signal}`);
    }
  });
  children.push(child);
  return child;
}

async function waitForUrl(url, { timeoutMs = 120_000, intervalMs = 500 } = {}) {
  const start = Date.now();
  let lastErr = "";
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2500) });
      if (res.ok || res.status < 500) return;
      lastErr = `HTTP ${res.status}`;
    } catch (err) {
      lastErr = err instanceof Error ? err.message : String(err);
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timeout waiting for ${url}: ${lastErr}`);
}

function backendEnv() {
  return {
    ...process.env,
    PAPER_TRADING_ONLY: "true",
    DATABASE_URL,
    DATABASE_URL_SYNC,
    REDIS_URL: "redis://disabled",
    APP_ENV: "development",
    ADMIN_API_KEY: "dev-admin-key",
    JWT_SECRET_KEY: "loop17-e2e-jwt-secret",
    CORS_ORIGINS: `${FE_BASE},http://localhost:${FE_PORT}`,
    LIVE_FEED_ENABLED: "false",
    SCHEDULER_NEWS_SCAN_ENABLED: "false",
    SCHEDULER_NEWS_MISPRICING_ENABLED: "false",
    SCHEDULER_UNUSUAL_FLOW_ENABLED: "false",
    SCHEDULER_WEATHER_SCAN_ENABLED: "false",
    SCHEDULER_MORNING_RESEARCH_ENABLED: "false",
    SCHEDULER_WHALE_REFRESH_ENABLED: "false",
    SCHEDULER_WC2026_RESOLVE_ENABLED: "false",
    SCHEDULER_EXTERNAL_RESOLVE_ENABLED: "false",
    SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED: "false",
    // Avoid importing a stale backend/.env override for admin keys in local runs.
    PYTHONUNBUFFERED: "1",
  };
}

function quote(path) {
  return `"${path.replace(/"/g, '\\"')}"`;
}

async function initSqlite() {
  mkdirSync(DATA_DIR, { recursive: true });
  if (existsSync(DB_PATH)) {
    rmSync(DB_PATH, { force: true });
  }
  log(`init sqlite schema at ${DB_PATH}`);
  const initScript = join(E2E_DIR, "helpers", "init_sqlite_db.py");
  const cmd = `uv run --extra dev python ${quote(initScript)}`;
  await new Promise((resolvePromise, reject) => {
    const child = spawn(cmd, {
      cwd: BACKEND_DIR,
      env: backendEnv(),
      stdio: "inherit",
      windowsHide: true,
      shell: true,
    });
    child.on("exit", (code) => {
      if (code === 0) resolvePromise();
      else reject(new Error(`init_sqlite_db.py exited ${code}`));
    });
  });
}

function startBackend() {
  log(`starting uvicorn on ${API_PORT}`);
  // Prefer `uv run` so the worktree venv + aiosqlite extra are used.
  const cmd = `uv run --extra dev uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --log-level warning`;
  return spawnLogged("uvicorn", cmd, {
    cwd: BACKEND_DIR,
    env: backendEnv(),
  });
}

function startFrontend() {
  log(`starting next dev on ${FE_PORT}`);
  const cmd = `npm run dev -- --port ${FE_PORT} --hostname 127.0.0.1`;
  return spawnLogged("next", cmd, {
    cwd: FRONTEND_DIR,
    env: {
      ...process.env,
      NEXT_PUBLIC_API_URL: API_BASE,
      NEXT_PUBLIC_WS_URL: API_BASE.replace(/^http/, "ws"),
      // Force local stack; never fall back to HF/prod.
      BROWSER: "none",
    },
  });
}

async function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  log("shutting down children");
  for (const child of children) {
    try {
      if (!child.killed) {
        child.kill("SIGTERM");
      }
    } catch {
      /* ignore */
    }
  }
  // Windows: ensure tree dies
  await sleep(500);
  for (const child of children) {
    try {
      if (!child.killed) child.kill("SIGKILL");
    } catch {
      /* ignore */
    }
  }
}

process.on("SIGINT", () => {
  void shutdown().then(() => process.exit(0));
});
process.on("SIGTERM", () => {
  void shutdown().then(() => process.exit(0));
});

async function main() {
  await initSqlite();
  startBackend();
  await waitForUrl(`${API_BASE}/health`, { timeoutMs: 90_000 });
  const health = await fetch(`${API_BASE}/health`).then((r) => r.json());
  log(`health ok paper_trading_only=${health.paper_trading_only}`);
  if (health.paper_trading_only !== true) {
    throw new Error("backend health missing paper_trading_only=true");
  }

  // Confirm seed catalog made markets available for smoke.
  const markets = await fetch(`${API_BASE}/api/v1/markets`).then((r) => r.json());
  const count = Array.isArray(markets) ? markets.length : markets?.items?.length ?? 0;
  log(`markets seeded count≈${count}`);

  startFrontend();
  await waitForUrl(FE_BASE, { timeoutMs: 120_000 });
  log(`stack ready api=${API_BASE} fe=${FE_BASE}`);

  // Stay alive for Playwright webServer lifecycle.
  await new Promise(() => {});
}

main().catch(async (err) => {
  console.error("[loop17-stack] FATAL", err);
  await shutdown();
  process.exit(1);
});
