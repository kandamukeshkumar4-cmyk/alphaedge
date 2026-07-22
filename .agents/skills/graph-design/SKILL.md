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
