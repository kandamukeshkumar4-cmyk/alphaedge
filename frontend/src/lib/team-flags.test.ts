import { describe, expect, it } from "vitest";
import { flagForTeam } from "./team-flags";

describe("flagForTeam", () => {
  it("returns the exact-match flag (case/space-insensitive)", () => {
    expect(flagForTeam("  Canada ")).toBe("🇨🇦");
    expect(flagForTeam("USA")).toBe("🇺🇸");
  });

  it("resolves a multi-word country key", () => {
    expect(flagForTeam("Bosnia and Herzegovina")).toBe("🇧🇦");
  });

  it("matches by substring when there is no exact key", () => {
    // "South Korea" contains the "korea" key.
    expect(flagForTeam("South Korea")).toBe("🇰🇷");
  });

  it("maps tie / draw to the handshake", () => {
    expect(flagForTeam("Draw")).toBe("🤝");
    expect(flagForTeam("tie")).toBe("🤝");
  });

  it("falls back to the soccer ball for an unknown team", () => {
    expect(flagForTeam("Zzz United")).toBe("⚽");
  });
});
