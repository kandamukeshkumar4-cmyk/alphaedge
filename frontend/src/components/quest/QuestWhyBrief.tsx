"use client";

import type { AnalystBrief } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

type Layer = {
  key: string;
  label: string;
  match: (kind: string) => boolean;
};

// Evidence layers mirror the backend alignment scorer (T04): the analyst
// fires when ≥3 of these agree. Citations carry a `kind` we can bucket.
const LAYERS: Layer[] = [
  { key: "price", label: "Price action", match: (k) => /price|delta|jump|volume|orderbook|candle/.test(k) },
  { key: "whale", label: "Whale activity", match: (k) => /whale|position|wallet/.test(k) },
  { key: "news", label: "News", match: (k) => /news|article|headline/.test(k) },
  { key: "model", label: "Model forecast", match: (k) => /model|forecast|prediction|feature/.test(k) },
];

function bucketCitations(brief: AnalystBrief) {
  const buckets = new Map<string, Array<{ index: number; label: string }>>();
  const other: Array<{ index: number; label: string }> = [];
  brief.citations.forEach((c, i) => {
    const kind = String(c.kind ?? "").toLowerCase();
    const label = String(c.label ?? c.ref ?? kind ?? "evidence");
    const layer = LAYERS.find((l) => l.match(kind));
    if (layer) {
      const list = buckets.get(layer.key) ?? [];
      list.push({ index: i + 1, label });
      buckets.set(layer.key, list);
    } else {
      other.push({ index: i + 1, label });
    }
  });
  return { buckets, other };
}

// "Why this brief?" — makes the invisible alignment trigger visible: which
// signal layers contributed evidence, and which stayed silent.
export function QuestWhyBrief({ brief }: { brief: AnalystBrief }) {
  const { buckets, other } = bucketCitations(brief);
  const activeCount = buckets.size;

  return (
    <section className="mt-8 rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
        Why this brief?
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        The analyst publishes when independent signal layers align on one market.
        This brief drew evidence from{" "}
        <span className="font-semibold text-text">
          {activeCount} of {LAYERS.length}
        </span>{" "}
        layers.
      </p>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {LAYERS.map((layer) => {
          const items = buckets.get(layer.key);
          const active = !!items?.length;
          return (
            <div
              key={layer.key}
              className={cn(
                "rounded-xl border px-3.5 py-3",
                active ? "border-accent/30 bg-accent-dim" : "border-border bg-surface-2 opacity-60",
              )}
            >
              <p
                className={cn(
                  "flex items-center gap-2 text-xs font-bold uppercase tracking-wide",
                  active ? "text-accent-bright" : "text-muted-2",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    active ? "bg-accent-bright" : "bg-surface-3",
                  )}
                />
                {layer.label}
              </p>
              {active ? (
                <ul className="mt-1.5 space-y-1">
                  {items.map((it) => (
                    <li key={it.index} className="truncate text-xs text-text">
                      <span className="mr-1.5 font-mono text-[10px] text-accent">
                        [{it.index}]
                      </span>
                      {it.label}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-xs text-muted-2">No evidence cited</p>
              )}
            </div>
          );
        })}
      </div>

      {other.length > 0 && (
        <p className="mt-3 text-xs text-muted-2">
          Plus {other.length} additional citation{other.length > 1 ? "s" : ""} outside
          the four core layers.
        </p>
      )}
    </section>
  );
}
