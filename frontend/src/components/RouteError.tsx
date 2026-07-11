import Link from "next/link";
import { cn } from "@/lib/cn";

/*
 * Shared route-level error fallback (Loop V13 U01). Rendered by every Next
 * App Router `error.tsx` / `global-error.tsx` boundary so a client render error
 * shows a friendly Quest-styled panel with a retry instead of a white screen.
 * ONE component so the boundaries never diverge. All styling flows through the
 * central Tailwind tokens (bg/surface/border/danger/primary/muted) — no hex.
 */
export function RouteError({
  reset,
  title = "Something went wrong",
  description = "This section hit an unexpected error. Your paper-trading data is safe — try again, or head back home.",
  error,
  className,
}: {
  /** Next.js error boundary reset — re-renders the failed segment. */
  reset?: () => void;
  title?: string;
  description?: string;
  error?: Error & { digest?: string };
  className?: string;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="route-error"
      className={cn(
        "mx-auto flex min-h-[60vh] max-w-[560px] flex-col items-center justify-center px-4 py-12 text-center",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-danger/40 bg-danger-dim">
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-danger"
          aria-hidden
        >
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        </svg>
      </div>
      <h1 className="mt-5 text-xl font-black tracking-tight text-text sm:text-2xl">{title}</h1>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">{description}</p>
      {error?.digest ? (
        <p className="mt-3 font-mono text-[11px] text-muted-2">Ref: {error.digest}</p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {reset ? (
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-[0_0_16px_rgba(45,212,191,0.25)] transition hover:brightness-110"
          >
            Try again
          </button>
        ) : null}
        <Link
          href="/"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-bold text-muted transition hover:border-border-light hover:text-text"
        >
          Back home
        </Link>
      </div>
    </div>
  );
}
