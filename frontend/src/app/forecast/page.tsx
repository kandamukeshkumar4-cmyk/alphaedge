"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { hasLiveApi } from "@/lib/alphaedge-api";
import {
  createAnonymousForecaster,
  fetchBackfillMarkets,
  fetchForecastDashboard,
  lockForecast,
  type BackfillMarket,
  type BrierTrendPoint,
  type CalibrationBin,
  type CategoryEdge,
  type ForecastDashboard,
  type ForecastMode,
  type ForecastResponse,
  type PlatformEdge,
  type TimeBucketEdge,
} from "@/lib/forecast-mirror-api";
import { buildForecastDashboardView } from "@/lib/forecast-dashboard-view-model";
import { cn } from "@/lib/cn";

const TOKEN_STORAGE_KEY = "alphaedge.forecasterToken";
const DEFAULT_URL = "https://polymarket.com/event/lakers-celtics";

type Notice = {
  tone: "success" | "error" | "muted";
  text: string;
};

export default function ForecastMirrorPage() {
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [forecasterId, setForecasterId] = useState("");
  const [marketUrl, setMarketUrl] = useState(DEFAULT_URL);
  const [marketTitle, setMarketTitle] = useState("");
  const [outcomeLabel, setOutcomeLabel] = useState("YES");
  const [userProbability, setUserProbability] = useState("64");
  const [marketProbability, setMarketProbability] = useState("58");
  const [mode, setMode] = useState<ForecastMode>("live");
  const [dashboard, setDashboard] = useState<ForecastDashboard | null>(null);
  const [backfillMarkets, setBackfillMarkets] = useState<BackfillMarket[]>([]);
  const [lastForecast, setLastForecast] = useState<ForecastResponse | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);
  const [isLocking, setIsLocking] = useState(false);

  const apiConfigured = hasLiveApi();
  const dashboardView = useMemo(() => buildForecastDashboardView(dashboard), [dashboard]);

  const profileLabel = useMemo(() => {
    if (forecasterId) {
      return shortId(forecasterId);
    }
    if (token) {
      return "Stored";
    }
    return "None";
  }, [forecasterId, token]);

  useEffect(() => {
    const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
    setToken(storedToken);
    setTokenDraft(storedToken);
    if (storedToken) {
      void loadDashboard(storedToken);
    }
    if (apiConfigured) {
      void loadBackfillMarkets();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfigured]);

  async function loadDashboard(nextToken = token) {
    if (!apiConfigured || !nextToken.trim()) {
      setDashboard(null);
      return;
    }
    setIsLoadingDashboard(true);
    setNotice(null);
    try {
      const nextDashboard = await fetchForecastDashboard({
        token: nextToken.trim(),
      });
      setDashboard(nextDashboard);
      setForecasterId(nextDashboard.forecaster_id);
    } catch (error) {
      setDashboard(null);
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setIsLoadingDashboard(false);
    }
  }

  async function loadBackfillMarkets() {
    try {
      setBackfillMarkets(await fetchBackfillMarkets());
    } catch {
      setBackfillMarkets([]);
    }
  }

  async function handleCreateForecaster() {
    if (!apiConfigured) {
      setNotice({ tone: "error", text: "Backend API URL is not configured." });
      return;
    }
    setIsCreating(true);
    setNotice(null);
    try {
      const forecaster = await createAnonymousForecaster();
      window.localStorage.setItem(TOKEN_STORAGE_KEY, forecaster.token);
      setToken(forecaster.token);
      setTokenDraft(forecaster.token);
      setForecasterId(forecaster.id);
      await loadDashboard(forecaster.token);
      setNotice({ tone: "success", text: "Forecaster profile created." });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setIsCreating(false);
    }
  }

  function handleLoadToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextToken = tokenDraft.trim();
    setToken(nextToken);
    setForecasterId("");
    if (nextToken) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
      void loadDashboard(nextToken);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      setDashboard(null);
    }
  }

  async function handleLockForecast(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token.trim()) {
      setNotice({ tone: "error", text: "Forecaster token required." });
      return;
    }

    const parsedUserProbability = parsePercent(userProbability);
    const marketProbabilityText = marketProbability.trim();
    const parsedMarketProbability = marketProbabilityText
      ? parsePercent(marketProbabilityText)
      : null;
    if (parsedUserProbability === null || (marketProbabilityText && parsedMarketProbability === null)) {
      setNotice({ tone: "error", text: "Probabilities must be 0 to 100." });
      return;
    }

    setIsLocking(true);
    setNotice(null);
    try {
      const forecast = await lockForecast({
        token: token.trim(),
        url: marketUrl.trim(),
        userProbability: parsedUserProbability,
        marketImpliedProbability: parsedMarketProbability,
        marketTitle: marketTitle.trim() || undefined,
        outcomeLabel: outcomeLabel.trim() || "YES",
        mode,
      });
      setLastForecast(forecast);
      await loadDashboard(token.trim());
      setNotice({ tone: "success", text: `Forecast #${forecast.seq} locked.` });
    } catch (error) {
      setNotice({ tone: "error", text: errorText(error) });
    } finally {
      setIsLocking(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 py-6 sm:px-5">
      <header className="grid gap-4 border-b border-border pb-5 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.14em] text-primary">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.8)]" />
            Smart Clone · Forecast
          </p>
          <h1 className="mt-2 text-2xl font-black tracking-normal text-text sm:text-3xl">
            AlphaEdge Mirror
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            Research only — analysis assistant. No betting execution, payments,
            account scraping, or copy trading.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.08em]">
            <StatusPill label="Mode" value="research" />
            <StatusPill label="Profile" value={profileLabel} />
            <StatusPill label="Guard" value={dashboard?.paper_trading_only ? "paper-only APIs" : "paper-only"} />
          </div>
        </div>

        <form className="flex flex-col gap-2" onSubmit={handleLoadToken}>
          <label className="sr-only" htmlFor="forecaster-token">
            Forecaster token
          </label>
          <div className="flex gap-2">
            <input
              id="forecaster-token"
              className="min-h-11 min-w-0 flex-1 rounded border border-border bg-surface px-3 font-mono text-xs text-text outline-none transition placeholder:text-muted-2 focus:border-primary"
              type="text"
              autoComplete="off"
              placeholder="Forecaster token"
              value={tokenDraft}
              onChange={(event) => setTokenDraft(event.target.value)}
            />
            <button
              className="inline-flex min-h-11 items-center gap-2 rounded border border-border-light px-4 text-sm font-semibold text-text transition hover:border-primary hover:text-primary"
              title="Load token"
              type="submit"
            >
              <RefreshIcon />
              Load
            </button>
          </div>
        </form>
      </header>

      {notice ? <NoticeBanner notice={notice} /> : null}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <section className="rounded border border-border bg-surface p-4 shadow-card">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-black uppercase tracking-[0.08em] text-text">
                Profile
              </h2>
              <button
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-black text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isCreating || !apiConfigured}
                title="Create forecaster profile"
                type="button"
                onClick={() => void handleCreateForecaster()}
              >
                <PlusIcon />
                {isCreating ? "Creating" : "Create"}
              </button>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <DetailStat label="Forecaster" value={profileLabel} />
              <DetailStat label="API" value={apiConfigured ? "Live" : "Local"} />
            </dl>
          </section>

          <section className="rounded border border-border bg-surface p-4 shadow-card">
            <h2 className="text-sm font-black uppercase tracking-[0.08em] text-text">
              Lock Forecast
            </h2>
            <form className="mt-4 flex flex-col gap-3" onSubmit={handleLockForecast}>
              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-2">
                Market URL
                <input
                  className="min-h-11 rounded border border-border bg-bg px-3 font-mono text-xs normal-case tracking-normal text-text outline-none transition placeholder:text-muted-2 focus:border-primary"
                  value={marketUrl}
                  onChange={(event) => setMarketUrl(event.target.value)}
                />
              </label>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-2">
                Market Title
                <input
                  className="min-h-11 rounded border border-border bg-bg px-3 text-sm normal-case tracking-normal text-text outline-none transition placeholder:text-muted-2 focus:border-primary"
                  placeholder="Optional for manual capture"
                  value={marketTitle}
                  onChange={(event) => setMarketTitle(event.target.value)}
                />
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-2">
                  P(YES)
                  <input
                    className="min-h-11 rounded border border-border bg-bg px-3 font-mono text-sm normal-case tracking-normal text-text outline-none transition focus:border-primary"
                    inputMode="decimal"
                    value={userProbability}
                    onChange={(event) => setUserProbability(event.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-2">
                  Market
                  <input
                    className="min-h-11 rounded border border-border bg-bg px-3 font-mono text-sm normal-case tracking-normal text-text outline-none transition focus:border-primary"
                    inputMode="decimal"
                    value={marketProbability}
                    onChange={(event) => setMarketProbability(event.target.value)}
                  />
                </label>
              </div>

              <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.08em] text-muted-2">
                Outcome Label
                <input
                  className="min-h-11 rounded border border-border bg-bg px-3 text-sm normal-case tracking-normal text-text outline-none transition focus:border-primary"
                  value={outcomeLabel}
                  onChange={(event) => setOutcomeLabel(event.target.value)}
                />
              </label>

              <div className="grid grid-cols-2 gap-2 rounded bg-bg p-1">
                {(["live", "practice"] as ForecastMode[]).map((nextMode) => (
                  <button
                    key={nextMode}
                    className={cn(
                      "min-h-10 rounded-lg px-3 text-sm font-bold capitalize transition",
                      mode === nextMode
                        ? "bg-accent text-white"
                        : "text-muted hover:bg-surface-2 hover:text-text",
                    )}
                    type="button"
                    onClick={() => setMode(nextMode)}
                  >
                    {nextMode}
                  </button>
                ))}
              </div>

              <button
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded border border-primary/45 px-4 text-sm font-black text-primary transition hover:border-primary hover:text-accent disabled:cursor-not-allowed disabled:border-border disabled:text-muted-2"
                disabled={isLocking || !apiConfigured}
                title="Lock forecast"
                type="submit"
              >
                <LockIcon />
                {isLocking ? "Locking" : "Lock"}
              </button>
            </form>

            {lastForecast ? (
              <div className="mt-4 rounded bg-bg p-3 text-sm">
                <div className="font-mono text-xs uppercase tracking-[0.08em] text-muted-2">
                  Forecast #{lastForecast.seq}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <SmallPill value={`${formatPercent(lastForecast.user_probability)} user`} />
                  <SmallPill
                    value={`${formatPercent(lastForecast.market_implied_probability)} market`}
                  />
                  <SmallPill value={lastForecast.is_independent ? "independent" : "anchored"} />
                </div>
              </div>
            ) : null}
          </section>
        </div>

        <div className="min-w-0 space-y-5">
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {dashboardView.summaryCards.map((card) => (
              <Metric key={card.label} label={card.label} value={card.value} />
            ))}
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader
                title="Calibration"
                actionLabel={isLoadingDashboard ? "Loading" : "Refresh"}
                onAction={() => void loadDashboard()}
              />
              <div className="p-4">
                <CalibrationTable bins={dashboard?.calibration ?? []} />
              </div>
            </div>

            <aside className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Track Record" />
              <div className="space-y-3 p-4">
                <DetailStat
                  label="Independent"
                  value={countLabel(dashboard?.live.independent_count)}
                />
                <DetailStat label="Anchored" value={countLabel(dashboard?.live.anchored_count)} />
                <DetailStat label="Headline" value={countLabel(dashboard?.live.headline_count)} />
                <DetailStat label="Edge" value={scoreLabel(dashboard?.live.mean_brier_delta)} />
                <DetailStat
                  label="Synthetic PnL"
                  value={moneyLabel(dashboard?.live.synthetic_pnl_total)}
                />
                <DetailStat
                  label="Practice"
                  value={`${countLabel(dashboard?.practice.resolved_count)} resolved`}
                />
                <ProvisionalFlags labels={dashboardView.qualityLabels} loaded={Boolean(dashboard)} />
              </div>
            </aside>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Brier Trend" />
              <BrierTrend trend={dashboardView.brierTrend} />
            </div>
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Timing" />
              <TimeBreakdown rows={dashboardView.timeBreakdown} />
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Categories" />
              <CategoryTable categories={dashboard?.category_breakdown ?? []} />
            </div>
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Platforms" />
              <PlatformTable platforms={dashboardView.platformBreakdown} />
            </div>
            <div className="rounded border border-border bg-surface shadow-card">
              <PanelHeader title="Practice Markets" />
              <BackfillList markets={backfillMarkets} />
            </div>
          </section>
        </div>
      </section>

      {dashboard?.disclaimer ? (
        <p className="text-xs leading-5 text-muted-2">{dashboard.disclaimer}</p>
      ) : null}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-surface p-4 shadow-card">
      <div className="text-xs font-bold uppercase tracking-[0.08em] text-muted-2">{label}</div>
      <div className="mt-2 min-h-8 font-mono text-2xl font-black text-text">{value}</div>
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-bg p-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted-2">
        {label}
      </div>
      <div className="mt-2 break-words font-mono text-sm font-bold text-text">{value}</div>
    </div>
  );
}

