import { useEffect, useState, type ReactNode } from "react";

import {
  SIGNAL_PANEL_DISCLAIMER,
  fetchArbitrageSignal,
  fetchDutchingSignal,
  fetchForecastSignal,
  fetchSmartMoneySignal,
  type ArbitrageSignalResponse,
  type DutchingSignalResponse,
  type ForecastSignalResponse,
  type SmartMoneySignalResponse,
} from "../backend-client";
import type { ParsedSupportedMarket } from "../platforms";

type Props = {
  market: ParsedSupportedMarket;
  apiBase: string;
};

type PanelState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
};

const INITIAL = { loading: false, data: null, error: null };

export function SignalPanels({ market, apiBase }: Props) {
  const [arb, setArb] = useState<PanelState<ArbitrageSignalResponse>>(INITIAL);
  const [dutch, setDutch] = useState<PanelState<DutchingSignalResponse>>(INITIAL);
  const [smart, setSmart] = useState<PanelState<SmartMoneySignalResponse>>(INITIAL);
  const [forecast, setForecast] = useState<PanelState<ForecastSignalResponse>>(INITIAL);
  const [openPanel, setOpenPanel] = useState<string | null>("arbitrage");

  const signalReady = Boolean(apiBase.trim()) && !market.manualOnly;

  useEffect(() => {
    if (!signalReady) {
      return;
    }
    void loadPanel("arbitrage", setArb, fetchArbitrageSignal);
    void loadPanel("dutching", setDutch, fetchDutchingSignal);
    void loadPanel("smart-money", setSmart, fetchSmartMoneySignal);
    void loadPanel("forecast", setForecast, fetchForecastSignal);
  }, [apiBase, market.externalId, market.platform, signalReady]);

  async function loadPanel<T>(
    _id: string,
    setter: (value: PanelState<T>) => void,
    fetcher: (input: {
      apiBase: string;
      platform: string;
      marketId: string;
    }) => Promise<T | null>,
  ) {
    setter({ loading: true, data: null, error: null });
    try {
      const data = await fetcher({
        apiBase,
        platform: market.platform,
        marketId: market.externalId,
      });
      setter({ loading: false, data, error: null });
    } catch (error) {
      setter({
        loading: false,
        data: null,
        error: error instanceof Error ? error.message : "Request failed.",
      });
    }
  }

  if (market.manualOnly) {
    return (
      <section className="ae-signals">
        <p className="ae-signal-note">
          FanDuel manual capture only — automated signal panels are disabled on this page.
        </p>
        <p className="ae-signal-footer">{SIGNAL_PANEL_DISCLAIMER}</p>
      </section>
    );
  }

  return (
    <section className="ae-signals">
      <SignalPanel
        id="arbitrage"
        title="Arbitrage"
        open={openPanel === "arbitrage"}
        onToggle={() => setOpenPanel(openPanel === "arbitrage" ? null : "arbitrage")}
        loading={arb.loading}
        error={arb.error}
      >
        <ArbitrageBody data={arb.data} />
      </SignalPanel>

      <SignalPanel
        id="dutching"
        title="Dutching"
        open={openPanel === "dutching"}
        onToggle={() => setOpenPanel(openPanel === "dutching" ? null : "dutching")}
        loading={dutch.loading}
        error={dutch.error}
      >
        <DutchingBody data={dutch.data} />
      </SignalPanel>

      <SignalPanel
        id="smart-money"
        title="Smart Money"
        open={openPanel === "smart-money"}
        onToggle={() => setOpenPanel(openPanel === "smart-money" ? null : "smart-money")}
        loading={smart.loading}
        error={smart.error}
      >
        <SmartMoneyBody data={smart.data} />
      </SignalPanel>

      <SignalPanel
        id="forecast"
        title="Forecast"
        open={openPanel === "forecast"}
        onToggle={() => setOpenPanel(openPanel === "forecast" ? null : "forecast")}
        loading={forecast.loading}
        error={forecast.error}
      >
        <ForecastBody data={forecast.data} />
      </SignalPanel>

      <p className="ae-signal-footer">{SIGNAL_PANEL_DISCLAIMER}</p>
    </section>
  );
}

type PanelProps = {
  id: string;
  title: string;
  open: boolean;
  loading: boolean;
  error: string | null;
  onToggle: () => void;
  children: ReactNode;
};

function SignalPanel({ title, open, loading, error, onToggle, children }: PanelProps) {
  return (
    <div className="ae-signal-panel">
      <button type="button" className="ae-signal-toggle" onClick={onToggle} aria-expanded={open}>
        <span>{title}</span>
        <span>{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div className="ae-signal-body">
          {loading ? <p className="ae-signal-muted">Loading…</p> : null}
          {error ? <p className="ae-signal-error">{error}</p> : null}
          {!loading && !error ? children : null}
        </div>
      ) : null}
    </div>
  );
}

