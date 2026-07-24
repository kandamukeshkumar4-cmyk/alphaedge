---
name: graph-design
description: >
  Design agent work as a GRAPH (nodes/edges/shared state), not a single loop.
  Auto-load before authoring any multi-agent plan, wave, or loop-vNN goal.
  Layers ON TOP of loop-design: each node's interior is still a designed loop.
  Sources: Steinberger/@rohit4verse graph-engineering shift (2026-07),
  0xCodez 14-step course, EXM7777 diamond/stop-rule/human-gate course.
---

# Graph design — draw the shape of the work before briefing any agent

A loop is a single-node graph with a self-edge. When the work is several jobs
that hand off, draw the graph FIRST: nodes (one bounded job each, one runner
each), edges (data dependencies ONLY), shared state (STATE files + commits).

## Rules (each fixes a named failure)

1. **Delete fake edges.** An edge exists only if the next node READS the prior
   node's output. "And then" is not an edge. Every fake edge deleted = free
   parallelism. Ask this for every sequential step in a plan.
2. **Node contract.** Bounded input, validated output shape, exactly one job,
   exclusive file charter (one writer per file — the collision rule). A node
   without a contract cannot be parallelized or verified.
3. **The diamond is the default topology.** Split → parallel workers → reduce
   (plain code/orchestrator, zero agent tokens) → synthesize. Barrier ONLY
   when a stage needs ALL prior results (dedupe, early-exit, cross-compare);
   otherwise pipeline items through independently.
4. **Verifier on the edge, not at the end.** An independent node (different
   model than the author) tries to KILL each result before it flows
   downstream. Distinct lenses per checker (correct? current? prod-safe?).
   Known-liar nodes (see routing matrix: Qwen) ALWAYS get this edge.
5. **Cycles must converge.** Any loop-back edge carries a max-rounds cap and
   dedupes against EVERYTHING seen (not just accepted results). K=2 dry
   rounds = stop.
6. **Model per node.** Cheap models on bounded/repetitive nodes, strong models
   on judgment nodes (synthesis, adjudication). Follow the routing matrix in
   .claude/LOOP_GUIDE.md.
7. **Human gate placement.** Route to the user exactly where a mistake is
   expensive to undo (publish/external/spend), not on every step. Everything
   else the orchestrator gates (review + gate.py + fingerprint deploy).
8. **Spend cap.** A graph is many loops; caps multiply. Every node brief keeps
   the token-budget law (retry caps, 3-strikes escalation, stop conditions).

## Authoring checklist (put in every wave/GOAL brief)
- [ ] Graph sketched: nodes, real edges only, fake edges deleted
- [ ] One runner + exclusive file charter per node
- [ ] Contracts: output shapes named on every real edge (contract-first lets
      dependent nodes start in parallel against the contract)
- [ ] Verifier edges placed (mandatory on Qwen output)
- [ ] Cycles capped + dedupe-vs-seen
- [ ] Model tier per node from routing matrix
- [ ] Parallel BACKEND nodes: assign distinct alembic migration parents in the
      briefs (or reserve migrations to ONE node) — two nodes branching the same
      down_revision = multiple-heads deploy failure (V86 incident)
- [ ] Orchestrator = reduce/merge/deploy; user = irreversible-only gate

## The canonical topology (Roan / RohOnChain graph-engineering, 2026-07)

Refs in repo: `docs/graph-engineering/` (swarm-hunts-alpha, multi-factor-alpha-graph,
graph-engineering-14-steps). Read them before authoring a research/alpha graph.
The progression is **prompt → loop → swarm → graph**; a graph is Stage 4: you
describe the coordination structure ONCE (nodes=agents, edges=data hand-offs)
and the harness knows when to parallel, wait, retry, escalate.

**Draw the diagram before writing any code.** State the nodes, which run in
parallel, where the sync barrier is, which run in sequence, what persists, and
the stop condition — on a napkin — before a single brief is written. If you
can't draw it, it's too complex.

**Canonical shape** (the workhorse for research/factor/scan graphs):
```
parallel factor/worker fan-out  →  SYNC barrier  →  sequential coordination
   (N specialist nodes,             (collect all,     (validator → auditor →
    one job each, cheap model)       dedupe/merge)      constructor → decomposer,
                                                         STRONG model)
   → persist state (+ rejection reasons) → stop-check → sleep → loop back
```
This is the diamond (fan-out → reduce → synthesize) with a rigor tail. Factor
nodes are the fan-out; the maker-checker coordination nodes are the sequential
tail. Adapt node names to the domain; keep the shape.

## The 5 failure modes (Roan) — treat as hard rules

1. **Never skip the validator.** An independent node re-runs statistical rigor
   (out-of-sample, bootstrap, significance) and KILLS weak findings. Without it
   every result is data-snooping in disguise.
2. **State persistence with rejection reasons.** Every rejected finding is
   logged with WHY, so no node ever re-pays to rediscover the same dead end.
   (Our encode-once law, promoted to graph state.)
3. **Maker-checker split across different agents AND models.** The node that
   produced a finding is the worst judge of it. Validation is a DIFFERENT node
   on a STRONGER model. (Our verifier-edge, made mandatory.)
4. **No one node does everything.** Specialization is the whole point; one node
   = one job. A node that generates AND engineers AND validates collapses.
5. **Stop condition checkable by something other than the agent's own claim.**
   "gate.py exit 0", "residual-alpha t-stat > 2.5 out-of-sample", "Brier beats
   the closing line" — never "the agent says it's done." A silent completion
   signal on bad results is the #1 killer.

**Model tiering (per node):** cheap/fast model on the high-volume specialist
fan-out; frontier model on the validation/decomposition reasoning tail. Route
per `.claude/LOOP_GUIDE.md`.

**No vendor runtime.** These docs pitch Slate; do NOT install it. Our
worktree + gate.py + STATE.md + routing table + Monitor already ARE the graph
runtime — nodes=runner-per-worktree, edges=frozen contracts + merges, sync=the
orchestrator reduce, persistence=commits+STATE, stop=gate/audit. Capture the
principle, skip the tool (same call as loop-design's Slate decline).
