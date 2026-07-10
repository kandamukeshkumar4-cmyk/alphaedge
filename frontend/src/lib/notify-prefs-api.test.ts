import { describe, expect, it } from "vitest";
import {
  buildNotifyPrefsView,
  filterItemsByPrefs,
  isCategoryEnabled,
  toggleFamily,
  type NotifyPrefsResponse,
} from "./notify-prefs-api";

const STORED: NotifyPrefsResponse = {
  families: {
    "news:mispricing": true,
    "anomaly:unusual_flow": false,
    "delta:*": false,
    "screener:*": false,
    arb: true,
  },
  enabled: ["news:mispricing", "arb"],
  all_families: ["news:mispricing", "anomaly:unusual_flow", "delta:*", "screener:*", "arb"],
  source: "stored",
  paper_trading_only: true,
  disclaimer: "Notification preferences are STORED and applied in-app only.",
};

describe("buildNotifyPrefsView", () => {
  it("shows the sign-in branch for anonymous callers (no toggles)", () => {
    const view = buildNotifyPrefsView(null, false);
    expect(view.authed).toBe(false);
    expect(view.reachable).toBe(false);
    expect(view.toggles).toHaveLength(0);
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("is unreachable when authed but the API returns null", () => {
    const view = buildNotifyPrefsView(null, true);
    expect(view.authed).toBe(true);
    expect(view.reachable).toBe(false);
    expect(view.toggles).toHaveLength(0);
  });

  it("builds a toggle per family with labels + enabled flags", () => {
    const view = buildNotifyPrefsView(STORED, true);
    expect(view.reachable).toBe(true);
    expect(view.source).toBe("stored");
    expect(view.toggles.map((t) => t.key)).toEqual([
      "news:mispricing",
      "anomaly:unusual_flow",
      "delta:*",
      "screener:*",
      "arb",
    ]);
    expect(view.toggles[0]).toEqual({
      key: "news:mispricing",
      label: "News mispricing",
      enabled: true,
    });
    expect(view.toggles[1].enabled).toBe(false);
    expect(view.enabled).toEqual(["news:mispricing", "arb"]);
  });

  it("defaults every family on when no stored row (source default)", () => {
    const view = buildNotifyPrefsView(
      {
        families: {
          "news:mispricing": true,
          "anomaly:unusual_flow": true,
          "delta:*": true,
          "screener:*": true,
          arb: true,
        },
        source: "default",
      },
      true,
    );
    expect(view.source).toBe("default");
    expect(view.toggles.every((t) => t.enabled)).toBe(true);
    expect(view.enabled).toHaveLength(5);
  });
});

describe("toggleFamily (optimistic)", () => {
  it("adds a disabled family back, in canonical order", () => {
    expect(toggleFamily(["news:mispricing", "arb"], "delta:*")).toEqual([
      "news:mispricing",
      "delta:*",
      "arb",
    ]);
  });

  it("removes an enabled family", () => {
    expect(toggleFamily(["news:mispricing", "arb"], "arb")).toEqual(["news:mispricing"]);
  });

  it("does not mutate its input", () => {
    const input = ["news:mispricing"];
    toggleFamily(input, "arb");
    expect(input).toEqual(["news:mispricing"]);
  });

  it("supports opting out of everything", () => {
    expect(toggleFamily(["arb"], "arb")).toEqual([]);
  });
});

describe("isCategoryEnabled + filterItemsByPrefs", () => {
  it("maps categories to their governing pref family", () => {
    const enabled = ["news:mispricing", "arb"];
    expect(isCategoryEnabled("news", enabled)).toBe(true);
    expect(isCategoryEnabled("screener", enabled)).toBe(false);
    expect(isCategoryEnabled("anomaly", enabled)).toBe(false);
  });

  it("always surfaces categories with no governing pref (dutching/other)", () => {
    expect(isCategoryEnabled("dutching", [])).toBe(true);
    expect(isCategoryEnabled("other", [])).toBe(true);
  });

  it("passes items through untouched when enabled is null (anon)", () => {
    const items = [{ signal_type: "screener:volume" }, { signal_type: "news:mispricing" }];
    expect(filterItemsByPrefs(items, null)).toHaveLength(2);
  });

  it("hides items whose category the user disabled", () => {
    const items = [
      { signal_type: "screener:volume" },
      { signal_type: "news:mispricing" },
      { signal_type: "arb" },
    ];
    const kept = filterItemsByPrefs(items, ["news:mispricing", "arb"]);
    expect(kept.map((i) => i.signal_type)).toEqual(["news:mispricing", "arb"]);
  });
});
