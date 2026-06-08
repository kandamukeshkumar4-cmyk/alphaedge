import { FormEvent, useEffect, useMemo, useState } from "react";

import { buildEdgePreview, shouldPromptForReforecast } from "../edge-preview";
import { lifecycleStateForMarket } from "../lifecycle";
import { buildLockForecastMessage } from "../messaging";
import type { ParsedSupportedMarket } from "../platforms";
import type { MarketPrefill } from "../prefill";
import { buildForecastReceipt } from "../receipt";
import { getSettings } from "../storage";
import { buildRecordTelemetryMessage } from "../telemetry";

type Props = {
  market: ParsedSupportedMarket;
  prefill?: MarketPrefill;
};

type Notice = {
  tone: "success" | "error" | "muted";
  text: string;
};

type TabId = "edge" | "market" | "lock";

const TABS: { id: TabId; label: string }[] = [
  { id: "edge", label: "Edge" },
  { id: "market", label: "Market" },
  { id: "lock", label: "Lock" },
];

export function MirrorOverlay({ market, prefill }: Props) {
  const [token, setToken] = useState("");
  const [marketTitle, setMarketTitle] = useState(prefill?.title ?? market.title);
  const [category, setCategory] = useState(prefill?.category ?? "");
  const [closeAt, setCloseAt] = useState(prefill?.closeAt);
  const [serverMarketProbability, setServerMarketProbability] = useState<number | null>(
    prefill?.marketImpliedProbability ?? null,
  );
  const [outcomeLabel, setOutcomeLabel] = useState("YES");
  const [userProbability, setUserProbability] = useState(50);
  const [marketProbability, setMarketProbability] = useState("");
  const [manualOdds, setManualOdds] = useState("");
  const [dashboardUrl, setDashboardUrl] = useState("http://localhost:3000/forecast");
  const [lastReceipt, setLastReceipt] = useState("");
  const [lifecycleLabel, setLifecycleLabel] = useState(lifecycleStateForMarket(market).label);
  const [tab, setTab] = useState<TabId>("edge");
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

  useEffect(() => {
    if (!prefill) {
      return;
    }
    setMarketTitle(prefill.title);
    setCategory(prefill.category ?? "");
    setCloseAt(prefill.closeAt);
    setServerMarketProbability(prefill.marketImpliedProbability);
    if (prefill.error) {
      setNotice({
        tone: "muted",
        text: "Server prefill unavailable. Research and paper simulation only.",
      });
    }
  }, [prefill]);

  const canLock = useMemo(() => Boolean(token.trim()) && !isSaving, [isSaving, token]);
  const manualImpliedProbability = parseManualProbability(marketProbability);
  const effectiveMarketProbability = market.manualOnly
    ? manualImpliedProbability
    : serverMarketProbability;
  const edgePreview = buildEdgePreview({
    userProbability: userProbability / 100,
    marketImpliedProbability: effectiveMarketProbability,
    closeAt,
  });
  const nearClosePrompt = shouldPromptForReforecast(edgePreview.timeBucket);

  const marketPct =
    effectiveMarketProbability === null ? null : Math.round(effectiveMarketProbability * 100);
  const marketLabel =
    effectiveMarketProbability === null
      ? "pending"
      : `${(effectiveMarketProbability * 100).toFixed(1)}%`;
  const edgeValue =
    effectiveMarketProbability === null ? null : userProbability / 100 - effectiveMarketProbability;
  const edgeToneClass =
    edgeValue === null ? "" : edgeValue > 0.0005 ? "ae-pos" : edgeValue < -0.0005 ? "ae-neg" : "";

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
    if (market.manualOnly && !manualOdds.trim()) {
      setNotice({ tone: "error", text: "Manual odds are required for FanDuel capture." });
      return;
    }

    setIsSaving(true);
    const lockedAt = new Date().toISOString();
    const message = buildLockForecastMessage({
      token: token.trim(),
      url: market.canonicalUrl,
      userProbability: userProbability / 100,
      marketImpliedProbability: market.manualOnly ? implied : serverMarketProbability,
      outcomeLabel: outcomeLabel.trim() || "YES",
      snapshotSource: market.manualOnly
        ? "manual"
        : prefill?.snapshotMetadata.snapshot_source
          ? String(prefill.snapshotMetadata.snapshot_source)
          : "server",
      marketTitle: marketTitle.trim() || undefined,
      category: category.trim() || undefined,
      closeAt,
      snapshotMetadata: {
        provider: market.provider,
        external_id: market.externalId,
        manual_only: market.manualOnly,
        close_at: closeAt,
        category: category.trim() || undefined,
        ...(prefill?.snapshotMetadata ?? {}),
        ...(market.manualOnly ? { manual_odds: manualOdds.trim() } : {}),
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

  function handleDashboardOpen() {
    chrome.runtime.sendMessage(buildRecordTelemetryMessage({ eventType: "dashboard_opened" }));
  }

  return (
    <>
      <style>{styles}</style>
      <aside className="ae-panel" aria-label="AlphaEdge Mirror forecast tracker">
        <div className="ae-head">
          <div className="ae-brand">
            <span className="ae-logo" aria-hidden="true">
              AE
            </span>
            <div className="ae-brandtext">
              <div className="ae-title">AlphaEdge Mirror</div>
              <div className="ae-subtitle">Research &amp; paper simulation only</div>
            </div>
          </div>
          <span className="ae-chip">{market.provider}</span>
        </div>

        <nav className="ae-tabs" role="tablist" aria-label="Mirror sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`ae-tab ${tab === t.id ? "ae-tab-on" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* EDGE — vidIQ-style metric chips + "You vs Market" comparison */}
        <div className="ae-pane" role="tabpanel" hidden={tab !== "edge"}>
          <div className="ae-metrics">
            <div className="ae-metric">
              <span className="ae-metric-k">Your read</span>
              <span className="ae-metric-v">{userProbability}%</span>
            </div>
            <div className="ae-metric">
              <span className="ae-metric-k">Edge</span>
              <span className={`ae-metric-v ${edgeToneClass}`}>{edgePreview.deltaLabel}</span>
            </div>
            <div className="ae-metric">
              <span className="ae-metric-k">Timing</span>
              <span className="ae-metric-v ae-metric-v-sm">{edgePreview.timeBucket}</span>
            </div>
          </div>

          <div className="ae-compare">
            <div className="ae-compare-head">
              <span className="ae-compare-num">{userProbability}%</span>
              <span className="ae-compare-sub">your P(YES)</span>
              <div className="ae-legend">
                <span>
                  <i className="ae-dot ae-dot-you" /> You
                </span>
                <span>
                  <i className="ae-dot ae-dot-mkt" /> Market
                </span>
              </div>
            </div>
            <div className="ae-bar">
              <div className="ae-bar-fill ae-bar-you" style={{ width: `${userProbability}%` }} />
            </div>
            <div className="ae-bar">
              <div
                className="ae-bar-fill ae-bar-mkt"
                style={{ width: `${marketPct ?? 0}%` }}
              />
            </div>
            <div className="ae-compare-foot">
              <span>Market {marketLabel}</span>
              <span>{edgePreview.anchoringLabel}</span>
            </div>
          </div>

          <div className="ae-state">{lifecycleLabel}</div>
          <p className="ae-pnl">{edgePreview.paperPnlLabel}</p>
        </div>

        {/* MARKET — detected market summary */}
        <div className="ae-pane" role="tabpanel" hidden={tab !== "market"}>
          <section className="ae-market-summary" aria-label="Detected market">
            <strong>{marketTitle || market.externalId}</strong>
            <span>{category || "Category unavailable"}</span>
            <span>
              {edgePreview.timeLabel} · {edgePreview.timeBucket}
            </span>
            <span>
              {market.manualOnly
                ? "FanDuel manual capture only"
                : serverMarketProbability === null
                  ? "Market implied pending from server"
                  : `Market implied ${(serverMarketProbability * 100).toFixed(1)}%`}
            </span>
          </section>
        </div>

        {/* LOCK — the forecast form */}
        <div className="ae-pane" role="tabpanel" hidden={tab !== "lock"}>
          <form className="ae-form" onSubmit={handleSubmit}>
            {market.manualOnly ? (
              <>
                <label>
                  <span>Market</span>
                  <input value={marketTitle} onChange={(event) => setMarketTitle(event.target.value)} />
                </label>
                <label>
                  <span>Odds</span>
                  <input
                    placeholder="Manual entry"
                    value={manualOdds}
                    onChange={(event) => setManualOdds(event.target.value)}
                  />
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
              <span>{market.manualOnly ? "Selection" : "Outcome"}</span>
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

            <section className={`ae-preview ${edgePreview.anchored ? "ae-preview-anchored" : ""}`}>
              <div>
                <span>Delta</span>
                <strong className={edgeToneClass}>{edgePreview.deltaLabel}</strong>
              </div>
              <div>
                <span>Timing</span>
                <strong>{edgePreview.timeBucket}</strong>
              </div>
              <p>{edgePreview.anchoringLabel}</p>
              <p>{edgePreview.paperPnlLabel}</p>
            </section>

            {nearClosePrompt ? (
              <div className="ae-reforecast">{edgePreview.timeLabel} - lock a final read?</div>
            ) : null}

            <button className="ae-submit" disabled={!canLock} type="submit">
              {isSaving ? "Locking" : "Lock forecast"}
            </button>
          </form>

          <div className="ae-actions">
            <a href={dashboardUrl} target="_blank" rel="noreferrer" onClick={handleDashboardOpen}>
              View dashboard
            </a>
            <button disabled={!lastReceipt} type="button" onClick={() => void handleCopyReceipt()}>
              Copy receipt
            </button>
          </div>
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
    width: min(360px, calc(100vw - 32px));
    box-sizing: border-box;
    border: 1px solid #242a3a;
    border-radius: 16px;
    background: linear-gradient(180deg, #0f121b 0%, #0b0d14 100%);
    color: #eef1f7;
    box-shadow: 0 18px 50px rgb(0 0 0 / 0.5);
    font: 500 13px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 14px;
  }
  .ae-panel * { box-sizing: border-box; }
  .ae-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  .ae-brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .ae-logo {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    background: linear-gradient(135deg, #2e7df6, #1b5fd0);
    color: #fff;
    font: 800 12px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    box-shadow: 0 4px 12px rgb(46 125 246 / 0.35);
  }
  .ae-title { font-weight: 800; font-size: 14px; letter-spacing: -0.01em; }
  .ae-subtitle { color: #8a93a6; font-size: 11px; margin-top: 1px; }
  .ae-chip {
    border: 1px solid #2c3550;
    border-radius: 999px;
    padding: 3px 9px;
    color: #2e7df6;
    background: rgb(46 125 246 / 0.12);
    font: 700 10px/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ae-tabs {
    display: flex;
    gap: 4px;
    padding: 4px;
    margin-bottom: 12px;
    border-radius: 12px;
    background: #151926;
    border: 1px solid #1f2433;
  }
  .ae-tab {
    flex: 1;
    border: none;
    border-radius: 9px;
    background: transparent;
    color: #9aa3b5;
    padding: 7px 0;
    font: 700 12px/1 inherit;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }
  .ae-tab:hover { color: #eef1f7; }
  .ae-tab-on {
    background: #2e7df6;
    color: #fff;
    box-shadow: 0 2px 8px rgb(46 125 246 / 0.4);
  }
  .ae-pane[hidden] { display: none; }
  .ae-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .ae-metric {
    display: grid;
    gap: 4px;
    border: 1px solid #232838;
    border-radius: 12px;
    background: #11141c;
    padding: 9px 10px;
  }
  .ae-metric-k {
    color: #646c7e;
    font: 700 9px/1.1 inherit;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .ae-metric-v {
    color: #eef1f7;
    font: 800 17px/1.1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .ae-metric-v-sm { font-size: 13px; }
  .ae-pos { color: #21d07a; }
  .ae-neg { color: #ff5470; }
  .ae-compare {
    display: grid;
    gap: 8px;
    margin-top: 10px;
    border: 1px solid #232838;
    border-radius: 14px;
    background: #11141c;
    padding: 12px;
  }
  .ae-compare-head { display: flex; align-items: baseline; gap: 8px; }
  .ae-compare-num {
    font: 800 26px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: #eef1f7;
  }
  .ae-compare-sub { color: #9aa3b5; font-size: 11px; }
  .ae-legend { margin-left: auto; display: flex; gap: 10px; color: #9aa3b5; font-size: 10px; }
  .ae-legend span { display: inline-flex; align-items: center; gap: 5px; }
  .ae-dot { width: 8px; height: 8px; border-radius: 3px; display: inline-block; }
  .ae-dot-you { background: #2e7df6; }
  .ae-dot-mkt { background: #ff4d8d; }
  .ae-bar { height: 8px; border-radius: 6px; background: #1b2030; overflow: hidden; }
  .ae-bar-fill { height: 100%; border-radius: 6px; transition: width 0.4s cubic-bezier(0.22,1,0.36,1); }
  .ae-bar-you { background: linear-gradient(90deg, #2e7df6, #5aa0ff); }
  .ae-bar-mkt { background: linear-gradient(90deg, #ff4d8d, #ff7fb0); }
  .ae-compare-foot { display: flex; justify-content: space-between; gap: 8px; color: #9aa3b5; font-size: 11px; }
  .ae-state {
    margin-top: 10px;
    border: 1px solid #232838;
    border-radius: 10px;
    padding: 7px 9px;
    color: #9aa3b5;
    font-size: 11px;
  }
  .ae-pnl { margin: 8px 0 0; color: #9aa3b5; font-size: 12px; line-height: 1.4; }
  .ae-market-summary {
    display: grid;
    gap: 4px;
    border: 1px solid #232838;
    border-radius: 12px;
    background: #11141c;
    padding: 11px;
  }
  .ae-market-summary strong { color: #eef1f7; font-size: 13px; line-height: 1.3; }
  .ae-market-summary span { color: #9aa3b5; font-size: 12px; line-height: 1.35; }
  .ae-form { display: grid; gap: 10px; }
  label { display: grid; gap: 5px; color: #646c7e; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; }
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
  input[type="range"] { padding: 0; min-height: 0; accent-color: #2e7df6; box-shadow: none; }
  .ae-preview {
    display: grid;
    gap: 6px;
    border: 1px solid #232838;
    border-radius: 12px;
    background: #11141c;
    padding: 9px;
  }
  .ae-preview-anchored { border-color: #2c3550; background: #151926; }
  .ae-preview div { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .ae-preview span { color: #646c7e; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
  .ae-preview strong { color: #eef1f7; font-size: 12px; text-align: right; }
  .ae-preview p { margin: 0; color: #9aa3b5; font-size: 12px; line-height: 1.35; }
  .ae-reforecast {
    border: 1px solid #4b4a2f;
    border-radius: 10px;
    background: #1e1d12;
    color: #e4d36b;
    padding: 7px 9px;
    font-size: 12px;
  }
  .ae-submit {
    min-height: 40px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #2e7df6, #1b5fd0);
    color: #fff;
    font: 800 13px/1.2 inherit;
    cursor: pointer;
    transition: filter 0.15s ease;
  }
  .ae-submit:hover { filter: brightness(1.08); }
  .ae-submit:disabled { cursor: not-allowed; opacity: 0.5; }
  .ae-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
  .ae-actions a {
    display: grid;
    min-height: 34px;
    place-items: center;
    border: 1px solid #2c3550;
    border-radius: 9px;
    color: #2e7df6;
    text-decoration: none;
    font-weight: 700;
  }
  .ae-actions a:hover { background: rgb(46 125 246 / 0.1); }
  .ae-actions button {
    min-height: 34px;
    border: 1px solid #232838;
    background: #151926;
    color: #eef1f7;
    border-radius: 9px;
    font: 700 13px/1.2 inherit;
    cursor: pointer;
  }
  .ae-actions button:disabled { cursor: not-allowed; opacity: 0.5; }
  .ae-notice { margin-top: 12px; border-radius: 10px; padding: 8px 10px; font-size: 12px; }
  .ae-muted { background: #151926; color: #9aa3b5; }
  .ae-success { background: rgb(33 208 122 / 0.12); color: #21d07a; }
  .ae-error { background: rgb(255 84 112 / 0.12); color: #ff7a8f; }
`;

function parseManualProbability(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value) / 100;
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1 ? parsed : null;
}
