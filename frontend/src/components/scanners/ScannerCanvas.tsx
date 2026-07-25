"use client";

/**
 * Loop V84 (U3) — scanner spec pipeline canvas. Node/edge styling reuses the
 * Loop V79 TerminalCanvas contract exactly: dotted 24px grid, compact
 * step-node cards with status dots, dagre left→right, animated mint dashed
 * edges while a run is in flight. Nodes are the spec steps, chained in
 * compiler order; per-node status derives from the latest run checkpoint.
 */

import dagre from "dagre";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useMemo } from "react";

import "@xyflow/react/dist/style.css";

import { cn } from "@/lib/cn";
import {
  stepLabel,
  type ScannerRun,
  type ScannerStep,
} from "@/lib/scanners-api";

type StepNodeData = {
  title: string;
  blurb: string;
  status: string;
  sequence: number;
};
type StepFlowNode = Node<StepNodeData, "step">;

const STEP_W = 240;
const STEP_H = 86;

/** Loop V86 (X2) dot contract — completed=mint, running=mint pulse,
 *  pending=gray, failed=blue. Never red (blue carries failure). */
function statusDot(status: string): string {
  if (status === "running") return "bg-primary animate-pulse";
  if (status === "pending" || status === "empty" || status === "waiting") return "bg-muted-2";
  if (status === "failed" || status === "error") return "bg-secondary";
  return "bg-primary"; // completed / done
}

function StepNode({ data }: NodeProps<StepFlowNode>) {
  return (
    <div
      data-testid="scanner-step-node"
      className={cn(
        "h-full w-full rounded-xl border border-border bg-surface px-3 py-2 text-left shadow-sm transition",
        "hover:border-primary/45 hover:bg-surface-2/40",
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
      <span className="flex items-center gap-2">
        <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/15 font-mono text-[10px] font-black text-primary">
          {String(data.sequence).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1 truncate text-[12px] font-bold text-text">
          {data.title}
        </span>
        <span
          aria-label={`status ${data.status}`}
          className={cn("h-1.5 w-1.5 shrink-0 rounded-full", statusDot(data.status))}
        />
      </span>
      <span className="mt-1.5 block truncate text-[11px] text-muted">{data.blurb}</span>
      <span className="mt-1 block font-mono text-[9px] uppercase tracking-wide text-muted-2">
        pipeline step · {data.status}
      </span>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
    </div>
  );
}

const nodeTypes = { step: StepNode };

function layout(nodes: StepFlowNode[], edges: Edge[]): StepFlowNode[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 26, ranksep: 72, marginx: 8, marginy: 8 });
  for (const node of nodes) g.setNode(node.id, { width: STEP_W, height: STEP_H });
  for (const edge of edges) g.setEdge(edge.source, edge.target);
  dagre.layout(g);
  return nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - STEP_W / 2, y: pos.y - STEP_H / 2 } };
  });
}

/** Per-node status from the latest run: checkpoint marks completed nodes. */
function nodeStatus(index: number, run: ScannerRun | null): string {
  if (!run) return "waiting";
  const checkpointNode = run.checkpoint?.node ?? -1;
  if (run.status === "completed") return "done";
  if (run.status === "empty") return "empty";
  if (run.status === "failed") {
    if (index <= checkpointNode) return "done";
    if (index === checkpointNode + 1) return "failed";
    return "waiting";
  }
  // running
  if (index <= checkpointNode) return "done";
  if (index === checkpointNode + 1) return "running";
  return "waiting";
}

function stepBlurb(step: ScannerStep): string {
  switch (step.type) {
    case "WHALE_FLOW":
      return "Large-flow pressure per market";
    case "PRICE_TREND":
      return `${step.window_days ?? 7}-day mid drift direction`;
    case "NEWS_SENTIMENT":
      return "Headline tone + sentiment trend";
    case "MODEL_EDGE":
      return "Model prob vs market mid (paper)";
    case "DIRECTION_ALIGNMENT":
      return "Keep only agreeing directions";
    case "CROSS_VENUE_DIVERGENCE":
      return "Price gap between Polymarket and Kalshi for the same event.";
    case "CLOSING_SOON":
      return "Markets locking within the next N hours.";
  }
}

export function ScannerCanvas({
  steps,
  latestRun,
}: {
  steps: ScannerStep[];
  latestRun: ScannerRun | null;
}) {
  const { nodes, edges } = useMemo(() => {
    const running = latestRun?.status === "running";
    const stepNodes: StepFlowNode[] = steps.map((step, i) => ({
      id: `step-${i}`,
      type: "step" as const,
      position: { x: 0, y: 0 },
      width: STEP_W,
      height: STEP_H,
      data: {
        title: stepLabel(step),
        blurb: stepBlurb(step),
        status: nodeStatus(i, latestRun),
        sequence: i + 1,
      },
    }));

    const flowEdges: Edge[] = steps.slice(0, -1).map((_, i) => ({
      id: `e-${i}-${i + 1}`,
      source: `step-${i}`,
      target: `step-${i + 1}`,
      animated: running,
      style: {
        stroke: "var(--color-primary, #00E8B0)",
        strokeWidth: 1.4,
        opacity: running ? 0.85 : 0.55,
        strokeDasharray: running ? "6 4" : undefined,
      },
    }));

    return { nodes: layout(stepNodes, flowEdges), edges: flowEdges };
  }, [steps, latestRun]);

  return (
    <div
      data-testid="scanner-canvas"
      className="h-[520px] w-full overflow-hidden rounded-xl border border-border bg-bg/60"
    >
      {steps.length === 0 ? (
        <div className="grid h-full place-items-center px-4 text-center">
          <p className="text-sm text-muted">
            This spec has no steps — compile a new description to build the pipeline.
          </p>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.18, maxZoom: 1.1 }}
          minZoom={0.4}
          maxZoom={1.6}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={24}
            size={1}
            color="rgba(148, 163, 184, 0.22)"
          />
          <Controls position="bottom-right" showInteractive={false} />
        </ReactFlow>
      )}
    </div>
  );
}
