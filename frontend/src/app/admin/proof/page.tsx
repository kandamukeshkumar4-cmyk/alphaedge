"use client";

import { FormEvent, useMemo, useState } from "react";

import {
  fetchAdminHistoricalClosingSnapshotCaptures,
  fetchAdminMarketSnapshotCaptures,
  fetchAdminAgentRunDetail,
  fetchAdminAgentRuns,
  runAdminHistoricalClosingSnapshotCapture,
  runAdminAgentProof,
  type AdminAgentRunDetail,
  type AdminAgentRunSummary,
  type AdminMarketSnapshotCaptureRun,
} from "@/lib/admin-proof-api";

const RUN_LIMIT = 10;
const CAPTURE_LIMIT = 5;
const DEFAULT_MARKET_SLUG = "nba-2025-01-15-lal-bos";

export default function AdminPage() {
  const [viewerToken, setViewerToken] = useState("");
  const [marketSlug, setMarketSlug] = useState(DEFAULT_MARKET_SLUG);
  const [runs, setRuns] = useState<AdminAgentRunSummary[]>([]);
  const [captureRuns, setCaptureRuns] = useState<AdminMarketSnapshotCaptureRun[]>([]);
  const [historicalCaptureRuns, setHistoricalCaptureRuns] = useState<
    AdminMarketSnapshotCaptureRun[]
  >([]);
  const [selectedRun, setSelectedRun] = useState<AdminAgentRunDetail | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [disclaimer, setDisclaimer] = useState("");
  const [message, setMessage] = useState("");
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [isLoadingCaptures, setIsLoadingCaptures] = useState(false);
  const [isLoadingHistoricalCaptures, setIsLoadingHistoricalCaptures] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isRunningProof, setIsRunningProof] = useState(false);
  const [isRunningHistoricalCapture, setIsRunningHistoricalCapture] = useState(false);

  const approvedCount = useMemo(
    () => runs.filter((run) => run.approved).length,
    [runs],
  );
  const latestCapture = captureRuns[0] ?? null;
  const latestHistoricalCapture = historicalCaptureRuns[0] ?? null;

  async function handleLoadRuns(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoadingRuns(true);
    setMessage("");
    setSelectedRun(null);
    setSelectedRunId(null);

    const result = await fetchAdminAgentRuns({
      viewerToken,
      limit: RUN_LIMIT,
    });

    setIsLoadingRuns(false);
    if (!result.ok) {
      setRuns([]);
      setDisclaimer("");
      setMessage(result.message);
      return;
    }

    setRuns(result.runs);
    setDisclaimer(result.disclaimer);
    setMessage(result.runs.length ? "" : "No proof runs found.");
    await loadCaptureRuns();
    await loadHistoricalCaptureRuns();
  }

  async function loadCaptureRuns() {
    setIsLoadingCaptures(true);
    setMessage("");

    const result = await fetchAdminMarketSnapshotCaptures({
      viewerToken,
      limit: CAPTURE_LIMIT,
    });

    setIsLoadingCaptures(false);
    if (!result.ok) {
      setCaptureRuns([]);
      setMessage(result.message);
      return;
    }

    setCaptureRuns(result.runs);
    setMessage(result.runs.length ? "" : "No connector captures found.");
  }

  async function handleLoadCaptures() {
    await loadCaptureRuns();
  }

  async function loadHistoricalCaptureRuns() {
    setIsLoadingHistoricalCaptures(true);
    setMessage("");

    const result = await fetchAdminHistoricalClosingSnapshotCaptures({
      viewerToken,
      limit: CAPTURE_LIMIT,
    });

    setIsLoadingHistoricalCaptures(false);
    if (!result.ok) {
      setHistoricalCaptureRuns([]);
      setMessage(result.message);
      return;
    }

    setHistoricalCaptureRuns(result.runs);
    setMessage(result.runs.length ? "" : "No historical closing backfills found.");
  }

  async function handleLoadHistoricalCaptures() {
    await loadHistoricalCaptureRuns();
  }

  async function handleRunHistoricalCapture() {
    setIsRunningHistoricalCapture(true);
    setMessage("");

    const result = await runAdminHistoricalClosingSnapshotCapture({
      viewerToken,
    });

    setIsRunningHistoricalCapture(false);
    if (!result.ok) {
      setMessage(result.message);
      return;
    }

    setHistoricalCaptureRuns((currentRuns) => upsertCaptureRun(currentRuns, result.run));
    setMessage("Historical closing backfill recorded.");
  }

  async function handleSelectRun(runId: string) {
    setIsLoadingDetail(true);
    setSelectedRunId(runId);
    setMessage("");

    const result = await fetchAdminAgentRunDetail({
      viewerToken,
      runId,
    });

    setIsLoadingDetail(false);
    if (!result.ok) {
      setSelectedRun(null);
      setMessage(result.message);
      return;
    }

    setSelectedRun(result.run);
  }

  async function handleRunProof(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsRunningProof(true);
    setMessage("");

    const result = await runAdminAgentProof({
      viewerToken,
      marketSlug,
    });

    setIsRunningProof(false);
    if (!result.ok) {
      setMessage(result.message);
      return;
    }

    setSelectedRun(result.run);
    setSelectedRunId(result.run.run_id);
    setDisclaimer(result.run.disclaimer);
    setRuns((currentRuns) => upsertRunSummary(currentRuns, result.run));
    setMessage("Agent proof recorded.");
  }

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
            Admin
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-text">
            Agent Run Proof
          </h1>
        </div>
        <form
          className="flex w-full flex-col gap-2 sm:max-w-xl sm:flex-row"
          onSubmit={handleLoadRuns}
        >
          <label className="sr-only" htmlFor="viewer-token">
            Viewer token
          </label>
          <input
            id="viewer-token"
            className="min-h-11 flex-1 rounded-xl border border-border bg-surface px-3 text-sm text-text outline-none transition focus:border-accent"
            type="password"
            autoComplete="off"
            placeholder="Viewer token"
            value={viewerToken}
            onChange={(event) => setViewerToken(event.target.value)}
          />
          <button
            className="min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-bg transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isLoadingRuns}
            type="submit"
          >
            {isLoadingRuns ? "Loading" : "Load Runs"}
          </button>
        </form>
      </header>

      {message ? (
        <div className="rounded border border-border bg-surface px-4 py-3 text-sm text-muted">
          {message}
        </div>
      ) : null}

      <form
        className="flex flex-col gap-2 rounded border border-border bg-surface p-4 sm:flex-row"
        onSubmit={handleRunProof}
      >
        <label className="sr-only" htmlFor="market-slug">
          Market slug
        </label>
        <input
          id="market-slug"
          className="min-h-11 flex-1 rounded border border-border bg-bg px-3 font-mono text-sm text-text outline-none transition focus:border-primary"
          value={marketSlug}
          onChange={(event) => setMarketSlug(event.target.value)}
        />
        <button
          className="min-h-11 rounded border border-primary/45 px-4 text-sm font-semibold text-primary transition hover:border-primary hover:text-accent disabled:cursor-not-allowed disabled:border-border disabled:text-muted-2"
          disabled={isRunningProof}
          type="submit"
        >
          {isRunningProof ? "Running" : "Run Proof"}
        </button>
      </form>

      <section className="grid gap-4 md:grid-cols-4">
        <Metric label="Runs" value={runs.length.toString()} />
        <Metric label="Approved" value={approvedCount.toString()} />
        <Metric label="Blocked" value={(runs.length - approvedCount).toString()} />
        <Metric label="Capture Failures" value={(latestCapture?.failed ?? 0).toString()} />
      </section>

      <section className="rounded border border-border bg-surface">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">Connector Capture Health</h2>
            <p className="mt-1 text-xs text-muted-2">
              Latest scheduled odds, Polymarket, and Kalshi snapshot capture runs.
            </p>
          </div>
          <button
            className="min-h-10 rounded border border-border-light px-3 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:text-muted-2"
            disabled={isLoadingCaptures}
            onClick={() => void handleLoadCaptures()}
            type="button"
          >
            {isLoadingCaptures ? "Refreshing" : "Refresh Captures"}
          </button>
        </div>

        {latestCapture ? (
          <div className="space-y-4 p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <CaptureStat label="Status" value={latestCapture.status} />
              <CaptureStat
                label="Inserted"
                value={`${latestCapture.ingested}/${latestCapture.fetched}`}
              />
              <CaptureStat label="Skipped" value={latestCapture.skipped.toString()} />
              <CaptureStat label="Captured" value={formatOptionalDate(latestCapture.captured_at)} />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Started</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Fetched</th>
                    <th className="px-3 py-2 font-semibold">Inserted</th>
                    <th className="px-3 py-2 font-semibold">Failed</th>
                    <th className="px-3 py-2 font-semibold">Failure Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {captureRuns.map((run) => (
                    <tr key={run.run_id} className="align-top">
                      <td className="px-3 py-3 text-muted">{formatDate(run.started_at)}</td>
                      <td className="px-3 py-3">
                        <CaptureStatusBadge status={run.status} failed={run.failed} />
                      </td>
                      <td className="px-3 py-3 tabular text-muted">{run.fetched}</td>
                      <td className="px-3 py-3 tabular text-muted">{run.ingested}</td>
                      <td className="px-3 py-3 tabular text-muted">{run.failed}</td>
                      <td className="px-3 py-3 text-muted">
                        {run.failures.length ? (
                          <ul className="space-y-1">
                            {run.failures.map((failure) => (
                              <li
                                key={`${run.run_id}-${failure.source}-${failure.target}`}
                                className="break-words"
                              >
                                <span className="font-mono text-xs text-danger">
                                  {failure.source}
                                </span>{" "}
                                <span className="font-mono text-xs text-muted-2">
                                  {failure.target}
                                </span>
                                <span className="block text-xs">{failure.error}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "No failures"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-4 text-sm text-muted">No connector captures loaded.</div>
        )}
      </section>

      <section className="rounded border border-border bg-surface">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">Historical Closing Backfill</h2>
            <p className="mt-1 text-xs text-muted-2">
              Manual closing-line snapshot pulls used to grow Phase 3 CLV evidence.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              className="min-h-10 rounded border border-primary/45 px-3 text-xs font-semibold text-primary transition hover:border-primary hover:text-accent disabled:cursor-not-allowed disabled:border-border disabled:text-muted-2"
              disabled={isRunningHistoricalCapture}
              onClick={() => void handleRunHistoricalCapture()}
              type="button"
            >
              {isRunningHistoricalCapture ? "Running" : "Run Backfill"}
            </button>
            <button
              className="min-h-10 rounded border border-border-light px-3 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:text-muted-2"
              disabled={isLoadingHistoricalCaptures}
              onClick={() => void handleLoadHistoricalCaptures()}
              type="button"
            >
              {isLoadingHistoricalCaptures ? "Refreshing" : "Refresh Backfills"}
            </button>
          </div>
        </div>

        {latestHistoricalCapture ? (
          <div className="space-y-4 p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <CaptureStat label="Status" value={latestHistoricalCapture.status} />
              <CaptureStat
                label="Inserted"
                value={`${latestHistoricalCapture.ingested}/${latestHistoricalCapture.fetched}`}
              />
              <CaptureStat
                label="Skipped"
                value={latestHistoricalCapture.skipped.toString()}
              />
              <CaptureStat
                label="Failed"
                value={latestHistoricalCapture.failed.toString()}
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Started</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Fetched</th>
                    <th className="px-3 py-2 font-semibold">Inserted</th>
                    <th className="px-3 py-2 font-semibold">Skipped</th>
                    <th className="px-3 py-2 font-semibold">Failure Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {historicalCaptureRuns.map((run) => (
                    <tr key={run.run_id} className="align-top">
                      <td className="px-3 py-3 text-muted">{formatDate(run.started_at)}</td>
                      <td className="px-3 py-3">
                        <CaptureStatusBadge status={run.status} failed={run.failed} />
                      </td>
                      <td className="px-3 py-3 tabular text-muted">{run.fetched}</td>
                      <td className="px-3 py-3 tabular text-muted">{run.ingested}</td>
                      <td className="px-3 py-3 tabular text-muted">{run.skipped}</td>
                      <td className="px-3 py-3 text-muted">
                        {run.failures.length ? (
                          <ul className="space-y-1">
                            {run.failures.map((failure) => (
                              <li
                                key={`${run.run_id}-${failure.source}-${failure.target}`}
                                className="break-words"
                              >
                                <span className="font-mono text-xs text-danger">
                                  {failure.source}
                                </span>{" "}
                                <span className="font-mono text-xs text-muted-2">
                                  {failure.target}
                                </span>
                                <span className="block text-xs">{failure.error}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "No failures"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-4 text-sm text-muted">
            No historical closing backfills loaded.
          </div>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="overflow-hidden rounded border border-border bg-surface">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-text">Recent Runs</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2">
                <tr>
                  <th className="px-4 py-3 font-semibold">Market</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Graph</th>
                  <th className="px-4 py-3 font-semibold">Steps</th>
                  <th className="px-4 py-3 font-semibold">Created</th>
                  <th className="px-4 py-3 font-semibold">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {runs.map((run) => (
                  <tr key={run.run_id} className="align-top">
                    <td className="px-4 py-3">
                      <div className="font-medium text-text">{run.market_title}</div>
                      <div className="mt-1 font-mono text-xs text-muted-2">
                        {run.market_slug}
                      </div>
                      {run.errors.length ? (
                        <div className="mt-2 text-xs text-danger">{run.errors.join("; ")}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge approved={run.approved} status={run.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">
                      {run.graph_version}
                    </td>
                    <td className="px-4 py-3 tabular text-muted">{run.step_count}</td>
                    <td className="px-4 py-3 text-muted">{formatDate(run.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        className="rounded border border-border-light px-3 py-2 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:text-muted-2"
                        disabled={isLoadingDetail && selectedRunId === run.run_id}
                        onClick={() => void handleSelectRun(run.run_id)}
                        type="button"
                      >
                        {isLoadingDetail && selectedRunId === run.run_id ? "Loading" : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
                {!runs.length ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted" colSpan={6}>
                      No runs loaded.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="rounded border border-border bg-surface">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-text">Run Detail</h2>
          </div>
          {selectedRun ? (
            <div className="space-y-4 p-4">
              <div>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-text">{selectedRun.market_title}</h3>
                  <StatusBadge approved={selectedRun.approved} status={selectedRun.status} />
                </div>
                <p className="mt-1 break-all font-mono text-xs text-muted-2">
                  {selectedRun.run_id}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <DetailStat label="Probability" value={formatPercent(selectedRun.predicted_prob)} />
                <DetailStat label="Confidence" value={formatPercent(selectedRun.confidence)} />
              </div>

              {selectedRun.reasoning ? (
                <section>
                  <h4 className="text-xs font-semibold uppercase text-muted-2">Reasoning</h4>
                  <p className="mt-2 text-sm leading-6 text-muted">{selectedRun.reasoning}</p>
                </section>
              ) : null}

              {selectedRun.errors.length ? (
                <section>
                  <h4 className="text-xs font-semibold uppercase text-muted-2">Errors</h4>
                  <ul className="mt-2 space-y-2 text-sm text-danger">
                    {selectedRun.errors.map((error) => (
                      <li key={error}>{error}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section>
                <h4 className="text-xs font-semibold uppercase text-muted-2">Steps</h4>
                <ol className="mt-2 space-y-3">
                  {selectedRun.steps.map((step, index) => (
                    <li key={`${step.step_name}-${index}`} className="rounded bg-surface-2 p-3">
                      <div className="font-mono text-xs font-semibold text-primary">
                        {index + 1}. {step.step_name}
                      </div>
                      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-bg/65 p-2 font-mono text-xs leading-5 text-muted">
                        {JSON.stringify(step.output_data, null, 2)}
                      </pre>
                    </li>
                  ))}
                </ol>
              </section>

              {selectedRun.disclaimer ? (
                <p className="border-t border-border pt-3 text-xs leading-5 text-muted-2">
                  {selectedRun.disclaimer}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="p-4 text-sm text-muted">Select a run.</div>
          )}
        </aside>
      </section>

      {disclaimer ? <p className="text-xs leading-5 text-muted-2">{disclaimer}</p> : null}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-surface p-4">
      <div className="text-xs font-semibold uppercase text-muted-2">{label}</div>
      <div className="mt-2 tabular text-2xl font-semibold text-text">{value}</div>
    </div>
  );
}

function CaptureStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-surface-2 p-3">
      <div className="text-xs font-semibold uppercase text-muted-2">{label}</div>
      <div className="mt-2 break-words text-sm font-semibold text-text">{value}</div>
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-surface-2 p-3">
      <div className="text-xs font-semibold uppercase text-muted-2">{label}</div>
      <div className="mt-2 tabular text-lg font-semibold text-text">{value}</div>
    </div>
  );
}

function CaptureStatusBadge({ status, failed }: { status: string; failed: number }) {
  const classes =
    failed > 0 || status !== "success"
      ? "border-danger/45 bg-danger-dim text-danger"
      : "border-primary/45 bg-primary-dim text-primary";

  return (
    <span className={`inline-flex rounded border px-2 py-1 text-xs font-semibold ${classes}`}>
      {status}
    </span>
  );
}

function StatusBadge({ approved, status }: { approved: boolean; status: string }) {
  const classes = approved
    ? "border-primary/45 bg-primary-dim text-primary"
    : "border-danger/45 bg-danger-dim text-danger";

  return (
    <span className={`inline-flex rounded border px-2 py-1 text-xs font-semibold ${classes}`}>
      {approved ? "Approved" : status}
    </span>
  );
}

function upsertRunSummary(
  runs: AdminAgentRunSummary[],
  run: AdminAgentRunDetail,
): AdminAgentRunSummary[] {
  const summary = {
    run_id: run.run_id,
    market_id: run.market_id,
    market_slug: run.market_slug,
    market_title: run.market_title,
    status: run.status,
    graph_version: run.graph_version,
    approved: run.approved,
    step_count: run.steps.length,
    errors: run.errors,
    created_at: run.created_at,
  };
  return [summary, ...runs.filter((item) => item.run_id !== run.run_id)].slice(0, RUN_LIMIT);
}

function upsertCaptureRun(
  runs: AdminMarketSnapshotCaptureRun[],
  run: AdminMarketSnapshotCaptureRun,
): AdminMarketSnapshotCaptureRun[] {
  return [run, ...runs.filter((item) => item.run_id !== run.run_id)].slice(
    0,
    CAPTURE_LIMIT,
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatOptionalDate(value: string | null) {
  if (!value) {
    return "Not recorded";
  }
  return formatDate(value);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
