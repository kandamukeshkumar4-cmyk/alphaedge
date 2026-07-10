import { describe, expect, it } from "vitest";
import {
  buildWatchlistItemView,
  buildWatchlistView,
  toggleWatchlistSlug,
  type WatchlistResponse,
} from "./watchlist-api";

describe("buildWatchlistItemView", () => {
  it("formats price, edge, and last-move with tones", () => {
    const view = buildWatchlistItemView({
      slug: "pm-lal-bos",
      title: "Lakers beat Celtics",
      snapshot: { yes_price: 0.62, last_move_pts: 3.4 },
      edge: { edge_vs_book: 0.08 },
    });
    expect(view.title).toBe("Lakers beat Celtics");
    expect(view.yesPriceLabel).toBe("62¢");
    expect(view.hasYesPrice).toBe(true);
    expect(view.edgeLabel).toBe("+8.0 pts");
    expect(view.edgeTone).toBe("up");
    expect(view.lastMoveLabel).toBe("+3.4 pts");
    expect(view.lastMoveTone).toBe("up");
  });

  it("degrades honestly when snapshot/edge are absent", () => {
    const view = buildWatchlistItemView({ slug: "pm-thin" });
    expect(view.title).toBe("pm-thin");
    expect(view.yesPriceLabel).toBe("—");
    expect(view.hasYesPrice).toBe(false);
    expect(view.edgeLabel).toBeNull();
    expect(view.edgeTone).toBe("neutral");
    expect(view.lastMoveLabel).toBeNull();
  });

  it("tones negative edge/move down", () => {
    const view = buildWatchlistItemView({
      slug: "s",
      snapshot: { yes_price: 0.4, last_move_pts: -2 },
      edge: { edge_vs_book: -0.05 },
    });
    expect(view.edgeTone).toBe("down");
    expect(view.lastMoveTone).toBe("down");
  });
});

describe("buildWatchlistView", () => {
  it("returns [] for null / missing items", () => {
    expect(buildWatchlistView(null)).toEqual([]);
    expect(buildWatchlistView({} as WatchlistResponse)).toEqual([]);
  });

  it("maps items and drops entries without a slug", () => {
    const raw: WatchlistResponse = {
      items: [
        { slug: "a", snapshot: { yes_price: 0.5 } },
        { slug: "", snapshot: null },
      ],
    };
    const rows = buildWatchlistView(raw);
    expect(rows).toHaveLength(1);
    expect(rows[0].slug).toBe("a");
  });
});

describe("toggleWatchlistSlug", () => {
  it("adds a slug that is absent", () => {
    const { next, action } = toggleWatchlistSlug(["a"], "b");
    expect(action).toBe("add");
    expect(new Set(next)).toEqual(new Set(["a", "b"]));
  });

  it("removes a slug that is present", () => {
    const { next, action } = toggleWatchlistSlug(["a", "b"], "a");
    expect(action).toBe("remove");
    expect(next).toEqual(["b"]);
  });

  it("does not mutate the input array", () => {
    const input = ["a"];
    toggleWatchlistSlug(input, "b");
    expect(input).toEqual(["a"]);
  });
});
