import { categorizeSignal } from "./signals-dashboard-view-model";

/**
 * F04: normalise the evidence carried on `news:mispricing` and
 * `anomaly:unusual_flow` signal payloads (backend G03/G04, see API-NOTES.md) so
 * /signals and /feed can render it consistently. Neutral wording only — the
 * anomaly note is an observation ("no public catalyst found"), never an
 * accusation. Absent fields degrade gracefully to null.
 */
export type NewsEvidence = {
  kind: "news";
  headline: string;
  url: string | null;
  modelP: number | null;
  marketP: number | null;
  edgeLabel: string | null;
};

export type CatalystEvidence = {
  kind: "catalyst";
  note: string;
};

export type SignalEvidence = NewsEvidence | CatalystEvidence;

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function numOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Pure: extract renderable evidence from a signal payload, or null. */
export function extractSignalEvidence(
  signalType: string,
  payload: Record<string, unknown> | null | undefined,
): SignalEvidence | null {
  if (!payload) return null;
  const category = categorizeSignal(signalType);

  if (category === "news") {
    const headline = str(payload.headline);
    if (!headline) return null;
    const modelP = numOrNull(payload.model_p);
    const marketP = numOrNull(payload.market_p);
    const gap = numOrNull(payload.gap);
    const edge = gap ?? (modelP !== null && marketP !== null ? modelP - marketP : null);
    return {
      kind: "news",
      headline,
      url: str(payload.news_url),
      modelP,
      marketP,
      edgeLabel: edge === null ? null : `${edge >= 0 ? "+" : ""}${(edge * 100).toFixed(1)} pts`,
    };
  }

  if (category === "anomaly") {
    const catalyst = str(payload.catalyst);
    const note = str(payload.note);
    if (catalyst === "none_found" || note) {
      return {
        kind: "catalyst",
        note: note ?? "No public catalyst found in the news window.",
      };
    }
  }

  return null;
}

/** Build a lookup index of evidence keyed by platform+market+family. */
export function buildEvidenceIndex(
  events: {
    signal_type: string;
    platform: string;
    market_id: string;
    payload: Record<string, unknown>;
  }[],
): Map<string, SignalEvidence> {
  const index = new Map<string, SignalEvidence>();
  for (const ev of events) {
    const evidence = extractSignalEvidence(ev.signal_type, ev.payload);
    if (!evidence) continue;
    const key = evidenceKey(ev.platform, ev.market_id, ev.signal_type);
    if (!index.has(key)) index.set(key, evidence); // first (most recent) wins
  }
  return index;
}

/** Stable key for evidence lookup — platform + market + signal family. */
export function evidenceKey(platform: string, marketId: string, signalType: string): string {
  return `${platform}::${marketId}::${categorizeSignal(signalType)}`;
}
