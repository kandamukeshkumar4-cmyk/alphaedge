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
      <header className="pop-head">
        <span className="pop-logo" aria-hidden="true">
          AE
        </span>
        <div>
          <h1>AlphaEdge Mirror</h1>
          <p>Research &amp; paper simulation only. No betting execution or real-money flows.</p>
        </div>
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
  body { margin: 0; background: #0a0c12; }
  * { box-sizing: border-box; }
  .popup {
    width: 340px;
    padding: 16px;
    color: #eef1f7;
    background: linear-gradient(180deg, #0f121b 0%, #0a0c12 160px);
    font: 500 13px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .pop-head { display: flex; align-items: flex-start; gap: 11px; margin-bottom: 14px; }
  .pop-logo {
    flex: none;
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(135deg, #2e7df6, #1b5fd0);
    color: #fff;
    font: 800 12px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    box-shadow: 0 4px 12px rgb(46 125 246 / 0.35);
  }
  h1 { margin: 0; font-size: 15px; font-weight: 800; line-height: 1.2; letter-spacing: -0.01em; }
  p { margin: 4px 0 0; color: #8a93a6; font-size: 11px; line-height: 1.4; }
  form { display: grid; gap: 10px; margin-bottom: 10px; }
  label { display: grid; gap: 5px; color: #646c7e; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
  input {
    min-height: 34px;
    width: 100%;
    border: 1px solid #232838;
    border-radius: 9px;
    background: #11141c;
    color: #eef1f7;
    padding: 6px 9px;
    font: 600 13px/1.2 inherit;
  }
  input:focus { outline: none; border-color: #2e7df6; box-shadow: 0 0 0 3px rgb(46 125 246 / 0.18); }
  button {
    min-height: 38px;
    width: 100%;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #2e7df6, #1b5fd0);
    color: #fff;
    font: 800 13px/1.2 inherit;
    cursor: pointer;
    transition: filter 0.15s ease;
  }
  button:hover { filter: brightness(1.08); }
  button + button { margin-top: 8px; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .recovery-code {
    display: grid;
    gap: 6px;
    margin-top: 10px;
    border: 1px solid #4b4a2f;
    border-radius: 12px;
    background: #1e1d12;
    padding: 10px 11px;
  }
  .recovery-code strong { color: #e4d36b; font-size: 12px; }
  .recovery-code input { background: #14130c; border-color: #4b4a2f; }
  .queue {
    margin-top: 12px;
    border: 1px solid #232838;
    border-radius: 14px;
    background: #11141c;
    padding: 12px;
  }
  .queue-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }
  .queue-head strong { font-size: 13px; font-weight: 800; }
  .queue-head span { color: #2e7df6; font-size: 11px; font-weight: 700; }
  .queue-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-bottom: 10px;
  }
  .queue-grid span {
    border: 1px solid #232838;
    border-radius: 9px;
    background: #151926;
    padding: 7px 9px;
    color: #9aa3b5;
    font-size: 11px;
    font-weight: 600;
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
    border-top: 1px solid #232838;
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
    color: #9aa3b5;
    font-size: 12px;
  }
  .notice { margin-top: 12px; border-radius: 10px; padding: 8px 10px; font-size: 12px; }
  .muted { background: #151926; color: #9aa3b5; }
  .success { background: rgb(33 208 122 / 0.12); color: #21d07a; }
  .error { background: rgb(255 84 112 / 0.12); color: #ff7a8f; }
`;

function updateResolvedBadge(count: number) {
  if (!chrome.action) {
    return;
  }
  chrome.action.setBadgeText({ text: count > 0 ? String(Math.min(count, 99)) : "" });
  chrome.action.setBadgeBackgroundColor?.({ color: "#2e7df6" });
}
