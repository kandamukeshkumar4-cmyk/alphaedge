import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  compileScanner,
  createScanner,
  getScanner,
  listScannerRuns,
  listScanners,
  pauseScanner,
  resetScannersMockStore,
  resumeScanner,
  runScannerNow,
  scheduleLabel,
  setScannersFetch,
} from "@/lib/scanners-api";

/** Force the live-first client onto its mock fallback for every call. */
const offlineFetch: typeof fetch = () => Promise.reject(new Error("offline"));
const realFetch: typeof fetch = (...args) => fetch(...args);

describe("scanners-api mock client", () => {
  beforeEach(() => {
    resetScannersMockStore();
    setScannersFetch(offlineFetch);
  });

  afterEach(() => {
    setScannersFetch(realFetch);
  });

  it("compiles plain English into a spec shape", async () => {
    const { spec, source } = await compileScanner(
      "Scan NBA markets with whale flow and price trend over 3 days plus news sentiment every 15 minutes, volume above 50,000, top 10",
    );
    expect(source).toBe("mock");
    // Spec shape: universe / schedule / steps[] / delivery / limit / notes.
    expect(Array.isArray(spec.universe.categories)).toBe(true);
    expect(typeof spec.universe.minimum_volume).toBe("number");
    expect(typeof spec.schedule.interval_minutes).toBe("number");
    expect(Array.isArray(spec.steps)).toBe(true);
    expect(spec.steps.length).toBeGreaterThan(0);

    expect(spec.universe.categories).toContain("nba");
    expect(spec.universe.minimum_volume).toBe(50_000);
    expect(spec.schedule.interval_minutes).toBe(15);
    expect(spec.limit).toBe(10);
    const types = spec.steps.map((s) => s.type);
    expect(types).toContain("WHALE_FLOW");
    expect(types).toContain("PRICE_TREND");
    expect(types).toContain("NEWS_SENTIMENT");
    // Two or more signal steps earn a DIRECTION_ALIGNMENT step.
    expect(types).toContain("DIRECTION_ALIGNMENT");
    expect(spec.steps.find((s) => s.type === "PRICE_TREND")?.window_days).toBe(3);
    expect(scheduleLabel(spec)).toBe("every 15 min");
  });

  it("creates a draft scanner and runs it to completion", async () => {
    const { spec } = await compileScanner("whale flow and model edge on crypto markets");
    const created = await createScanner({ name: "Crypto whale watcher", spec });
    expect(created.source).toBe("mock");
    expect(created.scanner.status).toBe("draft");
    expect(created.scanner.name).toBe("Crypto whale watcher");
    expect(created.scanner.spec.steps.length).toBeGreaterThan(0);

    const { run } = await runScannerNow(created.scanner.id);
    expect(run).not.toBeNull();
    expect(run?.status).toBe("completed");
    expect(run?.result?.candidates.length ?? 0).toBeGreaterThan(0);
    expect(run?.result?.counts.universe ?? 0).toBeGreaterThan(0);

    // Draft flips to active after the first run (backend parity).
    const after = await getScanner(created.scanner.id);
    expect(after.scanner?.status).toBe("active");
    expect(after.scanner?.latest_run?.id).toBe(run?.id);

    // The new scanner shows up in the list.
    const list = await listScanners();
    expect(list.scanners.some((s) => s.id === created.scanner.id)).toBe(true);
  });

  it("flips status on pause and resume", async () => {
    const seeded = await listScanners();
    const active = seeded.scanners.find((s) => s.status === "active");
    expect(active).toBeDefined();

    const paused = await pauseScanner(active!.id);
    expect(paused.scanner?.status).toBe("paused");
    expect((await getScanner(active!.id)).scanner?.status).toBe("paused");

    const resumed = await resumeScanner(active!.id);
    expect(resumed.scanner?.status).toBe("active");
    expect((await getScanner(active!.id)).scanner?.status).toBe("active");
  });

  it("lists run history newest first", async () => {
    const { runs, source } = await listScannerRuns("scn-mock-whale");
    expect(source).toBe("mock");
    expect(runs.length).toBeGreaterThanOrEqual(2);
    for (const run of runs) {
      expect(run.started_at.length).toBeGreaterThan(0);
      expect(["running", "completed", "empty", "failed"]).toContain(run.status);
    }
    const starts = runs.map((r) => Date.parse(r.started_at));
    const sorted = [...starts].sort((a, b) => b - a);
    expect(starts).toEqual(sorted);
    // Newest seeded run carries a candidate table + counts.
    expect(runs[0]?.result?.candidates.length ?? 0).toBeGreaterThan(0);
  });
});
