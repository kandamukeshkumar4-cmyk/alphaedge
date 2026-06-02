import Link from "next/link";
import type { RankRow } from "@/lib/mock-data";
import { Delta } from "./Delta";

export function DiscoveryRail({
  title,
  rows,
}: {
  title: string;
  rows: RankRow[];
}) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-black text-text">{title}</h2>
        <Link href="/markets" className="text-xs font-semibold text-accent hover:underline">
          See all ›
        </Link>
      </div>
      <ol className="mt-3 space-y-2.5">
        {rows.map((row, i) => (
          <li key={`${title}-${row.slug}`}>
            <Link
              href={`/markets/${row.slug}`}
              className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-md px-1 py-1 text-sm transition hover:bg-surface-2"
            >
              <span className="font-mono text-xs text-muted-2">{i + 1}</span>
              <span className="truncate text-text">{row.title}</span>
              <span className="flex items-center justify-end gap-1.5">
                <span className="font-mono text-xs font-bold text-text">{row.value}</span>
                <Delta value={row.delta} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
