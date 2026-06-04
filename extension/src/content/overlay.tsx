import { FormEvent, useEffect, useMemo, useState } from "react";

import { lifecycleStateForMarket } from "../lifecycle";
import { buildLockForecastMessage } from "../messaging";
import type { ParsedSupportedMarket } from "../platforms";
import { buildForecastReceipt } from "../receipt";
import { getSettings } from "../storage";

type Props = {
  market: ParsedSupportedMarket;
};

type Notice = {
  tone: "success" | "error" | "muted";
  text: string;
};

export function MirrorOverlay({ market }: Props) {
  const [token, setToken] = useState("");
  const [marketTitle, setMarketTitle] = useState(market.title);
  const [outcomeLabel, setOutcomeLabel] = useState("YES");
  const [userProbability, setUserProbability] = useState(50);
  const [marketProbability, setMarketProbability] = useState("");
  const [dashboardUrl, setDashboardUrl] = useState("http://localhost:3000/forecast");
  const [lastReceipt, setLastReceipt] = useState("");
  const [lifecycleLabel, setLifecycleLabel] = useState(lifecycleStateForMarket(market).label);
  const [notice, setNotice] = useState<Notice>({
    tone: "muted",
    text: "Research and paper simulation only.",
  });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    void getSettings().then((settings) => {
      setToken(settings.token);
      setDashboardUrl(settings.dashboardUrl);
    });
  }, []);

  const canLock = useMemo(() => Boolean(token.trim()) && !isSaving, [isSaving, token]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const implied = marketProbability.trim() ? Number(marketProbability) / 100 : null;
    if (!Number.isFinite(userProbability) || userProbability < 0 || userProbability > 100) {
      setNotice({ tone: "error", text: "Probability must be 0 to 100." });
      return;
    }
    if (implied !== null && (!Number.isFinite(implied) || implied < 0 || implied > 1)) {
      setNotice({ tone: "error", text: "Market probability must be 0 to 100." });
      return;
    }

    setIsSaving(true);
    const lockedAt = new Date().toISOString();
    const message = buildLockForecastMessage({
      token: token.trim(),
      url: market.canonicalUrl,
      userProbability: userProbability / 100,
      marketImpliedProbability: market.manualOnly ? implied : null,
      outcomeLabel: outcomeLabel.trim() || "YES",
      marketTitle: marketTitle.trim() || undefined,
      snapshotMetadata: {
        provider: market.provider,
        external_id: market.externalId,
        manual_only: market.manualOnly,
      },
    });

    chrome.runtime.sendMessage(message, (response) => {
      setIsSaving(false);
      if (chrome.runtime.lastError) {
        setNotice({ tone: "error", text: chrome.runtime.lastError.message ?? "Request failed." });
        return;
      }
      if (!response?.ok) {
        setNotice({ tone: "error", text: response?.error ?? "Forecast lock failed." });
        return;
      }
      const queued = Boolean(
        response.data && typeof response.data === "object" && "queued" in response.data,
      );
      const status = queued ? "queued" : "locked";
      setLifecycleLabel(
        lifecycleStateForMarket(market, queued ? "pending" : "locked").label,
      );
      setLastReceipt(
        buildForecastReceipt({
          message,
          lockedAt,
          platform: market.provider,
          status,
        }),
      );
      setNotice({ tone: "success", text: queued ? "Forecast queued." : "Forecast locked." });
    });
  }

  async function handleCopyReceipt() {
    if (!lastReceipt) {
      return;
    }
    await navigator.clipboard.writeText(lastReceipt);
    setNotice({ tone: "success", text: "Forecast receipt copied." });
  }

  return (
    <>
      <style>{styles}</style>
      <aside className="ae-panel" aria-label="AlphaEdge Mirror forecast tracker">
        <div className="ae-header">
          <div>
            <div className="ae-title">AlphaEdge Mirror</div>
            <div className="ae-subtitle">Research and paper simulation only</div>
          </div>
          <span className="ae-chip">{market.provider}</span>
        </div>
        <div className="ae-state">{lifecycleLabel}</div>

        <form className="ae-form" onSubmit={handleSubmit}>
          {market.manualOnly ? (
            <>
              <label>
                <span>Market</span>
                <input value={marketTitle} onChange={(event) => setMarketTitle(event.target.value)} />
              </label>
              <label>
                <span>Manual Market %</span>
                <input
                  inputMode="decimal"
                  placeholder="Optional"
                  value={marketProbability}
                  onChange={(event) => setMarketProbability(event.target.value)}
                />
              </label>
            </>
          ) : null}

          <label>
            <span>Outcome</span>
            <input value={outcomeLabel} onChange={(event) => setOutcomeLabel(event.target.value)} />
          </label>

          <label>
            <span>Your P(YES): {userProbability}%</span>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={userProbability}
              onChange={(event) => setUserProbability(Number(event.target.value))}
            />
          </label>

          <button disabled={!canLock} type="submit">
            {isSaving ? "Locking" : "Lock forecast"}
          </button>
        </form>

        <div className="ae-actions">
          <a href={dashboardUrl} target="_blank" rel="noreferrer">
            View dashboard
          </a>
          <button disabled={!lastReceipt} type="button" onClick={() => void handleCopyReceipt()}>
            Copy receipt
          </button>
        </div>

        <div className={`ae-notice ae-${notice.tone}`}>{notice.text}</div>
      </aside>
    </>
  );
}

const styles = `
  :host { all: initial; }
  .ae-panel {
    position: fixed;
    right: 18px;
    bottom: 18px;
    z-index: 2147483647;
    width: min(340px, calc(100vw - 32px));
    box-sizing: border-box;
    border: 1px solid #243039;
    border-radius: 8px;
    background: #090c0f;
    color: #f2f7f3;
    box-shadow: 0 16px 42px rgb(0 0 0 / 0.42);
    font: 500 13px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 14px;
  }
  .ae-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  .ae-title { font-weight: 900; font-size: 15px; }
  .ae-subtitle { color: #9ea9a3; font-size: 12px; margin-top: 2px; }
  .ae-chip {
    border: 1px solid #33444d;
    border-radius: 6px;
    padding: 3px 7px;
    color: #24c66d;
    font: 800 11px/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    text-transform: uppercase;
  }
  .ae-form { display: grid; gap: 10px; }
  .ae-state {
    margin-bottom: 10px;
    border: 1px solid #243039;
    border-radius: 6px;
    padding: 7px 8px;
    color: #9ea9a3;
    font-size: 12px;
  }
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
    font: 600 13px/1.2 inherit;
  }
  input[type="range"] { padding: 0; accent-color: #24c66d; }
  button {
    min-height: 38px;
    border: 1px solid #24c66d;
    border-radius: 6px;
    background: #24c66d;
    color: #090c0f;
    font: 900 13px/1.2 inherit;
    cursor: pointer;
  }
  button:disabled { cursor: not-allowed; opacity: .55; }
  .ae-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 10px;
  }
  .ae-actions a {
    display: grid;
    min-height: 34px;
    place-items: center;
    border: 1px solid #33444d;
    border-radius: 6px;
    color: #24c66d;
    text-decoration: none;
    font-weight: 900;
  }
  .ae-actions button {
    min-height: 34px;
    border-color: #33444d;
    background: #151b20;
    color: #f2f7f3;
  }
  .ae-notice { margin-top: 10px; border-radius: 6px; padding: 8px; font-size: 12px; }
  .ae-muted { background: #151b20; color: #9ea9a3; }
  .ae-success { background: #0c2618; color: #24c66d; }
  .ae-error { background: #2b1012; color: #ff6b6d; }
`;
