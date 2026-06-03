type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type AdminAgentRunSummary = {
  run_id: string;
  market_id: string;
  market_slug: string;
  market_title: string;
  status: string;
  graph_version: string;
  approved: boolean;
  step_count: number;
  errors: string[];
  created_at: string;
};

export type AdminAgentRunStep = {
  step_name: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
};

export type AdminAgentRunDetail = {
  run_id: string;
  market_id: string;
  market_slug: string;
  market_title: string;
  status: string;
  graph_version: string;
  approved: boolean;
  predicted_prob: number;
  confidence: number;
  reasoning: string;
  errors: string[];
  created_at: string;
  steps: AdminAgentRunStep[];
  disclaimer: string;
};

type FetchAdminAgentRunsInput = {
  fetcher?: Fetcher;
  viewerToken: string;
  limit?: number;
};

type FetchAdminAgentRunDetailInput = {
  fetcher?: Fetcher;
  viewerToken: string;
  runId: string;
};

export type FetchAdminAgentRunsResult =
  | {
      ok: true;
      disclaimer: string;
      runs: AdminAgentRunSummary[];
    }
  | {
      ok: false;
      message: string;
    };

export type FetchAdminAgentRunDetailResult =
  | {
      ok: true;
      run: AdminAgentRunDetail;
    }
  | {
      ok: false;
      message: string;
    };

export async function fetchAdminAgentRuns(
  input: FetchAdminAgentRunsInput,
): Promise<FetchAdminAgentRunsResult> {
  const viewerToken = input.viewerToken.trim();
  if (!viewerToken) {
    return missingToken();
  }

  const limit = Math.min(Math.max(input.limit ?? 20, 1), 100);
  const response = await fetchProofJson<{ disclaimer: string; runs: AdminAgentRunSummary[] }>(
    input.fetcher ?? fetch,
    `/api/proof/agents/runs?limit=${limit}`,
    viewerToken,
  );
  if (!response.ok) {
    return response;
  }
  return {
    ok: true,
    disclaimer: response.body.disclaimer,
    runs: response.body.runs,
  };
}

export async function fetchAdminAgentRunDetail(
  input: FetchAdminAgentRunDetailInput,
): Promise<FetchAdminAgentRunDetailResult> {
  const viewerToken = input.viewerToken.trim();
  if (!viewerToken) {
    return missingToken();
  }

  const response = await fetchProofJson<AdminAgentRunDetail>(
    input.fetcher ?? fetch,
    `/api/proof/agents/runs/${encodeURIComponent(input.runId)}`,
    viewerToken,
  );
  if (!response.ok) {
    return response;
  }
  return {
    ok: true,
    run: response.body,
  };
}

async function fetchProofJson<T>(
  fetcher: Fetcher,
  url: string,
  viewerToken: string,
): Promise<{ ok: true; body: T } | { ok: false; message: string }> {
  try {
    const response = await fetcher(url, {
      cache: "no-store",
      headers: {
        "x-alphaedge-admin-viewer-token": viewerToken,
      },
    });
    if (!response.ok) {
      return {
        ok: false,
        message: await errorMessage(response),
      };
    }
    return {
      ok: true,
      body: (await response.json()) as T,
    };
  } catch {
    return {
      ok: false,
      message: "Admin proof proxy unavailable.",
    };
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall through to generic HTTP status text.
  }
  return response.statusText || `HTTP ${response.status}`;
}

function missingToken() {
  return {
    ok: false,
    message: "Admin viewer token is required.",
  } as const;
}
