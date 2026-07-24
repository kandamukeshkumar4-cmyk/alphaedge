import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

export type LibraryKind = "brief" | "report" | "scanner" | "alpha" | "workflow";
export type LibrarySource = "briefs" | "memories" | "scanners" | "alpha" | "skills";
export type LibrarySourceStatus = "ready" | "empty" | "error";

export type LibraryItem = {
  id: string;
  kind: LibraryKind;
  source: LibrarySource;
  label: string;
  title: string;
  summary: string;
  timestamp: string | null;
  href: string;
  status: string | null;
  details: string[];
};

export type LibraryResult = {
  items: LibraryItem[];
  sources: Record<LibrarySource, LibrarySourceStatus>;
  failedSources: LibrarySource[];
};

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

type LoadOptions = {
  apiBase?: string;
  fetcher?: Fetcher;
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function string(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function plainText(value: unknown, fallback: string): string {
  const text = string(value);
  if (!text) return fallback;
  return (
    text
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/[#*_>`~[\]()]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 260) || fallback
  );
}

function normalizeBriefs(value: unknown): LibraryItem[] {
  const body = record(value);
  if (!Array.isArray(body.items)) throw new Error("Malformed briefs response.");
  return body.items.flatMap((raw) => {
    const brief = record(raw);
    const id = string(brief.id);
    const title = string(brief.headline);
    if (!id || !title) return [];
    const citations = list(brief.citations).length;
    const market = string(brief.market_slug);
    const kind = string(brief.kind);
    const claim = record(brief.claim);
    const claimStatus = string(claim.status);
    return [
      {
        id: `brief:${id}`,
        kind: "brief" as const,
        source: "briefs" as const,
        label: kind === "digest" ? "Daily digest" : "Analyst brief",
        title,
        summary: plainText(brief.body_markdown, "Brief body is not available."),
        timestamp: string(brief.created_at),
        href: `/research/brief?id=${encodeURIComponent(id)}`,
        status: claimStatus,
        details: [
          ...(market ? [market] : []),
          `${citations.toLocaleString()} citation${citations === 1 ? "" : "s"}`,
        ],
      },
    ];
  });
}

function normalizeMemories(value: unknown): LibraryItem[] {
  const body = record(value);
  if (!Array.isArray(body.items)) throw new Error("Malformed memories response.");
  return body.items.flatMap((raw) => {
    const memory = record(raw);
    const id = string(memory.id);
    const title = string(memory.question);
    const market = string(memory.market_slug);
    if (!id || !title || !market) return [];
    const brier = number(memory.brier);
    const outcome = string(memory.outcome);
    const category = string(memory.category);
    return [
      {
        id: `memory:${id}`,
        kind: "report" as const,
        source: "memories" as const,
        label: "Resolved report",
        title,
        summary: plainText(memory.rationale_summary, "No rationale was recorded."),
        timestamp: string(memory.created_at),
        href: `/markets/view?slug=${encodeURIComponent(market)}`,
        status: outcome ? `Resolved ${outcome}` : null,
        details: [
          ...(category ? [category] : []),
          ...(brier === null ? [] : [`Brier ${brier.toFixed(3)}`]),
        ],
      },
    ];
  });
}

function scannerResultSummary(scanner: Record<string, unknown>): string {
  const latestRun = record(scanner.latest_run);
  const result = record(latestRun.result);
  const topPick = record(result.top_pick);
  const topPickTitle = string(topPick.title) ?? string(topPick.market_slug);
  if (topPickTitle) return `Latest scan surfaced ${topPickTitle}.`;
  return plainText(scanner.description, "Saved scanner with no result summary yet.");
}

function normalizeScanners(value: unknown): LibraryItem[] {
  if (!Array.isArray(value)) throw new Error("Malformed scanners response.");
  return value.flatMap((raw) => {
    const scanner = record(raw);
    const id = string(scanner.id);
    const title = string(scanner.name);
    if (!id || !title) return [];
    const latestRun = record(scanner.latest_run);
    const runStatus = string(latestRun.status);
    const scannerStatus = string(scanner.status);
    const spec = record(scanner.spec);
    const steps = list(spec.steps).length;
    return [
      {
        id: `scanner:${id}`,
        kind: "scanner" as const,
        source: "scanners" as const,
        label: latestRun.id ? "Scanner result" : "Saved scanner",
        title,
        summary: scannerResultSummary(scanner),
        timestamp:
          string(latestRun.finished_at) ??
          string(latestRun.started_at) ??
          string(scanner.updated_at),
        href: `/scanners/${encodeURIComponent(id)}`,
        status: runStatus ?? scannerStatus,
        details: [
          `${steps.toLocaleString()} step${steps === 1 ? "" : "s"}`,
          scanner.is_public === true ? "Public" : "Private",
        ],
      },
    ];
  });
}

function alphaRuns(value: unknown): unknown[] {
  const body = record(value);
  if (Array.isArray(body.runs)) return body.runs;
  if (Array.isArray(body.items)) return body.items;
  throw new Error("Malformed alpha-runs response.");
}

function normalizeAlpha(value: unknown): LibraryItem[] {
  return alphaRuns(value).flatMap((raw, index) => {
    const run = record(raw);
    const id = string(run.id) ?? `dated:${string(run.run_date) ?? index}`;
    const runDate = string(run.run_date);
    const startedAt = string(run.started_at);
    const result = record(run.result);
    const signal = record(result.signal);
    const decomposition = record(result.decomposition);
    const status = string(run.status);
    const signalLabel = string(signal.label);
    const residualAlpha =
      number(run.residual_alpha) ?? number(decomposition.residual_alpha);
    const tStat =
      number(run.t_stat) ??
      number(decomposition.residual_alpha_t_stat) ??
      number(signal.residual_alpha_t_stat);
    const rejectionCount = list(run.rejection_reasons).length;
    const dateLabel = runDate ?? startedAt;
    return [
      {
        id: `alpha:${id}`,
        kind: "alpha" as const,
        source: "alpha" as const,
        label: "Alpha run",
        title: dateLabel ? `Daily alpha · ${dateLabel.slice(0, 10)}` : "Daily alpha run",
        summary:
          signalLabel ??
          (status
            ? `Validation completed with status “${status.replaceAll("_", " ")}”.`
            : "Alpha validation run persisted without a summary."),
        timestamp: startedAt ?? runDate,
        href: "/alpha",
        status,
        details: [
          ...(residualAlpha === null ? [] : [`Residual alpha ${residualAlpha.toFixed(4)}`]),
          ...(tStat === null ? [] : [`t-stat ${tStat.toFixed(2)}`]),
          `${rejectionCount.toLocaleString()} rejection${rejectionCount === 1 ? "" : "s"}`,
        ],
      },
    ];
  });
}

function normalizeSkills(value: unknown): LibraryItem[] {
  if (!Array.isArray(value)) throw new Error("Malformed skills response.");
  return value.flatMap((raw) => {
    const skill = record(raw);
    const id = string(skill.id);
    const title = string(skill.name);
    if (!id || !title) return [];
    const steps = list(skill.template).length;
    const runCount = number(skill.run_count);
    return [
      {
        id: `skill:${id}`,
        kind: "workflow" as const,
        source: "skills" as const,
        label: "Saved workflow",
        title,
        summary: plainText(skill.description, "Saved research workflow."),
        timestamp: string(skill.updated_at) ?? string(skill.created_at),
        href: "/skills",
        status: skill.is_public === false ? "Private" : "Public",
        details: [
          `${steps.toLocaleString()} step${steps === 1 ? "" : "s"}`,
          ...(runCount === null ? [] : [`${runCount.toLocaleString()} runs`]),
        ],
      },
    ];
  });
}

async function requestJson(
  base: string,
  path: string,
  token: string | null,
  fetcher: Fetcher,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetcher(apiUrl(path, base), {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new Error("Network request failed.");
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  try {
    return await response.json();
  } catch {
    throw new Error("Invalid JSON response.");
  }
}

export async function loadLibrary(
  token: string | null = null,
  input?: LoadOptions,
): Promise<LibraryResult> {
  const base = input?.apiBase ?? (await ensureApiBase()) ?? API_BASE;
  if (!hasLiveApi(base)) throw new Error("The live research service is not configured.");
  const fetcher = input?.fetcher ?? fetch;
  const requests: Array<{
    source: LibrarySource;
    promise: Promise<unknown>;
    normalize: (value: unknown) => LibraryItem[];
  }> = [
    {
      source: "briefs",
      promise: requestJson(base, "/api/v1/briefs?limit=100", null, fetcher),
      normalize: normalizeBriefs,
    },
    {
      source: "memories",
      promise: requestJson(base, "/api/v1/memories?limit=100", null, fetcher),
      normalize: normalizeMemories,
    },
    {
      source: "scanners",
      promise: requestJson(base, "/api/v1/scanners/", token, fetcher),
      normalize: normalizeScanners,
    },
    {
      source: "alpha",
      promise: requestJson(base, "/api/v1/alpha/runs?limit=100", null, fetcher),
      normalize: normalizeAlpha,
    },
    {
      source: "skills",
      promise: requestJson(base, "/api/v1/skills/", null, fetcher),
      normalize: normalizeSkills,
    },
  ];
  const settled = await Promise.allSettled(requests.map((request) => request.promise));
  const items: LibraryItem[] = [];
  const sources: Record<LibrarySource, LibrarySourceStatus> = {
    briefs: "error",
    memories: "error",
    scanners: "error",
    alpha: "error",
    skills: "error",
  };
  const failedSources: LibrarySource[] = [];

  settled.forEach((result, index) => {
    const request = requests[index];
    if (result.status === "rejected") {
      failedSources.push(request.source);
      return;
    }
    try {
      const normalized = request.normalize(result.value);
      items.push(...normalized);
      sources[request.source] = normalized.length > 0 ? "ready" : "empty";
    } catch {
      failedSources.push(request.source);
    }
  });

  return { items, sources, failedSources };
}
