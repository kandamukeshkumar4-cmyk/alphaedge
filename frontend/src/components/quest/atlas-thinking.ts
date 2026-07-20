/**
 * Loop V77 A2 — staged in-flight thinking phases for ATLAS Analyze.
 * Phases advance by elapsed wall time only; never claim completion early.
 */

export type AtlasThinkingPhase = {
  id: string;
  label: string;
  /** Elapsed ms from request start when this phase becomes active. */
  afterMs: number;
};

export const ATLAS_THINKING_PHASES: readonly AtlasThinkingPhase[] = [
  { id: "read", label: "Reading market data…", afterMs: 0 },
  { id: "signals", label: "Checking signals…", afterMs: 1200 },
  { id: "compose", label: "Composing analysis…", afterMs: 2800 },
] as const;

/** Pick the latest phase whose afterMs <= elapsedMs. */
export function atlasThinkingPhaseAt(elapsedMs: number): AtlasThinkingPhase {
  let current = ATLAS_THINKING_PHASES[0];
  for (const phase of ATLAS_THINKING_PHASES) {
    if (elapsedMs >= phase.afterMs) current = phase;
  }
  return current;
}

/** Next phase boundary after elapsedMs, or null if on the last phase. */
export function atlasNextPhaseBoundaryMs(elapsedMs: number): number | null {
  for (const phase of ATLAS_THINKING_PHASES) {
    if (phase.afterMs > elapsedMs) return phase.afterMs;
  }
  return null;
}