function PanelHeader({
  title,
  actionLabel,
  onAction,
}: {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex min-h-12 items-center justify-between gap-3 border-b border-border px-4">
      <h2 className="text-sm font-black uppercase tracking-[0.08em] text-text">{title}</h2>
      {actionLabel && onAction ? (
        <button
          className="inline-flex min-h-9 items-center gap-2 rounded border border-border-light px-3 text-xs font-bold text-muted transition hover:border-primary hover:text-primary"
          title={actionLabel}
          type="button"
          onClick={onAction}
        >
          <RefreshIcon />
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function CalibrationTable({ bins }: { bins: CalibrationBin[] }) {
  if (!bins.length) {
    return <EmptyState text="No calibration bins yet." />;
  }

  return (
    <div className="space-y-3">
      {bins.map((bin) => {
        const observed = bin.observed_frequency;
        const observedWidth = observed === null ? 0 : Math.max(4, observed * 100);
        return (
          <div
            key={`${bin.lower}-${bin.upper}`}
            className="grid gap-3 rounded border border-border bg-bg p-3 sm:grid-cols-[92px_minmax(0,1fr)_112px]"
          >
            <div className="font-mono text-xs font-bold text-text">
              {formatPercent(bin.lower)}-{formatPercent(bin.upper)}
            </div>
            <div className="min-w-0">
              <div className="h-2 overflow-hidden rounded bg-surface-3">
                {observed !== null ? (
                  <div
                    className="h-full rounded bg-primary"
                    style={{ width: `${observedWidth}%` }}
                  />
                ) : null}
              </div>
              <div className="mt-2 text-xs text-muted">
                Pred {formatPercent(bin.mean_predicted)} / Obs{" "}
                {formatPercent(bin.observed_frequency)}
              </div>
            </div>
            <div className="text-right font-mono text-xs text-muted">{bin.count} forecasts</div>
          </div>
        );
      })}
    </div>
  );
}

function CategoryTable({ categories }: { categories: CategoryEdge[] }) {
  if (!categories.length) {
    return <EmptyState text="No scored categories yet." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-left text-sm">
        <thead className="border-b border-border bg-bg text-xs uppercase tracking-[0.08em] text-muted-2">
          <tr>
            <th className="px-4 py-3 font-bold">Category</th>
            <th className="px-4 py-3 font-bold">Count</th>
            <th className="px-4 py-3 font-bold">Delta</th>
            <th className="px-4 py-3 font-bold">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {categories.map((category) => (
            <tr key={category.category}>
              <td className="px-4 py-3 font-semibold text-text">{category.category}</td>
              <td className="px-4 py-3 font-mono text-muted">{category.count}</td>
              <td className="px-4 py-3 font-mono text-muted">
                {scoreLabel(category.mean_brier_delta)}
              </td>
              <td className="px-4 py-3 font-mono text-muted">
                {category.provisional ? "provisional" : "stable"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlatformTable({ platforms }: { platforms: PlatformEdge[] }) {
  if (!platforms.length) {
    return <EmptyState text="No platform scores yet." />;
  }

  return (
    <div className="divide-y divide-border">
      {platforms.map((platform) => (
        <div
          key={platform.platform}
          className="grid grid-cols-[minmax(0,1fr)_64px_96px] gap-3 px-4 py-3 text-sm"
        >
          <div className="font-semibold capitalize text-text">{platform.platform}</div>
          <div className="font-mono text-muted">{platform.count}</div>
          <div className="text-right font-mono text-muted">
            {scoreLabel(platform.mean_brier_delta)}
          </div>
        </div>
      ))}
    </div>
  );
}

function TimeBreakdown({ rows }: { rows: TimeBucketEdge[] }) {
  if (!rows.length) {
    return <EmptyState text="No timing buckets yet." />;
  }

  const maxCount = Math.max(1, ...rows.map((row) => row.count));
  return (
    <div className="space-y-3 p-4">
      {rows.map((row) => (
        <div key={row.bucket} className="grid gap-3 sm:grid-cols-[64px_minmax(0,1fr)_92px]">
          <div className="font-mono text-xs font-bold text-text">{row.bucket}</div>
          <div className="min-w-0">
            <div className="h-2 overflow-hidden rounded bg-surface-3">
              <div
                className="h-full rounded bg-primary"
                style={{ width: `${Math.max(4, (row.count / maxCount) * 100)}%` }}
              />
            </div>
          </div>
          <div className="text-right font-mono text-xs text-muted">
            {row.count} / {scoreLabel(row.mean_brier_delta)}
          </div>
        </div>
      ))}
    </div>
  );
}

function BrierTrend({ trend }: { trend: BrierTrendPoint[] }) {
  if (!trend.length) {
    return <EmptyState text="No headline Brier trend yet." />;
  }

  return (
    <div className="space-y-3 p-4">
      {trend.slice(-12).map((point) => {
        const width = `${Math.max(3, Math.min(100, point.user_brier * 100))}%`;
        return (
          <div
            key={`${point.seq}-${point.locked_at}`}
            className="grid gap-3 rounded border border-border bg-bg p-3 sm:grid-cols-[48px_minmax(0,1fr)_92px]"
          >
            <div className="font-mono text-xs font-bold text-text">#{point.seq}</div>
            <div className="min-w-0">
              <div className="h-2 overflow-hidden rounded bg-surface-3">
                <div className="h-full rounded bg-primary" style={{ width }} />
              </div>
              <div className="mt-2 text-xs text-muted">
                Market {scoreLabel(point.market_brier)}
              </div>
            </div>
            <div className="text-right font-mono text-xs text-muted">
              {scoreLabel(point.user_brier)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BackfillList({ markets }: { markets: BackfillMarket[] }) {
  if (!markets.length) {
    return <EmptyState text="No practice markets loaded." />;
  }

  return (
    <div className="divide-y divide-border">
      {markets.slice(0, 5).map((market) => (
        <a
          key={market.id}
          className="block px-4 py-3 transition hover:bg-bg"
          href={market.url}
          rel="noreferrer"
          target="_blank"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-text">{market.title}</div>
              <div className="mt-1 font-mono text-xs text-muted-2">{market.platform}</div>
            </div>
            <span className="shrink-0 rounded border border-border-light px-2 py-1 text-xs font-bold text-muted">
              {market.category}
            </span>
          </div>
        </a>
      ))}
    </div>
  );
}

function ProvisionalFlags({ labels, loaded }: { labels: string[]; loaded: boolean }) {
  if (!loaded) {
    return <SmallPill value="No dashboard loaded" />;
  }
  if (!labels.length) {
    return <SmallPill value="Samples stable" />;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {labels.map((label) => (
        <SmallPill key={label} value={label} />
      ))}
    </div>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded border border-border bg-surface px-2.5 py-1 text-muted">
      <span className="text-muted-2">{label}</span>
      <span className="font-mono text-primary">{value}</span>
    </span>
  );
}

function SmallPill({ value }: { value: string }) {
  return (
    <span className="rounded border border-border-light bg-surface-2 px-2 py-1 text-xs font-bold text-muted">
      {value}
    </span>
  );
}

function NoticeBanner({ notice }: { notice: Notice }) {
  const classes =
    notice.tone === "success"
      ? "border-primary/45 bg-primary-dim text-primary"
      : notice.tone === "error"
        ? "border-danger/45 bg-danger-dim text-danger"
        : "border-border bg-surface text-muted";
  return <div className={cn("rounded border px-4 py-3 text-sm font-semibold", classes)}>{notice.text}</div>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="p-4 text-sm text-muted">{text}</div>;
}

function parsePercent(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
    return null;
  }
  return parsed / 100;
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function scoreLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return value.toFixed(4);
}

function countLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? "0" : value.toLocaleString();
}

function moneyLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "$0.00";
  }
  return `$${value.toFixed(2)}`;
}

function shortId(value: string): string {
  return value.length > 8 ? value.slice(0, 8) : value;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

function PlusIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14M5 12h14" strokeLinecap="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 11V8a5 5 0 0 1 10 0v3" strokeLinecap="round" />
      <path d="M6 11h12v10H6z" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 12a8 8 0 0 1-14.6 4.5" strokeLinecap="round" />
      <path d="M4 12A8 8 0 0 1 18.6 7.5" strokeLinecap="round" />
      <path d="M18 3v5h-5M6 21v-5h5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
