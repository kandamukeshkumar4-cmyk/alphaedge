import { describe, expect, it } from "vitest";

import {
  applyStreamEvent,
  isChartPayload,
  isTablePayload,
  listSessions,
  MOCK_SESSION,
  resetTerminalMockStore,
  SENSE_CHIPS,
  stepSummaryText,
  streamSession,
  type StreamEvent,
} from "@/lib/terminal-api";

describe("terminal-api mock client", () => {
  it("lists a seeded session with real step kinds", async () => {
    resetTerminalMockStore();
    const { sessions, source } = await listSessions();
    expect(source).toBe("mock");
    expect(sessions.length).toBeGreaterThan(0);
    expect(sessions[0]?.steps.length).toBeGreaterThanOrEqual(4);
    for (const step of sessions[0]?.steps ?? []) {
      expect(["table", "chart", "text"]).toContain(step.kind);
      expect(step.title.length).toBeGreaterThan(0);
    }
  });

  it("exposes six sense chips", () => {
    expect(SENSE_CHIPS.map((c) => c.id)).toEqual([
      "whale",
      "news",
      "sentiment",
      "model",
      "odds",
      "arb",
    ]);
  });

  it("narrows payload kinds", () => {
    expect(isTablePayload({ columns: ["a"], rows: [["1"]] })).toBe(true);
    expect(isChartPayload({ points: [{ t: 1, v: 0.5 }] })).toBe(true);
    expect(isTablePayload({ points: [{ t: 1, v: 0.5 }] } as never)).toBe(false);
  });

  it("streams steps, scoreboard, and done for a mock session", async () => {
    resetTerminalMockStore();
    const events: StreamEvent[] = [];
    for await (const ev of streamSession(MOCK_SESSION.id)) events.push(ev);
    const steps = events.filter((e) => e.type === "step");
    expect(steps.length).toBeGreaterThanOrEqual(4);
    expect(events.some((e) => e.type === "scoreboard")).toBe(true);
    expect(events.at(-1)?.type).toBe("done");

    let session: import("@/lib/terminal-api").ResearchSession = {
      ...MOCK_SESSION,
      steps: [],
    };
    for (const ev of events) session = applyStreamEvent(session, ev);
    expect(session.status).toBe("completed");
    expect(session.steps.length).toBe(steps.length);
    expect(session.summary.scoreboard.length).toBe(6);
    expect(session.summary.bull_case).toBeTruthy();
    expect(session.summary.bear_case).toBeTruthy();
  });

  it("derives a one-line step summary", () => {
    const step = MOCK_SESSION.steps[0];
    expect(stepSummaryText(step).length).toBeGreaterThan(0);
  });
});
