import { marketHref } from "@/lib/market-href";
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
    <section className="rounded-2xl border border-border bg-surface">
      <div className="flex items-center justify-between">
        <h2 className="px-4 pt-4 text-[12px] font-black uppercase tracking-[0.12em] text-text">
          {title}
        </h2>
        <Link
          href="/markets"
          className="mr-4 mt-4 text-xs font-black text-muted transition hover:text-accent"
        >
          See all
        </Link>
      </div>
      <ol className="mt-3 divide-y divide-border">
        {rows.map((row, i) => (
          <li key={`${title}-${row.slug}`}>
            <Link
              href={marketHref(row.slug)}
              className="grid grid-cols-[26px_minmax(0,1fr)_auto] items-center gap-2.5 px-4 py-3 text-sm transition hover:bg-surface-2"
            >
              <span className="font-mono text-xs font-black text-muted-2">{i + 1}</span>
              <span className="truncate font-semibold text-text">{row.title}</span>
              <span className="flex items-center justify-end gap-1.5">
                <span className="font-mono text-sm font-black text-accent tabular">{row.value}</span>
                <Delta value={row.delta} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
