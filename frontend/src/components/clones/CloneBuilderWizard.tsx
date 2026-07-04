"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { fetchVettedNodes, createClone } from "@/lib/alphaedge-api";
import { NodeToggleCard } from "./NodeToggleCard";

interface CloneBuilderWizardProps {
  token: string;
}

type Step = 1 | 2 | 3;

export function CloneBuilderWizard({ token }: CloneBuilderWizardProps) {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [allNodes, setAllNodes] = useState<string[]>([]);
  const [selectedNodes, setSelectedNodes] = useState<string[]>(["data", "prediction"]);
  const [markets, setMarkets] = useState<string>("nba-2025-01-15-lal-bos");
  const [edgeThreshold, setEdgeThreshold] = useState(5); // percent
  const [cooldown, setCooldown] = useState(60); // minutes
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVettedNodes(token).then((nodes) => {
      setAllNodes(nodes);
    });
  }, [token]);

  function toggleNode(nodeName: string) {
    setSelectedNodes((prev) =>
      prev.includes(nodeName) ? prev.filter((n) => n !== nodeName) : [...prev, nodeName],
    );
  }

  async function handleDeploy() {
    if (!name.trim()) {
      setError("Please give your clone a name.");
      return;
    }
    if (selectedNodes.length === 0) {
      setError("Select at least one node.");
      return;
    }
    setError(null);
    setSubmitting(true);
    const marketList = markets
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const result = await createClone(token, {
      name: name.trim(),
      nodes: selectedNodes,
      markets: marketList,
      edge_threshold: edgeThreshold / 100,
      cooldown_minutes: cooldown,
    });
    setSubmitting(false);

    if (result) {
      router.push("/clones");
    } else {
      setError("Failed to deploy clone. Check your connection and try again.");
    }
  }

  const STEPS: Array<{ n: Step; label: string }> = [
    { n: 1, label: "Nodes" },
    { n: 2, label: "Params" },
    { n: 3, label: "Deploy" },
  ];

  return (
    <div className="mx-auto max-w-2xl">
      {/* Step indicator */}
      <nav className="mb-8 flex items-center gap-2" aria-label="Build steps">
        {STEPS.map((s, i) => (
          <div key={s.n} className="flex items-center gap-2">
            {i > 0 && <div className="h-px w-8 bg-border" />}
            <button
              type="button"
              onClick={() => step > s.n && setStep(s.n)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition",
                step === s.n
                  ? "bg-accent-bright text-bg"
                  : step > s.n
                    ? "cursor-pointer text-muted hover:text-text"
                    : "cursor-default text-muted-2",
              )}
            >
              <span
                className={cn(
                  "grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold",
                  step === s.n ? "bg-bg/20" : step > s.n ? "bg-primary/20 text-primary" : "bg-surface",
                )}
              >
                {step > s.n ? "✓" : s.n}
              </span>
              {s.label}
            </button>
          </div>
        ))}
      </nav>

      {/* Step 1: Node selection */}
      {step === 1 && (
        <section>
          <h2 className="mb-1 text-base font-semibold text-text">Select graph nodes</h2>
          <p className="mb-4 text-xs text-muted">
            Your clone will run only these nodes in the order shown. All nodes are server-validated
            against the vetted allowlist.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {allNodes.map((nodeName) => (
              <NodeToggleCard
                key={nodeName}
                nodeName={nodeName}
                selected={selectedNodes.includes(nodeName)}
                onToggle={toggleNode}
              />
            ))}
          </div>
          {allNodes.length === 0 && (
            <p className="text-xs text-muted-2">Loading nodes…</p>
          )}
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => setStep(2)}
              disabled={selectedNodes.length === 0}
              className={cn(
                "rounded-lg px-5 py-2 text-sm font-semibold transition",
                selectedNodes.length > 0
                  ? "bg-accent-bright text-bg hover:bg-accent"
                  : "cursor-not-allowed bg-surface text-muted",
              )}
            >
              Next: Params
            </button>
          </div>
        </section>
      )}

      {/* Step 2: Params */}
      {step === 2 && (
        <section>
          <h2 className="mb-1 text-base font-semibold text-text">Set parameters</h2>
          <p className="mb-4 text-xs text-muted">
            Configure which markets to watch, minimum edge threshold, and run cooldown.
          </p>
          <div className="space-y-5">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-text">
                Markets (comma-separated slugs)
              </span>
              <input
                type="text"
                value={markets}
                onChange={(e) => setMarkets(e.target.value)}
                placeholder="nba-2025-01-15-lal-bos, btc-2026-01-01"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text placeholder:text-muted-2 focus:border-accent focus:outline-none"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-medium text-text">
                Edge threshold: {edgeThreshold}%
              </span>
              <input
                type="range"
                min={0}
                max={50}
                step={1}
                value={edgeThreshold}
                onChange={(e) => setEdgeThreshold(Number(e.target.value))}
                className="w-full accent-accent"
              />
              <div className="mt-0.5 flex justify-between text-[11px] text-muted-2">
                <span>0%</span>
                <span>50%</span>
              </div>
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-medium text-text">
                Cooldown: {cooldown >= 1440 ? `${(cooldown / 1440).toFixed(1)}d` : `${cooldown}m`}
              </span>
              <input
                type="range"
                min={60}
                max={10080}
                step={60}
                value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
                className="w-full accent-accent"
              />
              <div className="mt-0.5 flex justify-between text-[11px] text-muted-2">
                <span>1h</span>
                <span>7d</span>
              </div>
            </label>
          </div>

          <div className="mt-6 flex justify-between">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-lg px-4 py-2 text-sm font-medium text-muted hover:text-text"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="rounded-lg bg-accent-bright px-5 py-2 text-sm font-semibold text-bg hover:bg-accent transition"
            >
              Next: Deploy
            </button>
          </div>
        </section>
      )}

      {/* Step 3: Name + Deploy */}
      {step === 3 && (
        <section>
          <h2 className="mb-1 text-base font-semibold text-text">Name and deploy</h2>
          <p className="mb-4 text-xs text-muted">
            Give your clone a name, then deploy it to paper mode.
          </p>

          {/* Summary card */}
          <div className="mb-5 rounded-xl border border-border bg-surface p-4 text-xs text-muted space-y-1">
            <div><span className="font-semibold text-text">Nodes:</span> {selectedNodes.join(" → ")}</div>
            <div><span className="font-semibold text-text">Markets:</span> {markets || "(none)"}</div>
            <div><span className="font-semibold text-text">Edge threshold:</span> {edgeThreshold}%</div>
            <div><span className="font-semibold text-text">Cooldown:</span> {cooldown}m</div>
            <div className="mt-2 rounded-lg bg-secondary/10 px-3 py-1.5 font-semibold text-secondary">
              Paper trading only — no real funds are used.
            </div>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-text">Clone name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. NBA News Tracker v1"
              maxLength={128}
              className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text placeholder:text-muted-2 focus:border-accent focus:outline-none"
            />
          </label>

          {error && (
            <p className="mt-3 rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>
          )}

          <div className="mt-6 flex justify-between">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="rounded-lg px-4 py-2 text-sm font-medium text-muted hover:text-text"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleDeploy}
              disabled={submitting || !name.trim()}
              className={cn(
                "rounded-lg px-5 py-2 text-sm font-semibold transition",
                !submitting && name.trim()
                  ? "bg-primary text-bg hover:bg-primary/90"
                  : "cursor-not-allowed bg-surface text-muted",
              )}
            >
              {submitting ? "Deploying…" : "Deploy (paper)"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
