import { FormEvent, useEffect, useState } from "react";

import {
  createAnonymousForecaster,
  fetchForecastDashboard,
  fetchForecastLifecycle,
  recoverForecaster,
  recordMirrorTelemetryEvent,
  sendForecastToBackend,
  type ForecastDashboardSummary,
  type ForecastLifecycleSummary,
} from "../backend-client";
import { indexedDbForecastQueueStore, syncQueuedForecasts, type QueuedForecast } from "../queue";
import { getSettings, normalizeApiBase, normalizeUrl, saveSettings } from "../storage";
import { telemetryForSyncedQueue } from "../telemetry";
import { buildPopupDashboardView } from "./popup-dashboard";

type Notice = {
  tone: "success" | "error" | "muted";
  text: string;
};

export function Popup() {
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [dashboardUrl, setDashboardUrl] = useState("http://localhost:3000/forecast");
  const [tokenDraft, setTokenDraft] = useState("");
  const [recoveryCodeDraft, setRecoveryCodeDraft] = useState("");
  const [latestRecoveryCode, setLatestRecoveryCode] = useState("");
  const [hasToken, setHasToken] = useState(false);
  const [queue, setQueue] = useState<QueuedForecast[]>([]);
  const [dashboard, setDashboard] = useState<ForecastDashboardSummary | null>(null);
  const [lifecycle, setLifecycle] = useState<ForecastLifecycleSummary | null>(null);
  const [unresolvedCount, setUnresolvedCount] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [notice, setNotice] = useState<Notice>({
    tone: "muted",
    text: "Research and paper simulation only.",
  });
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    void getSettings().then((settings) => {
      setApiBase(settings.apiBase);
      setDashboardUrl(settings.dashboardUrl);
      setHasToken(Boolean(settings.token));
    });
    void refreshQueue();
    void refreshLifecycle();
    void refreshDashboard();
  }, []);

  const miniDashboard = buildPopupDashboardView({ dashboard, lifecycle, queue });

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextSettings = {
      apiBase: normalizeApiBase(apiBase),
      dashboardUrl: normalizeUrl(dashboardUrl),
      ...(tokenDraft.trim() ? { token: tokenDraft.trim() } : {}),
    };
    await saveSettings(nextSettings);
    if (tokenDraft.trim()) {
      setHasToken(true);
      setTokenDraft("");
    }
    setNotice({ tone: "success", text: "Settings saved." });
  }

  async function handleCreateProfile() {
    setIsCreating(true);
    try {
      const normalizedApiBase = normalizeApiBase(apiBase);
      const data = await createAnonymousForecaster({
        apiBase: normalizedApiBase,
      });
      await saveSettings({ apiBase: normalizedApiBase, token: data.token });
      setLatestRecoveryCode(data.recovery_code);
      setHasToken(true);
      setTokenDraft("");
      setNotice({ tone: "success", text: "Forecaster profile created. Save the recovery code." });
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "Could not create profile.",
      });
    } finally {
      setIsCreating(false);
    }
  }

  async function handleRecoverProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const normalizedApiBase = normalizeApiBase(apiBase);
      const data = await recoverForecaster({
        apiBase: normalizedApiBase,
        recoveryCode: recoveryCodeDraft.trim(),
      });
      await saveSettings({ apiBase: normalizedApiBase, token: data.token });
      setLatestRecoveryCode(data.recovery_code);
      setRecoveryCodeDraft("");
      setHasToken(true);
      setNotice({ tone: "success", text: "Profile recovered. Save the new recovery code." });
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "Could not recover profile.",
      });
    }
  }

  async function refreshQueue() {
    setQueue(await indexedDbForecastQueueStore.loadQueue());
  }

  async function refreshLifecycle() {
    const settings = await getSettings();
    if (!settings.token) {
      return;
    }
    try {
      const lifecycle = await fetchForecastLifecycle({
        apiBase: settings.apiBase,
        token: settings.token,
      });
      setLifecycle(lifecycle);
      setUnresolvedCount(lifecycle.unresolved_count);
      setResolvedCount(lifecycle.recently_resolved_count);
      updateResolvedBadge(lifecycle.recently_resolved_count);
    } catch {
      setLifecycle(null);
      setUnresolvedCount(0);
      setResolvedCount(0);
      updateResolvedBadge(0);
    }
  }

  async function refreshDashboard() {
    const settings = await getSettings();
    if (!settings.token) {
      return;
    }
    try {
      setDashboard(
        await fetchForecastDashboard({
          apiBase: settings.apiBase,
          token: settings.token,
        }),
      );
    } catch {
      setDashboard(null);
    }
  }

  async function handleSyncQueue() {
    const settings = await getSettings();
    const result = await syncQueuedForecasts(indexedDbForecastQueueStore, async (queued) => {
      try {
        const response = await sendForecastToBackend({
          apiBase: settings.apiBase,
          message: queued.message,
          idempotencyKey: queued.idempotencyKey,
        });
        if (!response.ok) {
          return { ok: false, error: response.error };
        }
        return { ok: true };
      } catch (error) {
        return {
          ok: false,
          error: error instanceof Error ? error.message : "Sync failed.",
        };
      }
    });
    await refreshQueue();
    await refreshLifecycle();
    await refreshDashboard();
    for (const event of telemetryForSyncedQueue(result.synced)) {
      void recordMirrorTelemetryEvent({
        apiBase: settings.apiBase,
        token: settings.token || undefined,
        event,
      });
    }
    setNotice({
      tone: result.failed ? "error" : "success",
      text: `Synced ${result.synced}; failed ${result.failed}.`,
    });
  }

  return (
    <main className="popup">
      <style>{styles}</style>
      <header>
        <h1>AlphaEdge Mirror</h1>
        <p>Research and paper simulation only. No betting execution or real-money flows.</p>
      </header>

      <form onSubmit={handleSave}>
        <label>
          <span>API Base</span>
          <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
        </label>
        <label>
          <span>Dashboard URL</span>
          <input value={dashboardUrl} onChange={(event) => setDashboardUrl(event.target.value)} />
        </label>
        <label>
          <span>{hasToken ? "Profile saved" : "Forecaster token"}</span>
          <input
            type="password"
            placeholder={hasToken ? "Paste only to replace" : "Paste token"}
            value={tokenDraft}
            onChange={(event) => setTokenDraft(event.target.value)}
          />
        </label>
        <button type="submit">Save</button>
      </form>

      <button disabled={isCreating} type="button" onClick={() => void handleCreateProfile()}>
        {isCreating ? "Creating" : "Create anonymous profile"}
      </button>

      {latestRecoveryCode ? (
        <section className="recovery-code">
          <strong>Recovery code</strong>
          <input readOnly value={latestRecoveryCode} />
        </section>
      ) : null}

      <form onSubmit={handleRecoverProfile}>
        <label>
          <span>Recovery code</span>
          <input
            type="password"
            placeholder="Paste recovery code"
            value={recoveryCodeDraft}
            onChange={(event) => setRecoveryCodeDraft(event.target.value)}
          />
        </label>
        <button disabled={!recoveryCodeDraft.trim()} type="submit">
          Recover profile
        </button>
      </form>

      <section className="queue">
        <div className="queue-head">
          <strong>Mini-dashboard</strong>
          <span>{unresolvedCount} unresolved</span>
        </div>
        <div className="queue-grid">
          <span>Brier {miniDashboard.rollingBrier}</span>
          <span>Independent {miniDashboard.independentCount}</span>
          <span>Anchored {miniDashboard.anchoredCount}</span>
          <span>Recently scored {resolvedCount}</span>
        </div>
        {miniDashboard.lastResolved.length ? (
          <ol className="resolved-list">
            {miniDashboard.lastResolved.map((row) => (
              <li key={`${row.title}-${row.score}`}>
                <strong>{row.title}</strong>
                <span>
                  {row.score} · {row.pnl}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-mini">No resolved forecasts yet.</p>
        )}
      </section>

      <section className="queue">
        <div className="queue-head">
          <strong>Queue</strong>
          <span>{miniDashboard.pendingText}</span>
        </div>
        <div className="queue-grid">
          <span>Pending {queue.filter((row) => row.status === "pending").length}</span>
          <span>Syncing {queue.filter((row) => row.status === "syncing").length}</span>
          <span>Synced {queue.filter((row) => row.status === "synced").length}</span>
          <span>Failed {queue.filter((row) => row.status === "failed").length}</span>
        </div>
        <button type="button" onClick={() => void handleSyncQueue()}>
          Retry queue
        </button>
      </section>

      <div className={`notice ${notice.tone}`}>{notice.text}</div>
    </main>
  );
}

const styles = `
  body { margin: 0; background: #090c0f; }
  .popup {
    box-sizing: border-box;
    width: 320px;
    padding: 16px;
    color: #f2f7f3;
    font: 500 13px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  h1 { margin: 0; font-size: 18px; line-height: 1.2; }
  p { margin: 6px 0 14px; color: #9ea9a3; }
  form { display: grid; gap: 10px; margin-bottom: 10px; }
  label { display: grid; gap: 5px; color: #66716b; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
  input {
    min-height: 34px;
    box-sizing: border-box;
    width: 100%;
    border: 1px solid #243039;
    border-radius: 6px;
    background: #0f1417;
    color: #f2f7f3;
    padding: 6px 8px;
  }
  button {
    min-height: 36px;
    width: 100%;
    border: 1px solid #24c66d;
    border-radius: 6px;
    background: #24c66d;
    color: #090c0f;
    font-weight: 900;
  }
  button + button { margin-top: 8px; }
  button:disabled { opacity: .55; }
  .recovery-code {
    display: grid;
    gap: 6px;
    margin-top: 10px;
    border: 1px solid #4b4a2f;
    border-radius: 6px;
    background: #1e1d12;
    padding: 10px;
  }
  .recovery-code strong {
    color: #e4d36b;
    font-size: 12px;
  }
  .queue {
    margin-top: 12px;
    border: 1px solid #243039;
    border-radius: 6px;
    padding: 10px;
  }
  .queue-head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;
  }
  .queue-head span { color: #9ea9a3; }
  .queue-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-bottom: 8px;
    color: #9ea9a3;
    font-size: 12px;
  }
  .resolved-list {
    display: grid;
    gap: 6px;
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
  }
  .resolved-list li {
    display: grid;
    gap: 2px;
    border-top: 1px solid #243039;
    padding-top: 6px;
  }
  .resolved-list strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }
  .resolved-list span,
  .empty-mini {
    margin: 0;
    color: #9ea9a3;
    font-size: 12px;
  }
  .notice { margin-top: 10px; border-radius: 6px; padding: 8px; font-size: 12px; }
  .muted { background: #151b20; color: #9ea9a3; }
  .success { background: #0c2618; color: #24c66d; }
  .error { background: #2b1012; color: #ff6b6d; }
`;

function updateResolvedBadge(count: number) {
  if (!chrome.action) {
    return;
  }
  chrome.action.setBadgeText({ text: count > 0 ? String(Math.min(count, 99)) : "" });
  chrome.action.setBadgeBackgroundColor?.({ color: "#24c66d" });
}
