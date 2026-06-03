const VIEWER_TOKEN_HEADER = "x-alphaedge-admin-viewer-token";

async function proxyAdminAgentRuns(request, options = {}) {
  return proxyAdminProof(request, "/admin/agents/runs", options);
}

async function proxyAdminAgentRun(request, options = {}) {
  const slug = request.params?.slug;
  if (!slug) {
    return json(400, { detail: "Market slug is required" });
  }
  return proxyAdminProof(
    request,
    `/admin/agents/run/${encodeURIComponent(slug)}`,
    { ...options, method: "POST" },
  );
}

async function proxyAdminAgentRunDetail(request, options = {}) {
  const runId = request.params?.runId;
  if (!runId) {
    return json(400, { detail: "Agent run id is required" });
  }
  return proxyAdminProof(
    request,
    `/admin/agents/runs/${encodeURIComponent(runId)}`,
    options,
  );
}

async function proxyAdminProof(request, backendPath, options) {
  const env = options.env || process.env;
  const expectedViewerToken = env.ADMIN_VIEWER_TOKEN;
  const viewerToken = getHeader(request, VIEWER_TOKEN_HEADER);
  if (!expectedViewerToken || viewerToken !== expectedViewerToken) {
    return json(401, { detail: "Invalid admin viewer token" });
  }

  const backendApiUrl = trimTrailingSlash(env.ALPHAEDGE_BACKEND_API_URL || "");
  const adminApiKey = env.ADMIN_API_KEY;
  if (!backendApiUrl || !adminApiKey) {
    return json(503, { detail: "Admin proof proxy not configured" });
  }

  const query = queryString(request.query);
  const fetchImpl = options.fetchImpl || fetch;
  const response = await fetchImpl(`${backendApiUrl}${backendPath}${query}`, {
    method: options.method || "GET",
    headers: {
      "X-Admin-API-Key": adminApiKey,
    },
  });
  return json(response.status, await readJson(response));
}

function getHeader(request, name) {
  const headers = request.headers;
  if (!headers) {
    return "";
  }
  if (typeof headers.get === "function") {
    return headers.get(name) || "";
  }
  const exact = headers[name];
  if (exact) {
    return exact;
  }
  const lowerName = name.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === lowerName) {
      return value;
    }
  }
  return "";
}

function queryString(query) {
  if (!query) {
    return "";
  }
  const params = new URLSearchParams(query);
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

function trimTrailingSlash(value) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return { detail: "Backend admin proof response was not JSON" };
  }
}

function json(status, jsonBody) {
  return { status, jsonBody };
}

module.exports = {
  proxyAdminAgentRun,
  proxyAdminAgentRunDetail,
  proxyAdminAgentRuns,
};