function ArbitrageBody({ data }: { data: ArbitrageSignalResponse | null }) {
  const signal = data?.signal;
  if (!signal?.is_arbitrage) {
    return <p className="ae-signal-muted">No signal detected</p>;
  }
  const edgePct = ((signal.net_spread ?? 0) * 100).toFixed(2);
  return (
    <div className="ae-signal-grid">
      <div>
        <span>Net edge</span>
        <strong>{edgePct}%</strong>
      </div>
      <div>
        <span>Confidence</span>
        <strong>{pct(signal.confidence)}</strong>
      </div>
      <div className="ae-signal-span">
        <span>YES leg</span>
        <strong>
          {signal.yes_leg?.market?.platform}/{signal.yes_leg?.market?.market_id} @{" "}
          {price(signal.yes_leg?.price)}
        </strong>
      </div>
      <div className="ae-signal-span">
        <span>NO leg</span>
        <strong>
          {signal.no_leg?.market?.platform}/{signal.no_leg?.market?.market_id} @{" "}
          {price(signal.no_leg?.price)}
        </strong>
      </div>
    </div>
  );
}

function DutchingBody({ data }: { data: DutchingSignalResponse | null }) {
  const signal = data?.signal;
  if (!signal?.risk_free) {
    return <p className="ae-signal-muted">No signal detected</p>;
  }
  return (
    <div className="ae-signal-grid">
      <div>
        <span>Combined implied</span>
        <strong>{price(signal.combined_implied ?? signal.total_cost)}</strong>
      </div>
      <div>
        <span>Return</span>
        <strong>{(signal.return_pct ?? 0).toFixed(2)}%</strong>
      </div>
      {(signal.outcomes ?? []).map((outcome) => (
        <div key={outcome.name} className="ae-signal-span">
          <span>{outcome.name}</span>
          <strong>
            {price(outcome.price)} · stake {pct(outcome.stake_share)}
          </strong>
        </div>
      ))}
    </div>
  );
}

function SmartMoneyBody({ data }: { data: SmartMoneySignalResponse | null }) {
  const positions = data?.positions ?? [];
  if (!positions.length) {
    return <p className="ae-signal-muted">No signal detected</p>;
  }
  return (
    <div className="ae-signal-list">
      {positions.slice(0, 4).map((position) => (
        <div key={`${position.holder_address}-${position.outcome}`} className="ae-signal-row">
          <span>{shortAddress(position.holder_address)}</span>
          <strong>
            {position.side?.toUpperCase()} {position.outcome} · PnL {money(position.total_pnl)}
          </strong>
        </div>
      ))}
    </div>
  );
}

function ForecastBody({ data }: { data: ForecastSignalResponse | null }) {
  const signal = data?.signal;
  if (!signal) {
    return <p className="ae-signal-muted">No signal detected</p>;
  }
  return (
    <div className="ae-signal-grid">
      <div>
        <span>Model</span>
        <strong>{pct(signal.model_prob)}</strong>
      </div>
      <div>
        <span>CLV</span>
        <strong>{signal.clv === null || signal.clv === undefined ? "—" : signedPct(signal.clv)}</strong>
      </div>
      <div>
        <span>Confidence</span>
        <strong>{pct(signal.confidence)}</strong>
      </div>
      <div className="ae-signal-span">
        <span>Gate</span>
        <strong>{signal.is_edge ? "Edge credited" : "CLV gate blocked"}</strong>
      </div>
    </div>
  );
}

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function signedPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

function price(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function shortAddress(value: string | undefined): string {
  if (!value) {
    return "holder";
  }
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

export const signalPanelStyles = `
  .ae-signals { display: grid; gap: 8px; margin-top: 12px; }
  .ae-signal-panel { border: 1px solid #232838; border-radius: 12px; background: #11141c; overflow: hidden; }
  .ae-signal-toggle {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    border: none;
    background: transparent;
    color: #eef1f7;
    padding: 10px 12px;
    font: 700 12px/1.2 inherit;
    cursor: pointer;
  }
  .ae-signal-body { border-top: 1px solid #232838; padding: 10px 12px; }
  .ae-signal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .ae-signal-grid div { display: grid; gap: 3px; }
  .ae-signal-grid span { color: #646c7e; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
  .ae-signal-grid strong { color: #eef1f7; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .ae-signal-span { grid-column: 1 / -1; }
  .ae-signal-list { display: grid; gap: 6px; }
  .ae-signal-row { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: #9aa3b5; }
  .ae-signal-row strong { color: #eef1f7; text-align: right; font-size: 11px; }
  .ae-signal-muted { margin: 0; color: #9aa3b5; font-size: 12px; }
  .ae-signal-error { margin: 0; color: #ff7a8f; font-size: 12px; }
  .ae-signal-note { margin: 0; color: #9aa3b5; font-size: 12px; line-height: 1.4; }
  .ae-signal-footer { margin: 4px 0 0; color: #646c7e; font-size: 10px; line-height: 1.35; }
`;
