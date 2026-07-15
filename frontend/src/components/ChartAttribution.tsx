/**
 * TradingView attribution placed OUTSIDE any role="img" chart shell.
 * lightweight-charts injects #tv-attr-logo inside the canvas container by
 * default; we disable that (attributionLogo: false) to avoid axe
 * nested-interactive, and fulfill the license link requirement here instead.
 */
export function ChartAttribution({ className = "" }: { className?: string }) {
  return (
    <p className={`text-[10px] text-muted-2 ${className}`.trim()}>
      Charts by{" "}
      <a
        href="https://www.tradingview.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="underline decoration-border underline-offset-2 hover:text-muted"
      >
        TradingView
      </a>
    </p>
  );
}
