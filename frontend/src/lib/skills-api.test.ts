import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  getSkill,
  listSkills,
  resetSkillsMockStore,
  runSkill,
  setSkillsFetch,
} from "@/lib/skills-api";
import {
  getSession,
  resetTerminalMockStore,
  setTerminalFetch,
} from "@/lib/terminal-api";

describe("skills-api mock client", () => {
  beforeEach(() => {
    resetSkillsMockStore();
    resetTerminalMockStore();
    // Force live failure everywhere so tests are deterministic offline.
    setSkillsFetch(() => Promise.reject(new Error("offline")));
    setTerminalFetch(() => Promise.reject(new Error("offline")));
  });

  afterEach(() => {
    setSkillsFetch((...args) => fetch(...args));
    setTerminalFetch((...args) => fetch(...args));
  });

  it("lists seeded skills with the expected shape (fallback)", async () => {
    const { skills, source } = await listSkills();
    expect(source).toBe("mock");
    expect(skills.length).toBeGreaterThan(0);
    for (const s of skills) {
      expect(typeof s.id).toBe("string");
      expect(s.name.length).toBeGreaterThan(0);
      expect(s.description.length).toBeGreaterThan(0);
      expect(Array.isArray(s.template)).toBe(true);
      expect(typeof s.run_count).toBe("number");
      expect(typeof s.is_public).toBe("boolean");
    }
    const kinds = new Set(skills.flatMap((s) => s.template.map((t) => t.kind)));
    for (const k of kinds) expect(["table", "chart", "text"]).toContain(k);
  });

  it("runSkill returns a session id the terminal can load (mock parity)", async () => {
    const { session_id, source } = await runSkill("confluence");
    expect(source).toBe("mock");
    expect(session_id.length).toBeGreaterThan(0);

    // Mock run seeds a terminal session findable via getSession.
    const { session } = await getSession(session_id);
    expect(session).not.toBeNull();
    expect(session?.id).toBe(session_id);
    expect(session?.status).toBe("completed");
  });

  it("falls back to mock when the live API is unavailable", async () => {
    const { skills, source } = await listSkills();
    expect(source).toBe("mock");
    expect(skills.length).toBeGreaterThan(0);

    const { skill, source: gs } = await getSkill("whale");
    expect(gs).toBe("mock");
    expect(skill?.id).toBe("whale");
    expect(skill?.icon.length).toBeGreaterThan(0);
  });
});
