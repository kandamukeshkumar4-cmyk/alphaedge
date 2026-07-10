import { describe, expect, it } from "vitest";

import { formatApiDetail } from "./alphaedge-api";

describe("formatApiDetail", () => {
  it("returns string details unchanged", () => {
    expect(formatApiDetail("Email taken", "fallback")).toBe("Email taken");
  });

  it("flattens FastAPI validation-error arrays", () => {
    expect(
      formatApiDetail(
        [
          {
            type: "value_error",
            loc: ["body", "email"],
            msg: "value is not a valid email address",
            input: "x@alphaedge.test",
            ctx: { reason: "reserved" },
          },
        ],
        "fallback",
      ),
    ).toBe("value is not a valid email address");
  });

  it("falls back when detail is empty", () => {
    expect(formatApiDetail(undefined, "Unable to create account")).toBe(
      "Unable to create account",
    );
  });
});
