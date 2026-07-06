"use client";

// Market-slug entry point for briefs — where every "✦ AI Analyze" button and
// brief-card link lands. Resolves the slug to its LATEST brief and forwards to
// the canonical detail view (/research/brief?id=…). When no brief exists yet,
// offers to run the analyst on demand (optionally through a persona lens) and
// forwards to the fresh brief when it lands.
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { API_BASE } from "@/lib/alphaedge-api";
import { fetchBriefs } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

const PERSONAS = [
  { id: "", label: "General desk" },
  { id: "macro", label: "Macro desk" },
  { id: "whale-flow", label: "Whale flow" },
  { id: "news", label: "News desk" },
] as const;

export default function BriefBySlugClient({ slug: slugProp }: { slug?: string } = {}) {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const slug = slugProp ?? params?.slug ?? "";
  const [state, setState] = useState<"resolving" | "none" | "running" | "failed">("resolving");
  const [persona, setPersona] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let dead = false;
    fetchBriefs({ market: slug, limit: 1 })
      .then((page) => {
        if (dead) return;
        const brief = page.items[0];
        if (brief) router.replace(`/research/brief?id=${brief.id}`);
        else setState("none");
      })
      .catch(() => {
        if (!dead) setState("none");
      });
    return () => {
      dead = true;
    };
  }, [slug, router]);

  const runAnalyst = async () => {
    setState("running");
    setError(null);
    try {
      const qs = new URLSearchParams({ market_slug: slug });
      if (persona) qs.set("persona", persona);
      const res = await fetch(`${API_BASE}/api/v1/analyst/run?${qs}`, { method: "POST" });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `Analyst failed (HTTP ${res.status})`);
      }
      const brief = (await res.json()) as { id: string };
      router.replace(`/research/brief?id=${brief.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyst run failed");
      setState("failed");
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-2xl px-4 py-10 sm:px-6">
      <p className="font-mono text-xs text-muted-2">{slug}</p>
      {state === "resolving" ? (
        <div className="mt-4">
          <div className="skeleton h-6 w-2/3 rounded" />
          <div className="skeleton mt-3 h-4 w-full rounded" />
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-border bg-surface p-6">
          <h1 className="text-lg font-bold text-text">
            {state === "running" ? "Analyst is working…" : "No brief for this market yet"}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            {state === "running"
              ? "Gathering market state, model read, news and whale evidence — then writing a cited brief with a falsifiable claim."
              : "The analyst publishes automatically when ≥3 signal layers align. You can also commission an analysis right now."}
          </p>

          {state !== "running" && (
            <>
              <p className="mt-4 text-[10px] font-bold uppercase tracking-wide text-muted-2">
                Analyst lens
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPersona(p.id)}
                    className={cn(
                      "rounded-pill border px-3 py-1 text-xs font-semibold transition",
                      persona === p.id
                        ? "border-accent-bright text-accent-bright"
                        : "border-border text-muted hover:text-text",
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => void runAnalyst()}
                className="mt-4 rounded-lg bg-accent-bright px-4 py-2 text-sm font-semibold text-bg transition hover:bg-accent"
              >
                ✦ Run the analyst now
              </button>
            </>
          )}

          {state === "running" && (
            <div className="mt-4 flex items-center gap-2 text-xs text-muted">
              <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent-bright" />
              Research in progress — usually a few seconds…
            </div>
          )}

          {error && (
            <p className="mt-3 rounded-lg border border-danger/30 bg-danger-dim px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}
          <p className="mt-4 text-[10px] text-muted-2">
            Research only — never a bet-size recommendation. Paper trading only.
          </p>
        </div>
      )}
    </main>
  );
}
