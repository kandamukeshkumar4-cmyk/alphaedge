import Link from "next/link";

import { cn } from "@/lib/cn";
import type { LibraryItem } from "@/lib/library-api";

const KIND_TONE: Record<LibraryItem["kind"], string> = {
  brief: "border-secondary/30 bg-secondary-dim text-secondary",
  report: "border-gold/30 bg-gold/10 text-gold",
  scanner: "border-primary/30 bg-primary-dim text-primary",
  alpha: "border-accent/30 bg-accent-dim text-accent-bright",
  workflow: "border-border-light bg-surface-2 text-text",
};

function formatDate(value: string | null): string {
  if (!value) return "Date not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function LibraryCard({ item }: { item: LibraryItem }) {
  return (
    <li
      className="group relative border-b border-border/70 last:border-0"
      data-testid="library-card"
      data-kind={item.kind}
    >
      <article className="grid gap-3 p-4 sm:grid-cols-[132px_minmax(0,1fr)_auto] sm:items-start sm:gap-5 sm:p-5">
        <header>
          <span
            className={cn(
              "inline-flex rounded-full border px-2.5 py-1 font-mono text-[10px] font-black uppercase tracking-[0.1em]",
              KIND_TONE[item.kind],
            )}
          >
            {item.label}
          </span>
          <time
            dateTime={item.timestamp ?? undefined}
            className="mt-2 block font-mono text-[11px] text-muted-2"
          >
            {formatDate(item.timestamp)}
          </time>
        </header>

        <section className="min-w-0">
          <Link
            href={item.href}
            className="text-base font-black leading-snug text-text outline-none transition group-hover:text-primary focus-visible:rounded focus-visible:ring-2 focus-visible:ring-primary"
          >
            {item.title}
          </Link>
          <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-muted">
            {item.summary}
          </p>
          <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={`${item.title} details`}>
            {item.status ? (
              <li className="rounded-full border border-border bg-bg px-2.5 py-1 font-mono text-[10px] text-text">
                {item.status.replaceAll("_", " ")}
              </li>
            ) : null}
            {item.details.map((detail) => (
              <li
                key={detail}
                className="rounded-full border border-border bg-surface-2 px-2.5 py-1 font-mono text-[10px] text-muted"
              >
                {detail}
              </li>
            ))}
          </ul>
        </section>

        <Link
          href={item.href}
          aria-label={`Open ${item.title}`}
          className="inline-flex min-h-11 items-center justify-center self-center rounded-xl border border-border px-3 py-2 text-xs font-black text-muted outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary sm:self-start"
          data-testid="library-open"
        >
          Open
        </Link>
      </article>
    </li>
  );
}
