import { UsageDashboard } from "./UsageDashboard";

/**
 * Loop V85 (D-U2, G2) — /usage: 14-day paper research activity.
 * Ambient glows + fine desk grid sit behind the dashboard; every layer is
 * pointer-events-none so the chart and table stay fully interactive.
 */
export default function UsagePage() {
  return (
    <main data-testid="usage-page" className="relative min-h-screen overflow-hidden bg-bg">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {/* Mint desk-lamp glow up top, faint blue spill off the right edge. */}
        <div className="absolute inset-0 bg-[radial-gradient(58%_42%_at_50%_-6%,rgba(0,232,176,0.09),transparent_70%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(40%_36%_at_88%_18%,rgba(75,158,255,0.05),transparent_72%)]" />
        {/* Fine grid, faded out toward the bottom of the fold. */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(28,44,40,0.22)_1px,transparent_1px),linear-gradient(to_bottom,rgba(28,44,40,0.22)_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(70%_60%_at_50%_0%,black,transparent)]" />
      </div>
      <div className="relative mx-auto max-w-[1100px] px-4 py-8 lg:py-12">
        <UsageDashboard />
      </div>
    </main>
  );
}
