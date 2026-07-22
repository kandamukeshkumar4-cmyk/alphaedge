import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  addSubscription,
  forkScanner,
  forkSkill,
  isSubscribed,
  listSubscriptions,
  removeSubscription,
  resetCommunityMockStore,
  setCommunityFetch,
} from "@/lib/community-api";
import {
  listScreener,
  resetScreenerMockStore,
  setScreenerFetch,
  sortItems,
} from "@/lib/screener-api";
import { resetSkillsMockStore } from "@/lib/skills-api";
import { resetScannersMockStore } from "@/lib/scanners-api";

// Force every live call to fail so the mock fallback path is deterministic.
function offlineFetch(): () => Promise<never> {
  return () => Promise.reject(new Error("offline"));
}

describe("V85 screener + community mock clients", () => {
  beforeEach(() => {
    resetScreenerMockStore();
    resetCommunityMockStore();
    resetSkillsMockStore();
    resetScannersMockStore();
    setScreenerFetch(offlineFetch());
    setCommunityFetch(offlineFetch());
  });

  afterEach(() => {
    setScreenerFetch((...args) => fetch(...args));
    setCommunityFetch((...args) => fetch(...args));
  });

  it("listScreener returns seeded mock rows with the contract shape", async () => {
    const { result, source } = await listScreener();
    expect(source).toBe("mock");
    expect(result.total).toBeGreaterThan(0);
    expect(result.items.length).toBe(result.total);
    for (const item of result.items) {
      expect(typeof item.slug).toBe("string");
      expect(item.slug.length).toBeGreaterThan(0);
      expect(typeof item.title).toBe("string");
      expect(typeof item.category).toBe("string");
      expect(typeof item.volume).toBe("number");
      expect(item.volume).toBeGreaterThanOrEqual(0);
      expect(item.yes_price).toBeGreaterThanOrEqual(0);
      expect(item.yes_price).toBeLessThanOrEqual(1);
      expect(typeof item.move_24h).toBe("number");
      expect(typeof item.model_edge).toBe("number");
      expect(item.hours_to_close === null || typeof item.hours_to_close === "number").toBe(true);
    }
  });

  it("screener filters + sort narrow the mock set (category, min_edge, closing)", async () => {
    // category filter
    const nba = await listScreener({ category: "nba" });
    expect(nba.source).toBe("mock");
    expect(nba.result.items.length).toBeGreaterThan(0);
    for (const i of nba.result.items) expect(i.category).toBe("nba");

    // min_edge filters out small edges (uses |edge|)
    const all = await listScreener();
    const minEdge = 0.02;
    const edged = await listScreener({ min_edge: minEdge });
    for (const i of edged.result.items) {
      expect(Math.abs(i.model_edge)).toBeGreaterThanOrEqual(minEdge);
    }
    expect(edged.result.items.length).toBeLessThanOrEqual(all.result.items.length);

    // closing sort: ascending hours_to_close, nulls last — and matches the
    // pure sortItems helper applied to the same full mock set.
    const fullAll = await listScreener();
    const closing = await listScreener({ sort: "closing" });
    expect(closing.result.items.map((i) => i.slug)).toEqual(
      sortItems(fullAll.result.items, "closing").map((i) => i.slug),
    );
    const hours = closing.result.items
      .map((i) => i.hours_to_close)
      .filter((h): h is number => h !== null);
    const asc = [...hours].sort((a, b) => a - b);
    expect(hours).toEqual(asc);
  });

  it("forkSkill/forkScanner mock-copy the source and are findable + not_found for unknown", async () => {
    const skillFork = await forkSkill("confluence");
    expect(skillFork.ok).toBe(true);
    if (skillFork.ok) {
      expect(skillFork.source).toBe("mock");
      expect(skillFork.skill.id).not.toBe("confluence");
      expect(skillFork.skill.name).toContain("fork");
      expect(skillFork.skill.run_count).toBe(0);
    }
    const missingSkill = await forkSkill("does-not-exist");
    expect(missingSkill.ok).toBe(false);
    expect(missingSkill.ok === false && missingSkill.reason).toBe("not_found");

    const scnFork = await forkScanner("scn-mock-whale");
    expect(scnFork.ok).toBe(true);
    if (scnFork.ok) {
      expect(scnFork.source).toBe("mock");
      expect(scnFork.scanner.id).not.toBe("scn-mock-whale");
      expect(scnFork.scanner.status).toBe("draft");
      expect(scnFork.scanner.latest_run).toBeNull();
    }
    const missingScn = await forkScanner("nope");
    expect(missingScn.ok).toBe(false);
    expect(missingScn.ok === false && missingScn.reason).toBe("not_found");
  });

  it("subscriptions add/remove/list toggle membership idempotently", async () => {
    const initial = await listSubscriptions();
    expect(initial.source).toBe("mock");
    expect(initial.subscriptions.length).toBeGreaterThan(0);

    // Add a new subscription (whale skill).
    const afterAdd = await addSubscription("skill", "whale");
    expect(isSubscribed(afterAdd.subscriptions, "skill", "whale")).toBe(true);
    // Idempotent: adding again does not duplicate.
    const afterAdd2 = await addSubscription("skill", "whale");
    expect(afterAdd2.subscriptions.filter((s) => subKey(s) === "skill|whale").length).toBe(1);

    // Remove it.
    const afterRemove = await removeSubscription("skill", "whale");
    expect(isSubscribed(afterRemove.subscriptions, "skill", "whale")).toBe(false);
    // Idempotent remove.
    const afterRemove2 = await removeSubscription("skill", "whale");
    expect(isSubscribed(afterRemove2.subscriptions, "skill", "whale")).toBe(false);

    // Unknown ref_type normalizes to "skill" and is tolerated.
    const ok = await addSubscription("skill", "price");
    expect(isSubscribed(ok.subscriptions, "skill", "price")).toBe(true);
  });
});

function subKey(s: { ref_type: string; ref_id: string }): string {
  return `${s.ref_type}|${s.ref_id}`;
}
