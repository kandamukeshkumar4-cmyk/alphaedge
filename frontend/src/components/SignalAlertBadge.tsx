"use client";

import { cn } from "@/lib/cn";

type SignalAlertBadgeProps = {
  count: number;
  className?: string;
};

export function SignalAlertBadge({ count, className }: SignalAlertBadgeProps) {
  if (count <= 0) {
    return null;
  }

  const label = count > 9 ? "9+" : String(count);

  return (
    <span
      className={cn(
        "pointer-events-none absolute -right-1.5 -top-1.5 grid min-h-[16px] min-w-[16px] place-items-center rounded-full bg-danger px-1 text-[9px] font-black leading-none text-white shadow-[0_0_0_2px_#0a0b0d]",
        count === 1 && "h-2 w-2 min-h-0 min-w-0 p-0",
        className,
      )}
      aria-label={`${count} unread signal${count === 1 ? "" : "s"}`}
    >
      {count > 1 ? label : null}
    </span>
  );
}
