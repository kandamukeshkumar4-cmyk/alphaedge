"use client";

/**
 * Loop V79 (A6/A8) — Canvas view per UI-DIRECTION: dotted 24px grid, compact
 * step-card nodes with status dots, animated mint dashed edges while running,
 * dagre left→right, minimap off, zoom controls bottom-right, larger Final
 * Results node (verdict + sparkline). Node click → Dashboard step expand.
 * Read-only paper research — no execution language.
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
  isChartPayload,
  stepSummaryText,
  type ResearchStep,
  type ScoreboardLens,
} from "@/lib/terminal-api";

type StepNodeData = {
  title: string;
  blurb: string;
  kind: ResearchStep["kind"];
  status: string;
  sequence: number;
  onSelect?: () => void;
};
type StepFlowNode = Node<StepNodeData, "step">;

type ResultsNodeData = {
  verdict: string | null;
  lensCount: number;
  spark: number[];
  done: boolean;
};
type ResultsFlowNode = Node<ResultsNodeData, "results">;

type TerminalFlowNode = StepFlowNode | ResultsFlowNode;

const STEP_W = 240;
const STEP_H = 86;
const RESULT_W = 280;
const RESULT_H = 148;

function statusDot(status: string): string {
  if (status === "running" || status === "pending") return "bg-primary animate-pulse";
  if (status === "empty") return "bg-muted-2";
  if (status === "failed" || status === "error") return "bg-secondary";
  return "bg-primary";
}

function StepNode({ data }: NodeProps<StepFlowNode>) {
  return (
    <div
      title="Open in Dashboard"
      className={cn(
        "h-full w-full cursor-pointer rounded-xl border border-border bg-surface px-3 py-2 text-left shadow-sm transition",
        "hover:border-primary/45 hover:bg-surface-2/40 active:scale-[0.99]",
        "focus-within:ring-2 focus-within:ring-primary/30",
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
        {data.kind} · {data.status}
      </span>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
    </div>
  );
}

function ResultsNode({ data }: NodeProps<ResultsFlowNode>) {
  const points = data.spark.length > 1 ? data.spark : [0.5, 0.5];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const polyline = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = 28 - ((v - min) / span) * 28;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div
      className={cn(
        "h-full w-full rounded-xl border bg-surface px-3.5 py-2.5 shadow-glow",
        data.done ? "border-primary/45" : "border-dashed border-border",
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-border" />
      <p className="font-mono text-[9px] font-black uppercase tracking-[0.14em] text-primary">
        Final results · paper only
      </p>
      <p className="mt-1 text-[13px] font-black tracking-tight text-text">
        {data.verdict ?? (data.done ? "Complete" : "Awaiting run")}
      </p>
      <p className="mt-0.5 text-[10px] text-muted">
        {data.lensCount > 0 ? `${data.lensCount} confluence lenses` : "Scoreboard pending"}
      </p>
      <svg
        viewBox="0 0 100 28"
        preserveAspectRatio="none"
        className="mt-1.5 h-7 w-full text-primary"
        aria-hidden="true"
      >
        <polyline
          points={polyline}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

const nodeTypes = { step: StepNode, results: ResultsNode };

function layout(nodes: TerminalFlowNode[], edges: Edge[]): TerminalFlowNode[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 26, ranksep: 72, marginx: 8, marginy: 8 });
  for (const node of nodes) {
    g.setNode(node.id, {
      width: node.type === "results" ? RESULT_W : STEP_W,
      height: node.type === "results" ? RESULT_H : STEP_H,
    });
  }
  for (const edge of edges) g.setEdge(edge.source, edge.target);
  dagre.layout(g);
  return nodes.map((node) => {
    const pos = g.node(node.id);
    const w = node.type === "results" ? RESULT_W : STEP_W;
    const h = node.type === "results" ? RESULT_H : STEP_H;
    return { ...node, position: { x: pos.x - w / 2, y: pos.y - h / 2 } };
  });
}

export function TerminalCanvas({
  steps,
  scoreboard,
  verdict,
  running,
  onSelectStep,
}: {
  steps: ResearchStep[];
  scoreboard: ScoreboardLens[];
  verdict: string | null;
  running: boolean;
  /** Click a step node → open that step in the Dashboard tab. */
  onSelectStep?: (stepId: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const sorted = [...steps].sort((a, b) => a.sequence - b.sequence);
    const sparkStep = sorted.find((s) => s.kind === "chart" && isChartPayload(s.payload));
    const spark =
      sparkStep && isChartPayload(sparkStep.payload)
        ? sparkStep.payload.points.slice(-24).map((p) => p.v)
        : [];

    const stepNodes: TerminalFlowNode[] = sorted.map((step) => ({
      id: `step-${step.id}`,
      type: "step" as const,
      position: { x: 0, y: 0 },
      width: STEP_W,
      height: STEP_H,
      data: {
        title: step.title,
        blurb: stepSummaryText(step),
        kind: step.kind,
        status: step.status,
        sequence: step.sequence,
        onSelect: onSelectStep ? () => onSelectStep(step.id) : undefined,
      },
    }));

    const resultsNode: TerminalFlowNode = {
      id: "results",
      type: "results" as const,
      position: { x: 0, y: 0 },
      width: RESULT_W,
      height: RESULT_H,
      data: {
        verdict,
        lensCount: scoreboard.length,
        spark,
        done: scoreboard.length > 0 || verdict !== null,
      },
    };

    const flowEdges: Edge[] = sorted.map((step) => ({
      id: `e-${step.id}-results`,
      source: `step-${step.id}`,
      target: "results",
      animated: running,
      style: {
        stroke: "var(--color-primary, #00E8B0)",
        strokeWidth: 1.4,
        opacity: running ? 0.85 : 0.55,
        strokeDasharray: running ? "6 4" : undefined,
      },
    }));

    const allNodes = [...stepNodes, resultsNode];
    return { nodes: layout(allNodes, flowEdges), edges: flowEdges };
  }, [steps, scoreboard, verdict, running, onSelectStep]);

  return (
    <div
      data-testid="terminal-canvas"
      className="h-[520px] w-full overflow-hidden rounded-xl border border-border bg-bg/60"
    >
      {steps.length === 0 ? (
        <div className="grid h-full place-items-center px-4 text-center">
          <p className="text-sm text-muted">
            Resume a session or run a question — the step graph appears here.
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
          onNodeClick={(_, node) => {
            if (node.type !== "step") return;
            const data = node.data as StepNodeData;
            data.onSelect?.();
          }}
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
