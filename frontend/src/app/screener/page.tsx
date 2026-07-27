import { ScreenerShell } from "@/components/screener/ScreenerShell";

/**
 * Loop V85 (L2) — /screener page. Dense, sortable table of paper markets
 * ranked by forecast edge (market-baseline). Read-only research surface. Paper trading only.
 */
export default function ScreenerPage() {
  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-[1200px] px-4 py-8">
        <ScreenerShell />
      </div>
    </main>
  );
}
