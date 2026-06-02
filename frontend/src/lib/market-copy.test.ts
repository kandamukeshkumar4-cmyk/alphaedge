import { describe, expect, it } from "vitest";

import { marketCountLabel } from "./market-copy";

describe("market copy", () => {
  it("formats singular and plural market counts", () => {
    expect(marketCountLabel(1)).toBe("1 market");
    expect(marketCountLabel(2)).toBe("2 markets");
  });
});
