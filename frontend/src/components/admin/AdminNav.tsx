"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const LINKS = [
  { label: "Overview", href: "/admin" },
  { label: "Markets", href: "/admin#markets" },
  { label: "Jobs", href: "/admin#jobs" },
  { label: "Users", href: "/admin#users" },
] as const;

export function AdminNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1">
      <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-[0.14em] text-muted-2">
        Admin
      </p>
      {LINKS.map((link) => {
        // Only the exact Overview link is highlighted on /admin; the hash
        // links (Markets/Jobs) are in-page anchors and shouldn't all light up.
        const active = link.href === "/admin" && pathname === "/admin";

        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "rounded-lg px-3 py-2 text-sm font-medium transition",
              active
                ? "bg-primary-dim text-primary"
                : "text-muted hover:bg-surface-2 hover:text-text",
            )}
          >
            {link.label}
          </Link>
        );
      })}
      <div className="my-3 border-t border-border" />
      <Link
        href="/admin/calibration"
        className={cn(
          "rounded-lg px-3 py-2 text-sm font-medium transition",
          pathname === "/admin/calibration"
            ? "bg-primary-dim text-primary"
            : "text-muted hover:bg-surface-2 hover:text-text",
        )}
      >
        Calibration
      </Link>
      <Link
        href="/admin/resolve"
        className={cn(
          "rounded-lg px-3 py-2 text-sm font-medium transition",
          pathname === "/admin/resolve"
            ? "bg-primary-dim text-primary"
            : "text-muted hover:bg-surface-2 hover:text-text",
        )}
      >
        Resolve
      </Link>
      <Link
        href="/admin/proof"
        className={cn(
          "rounded-lg px-3 py-2 text-sm font-medium transition",
          pathname === "/admin/proof"
            ? "bg-primary-dim text-primary"
            : "text-muted hover:bg-surface-2 hover:text-text",
        )}
      >
        Agent Proof
      </Link>
      <Link
        href="/admin/observability"
        className={cn(
          "rounded-lg px-3 py-2 text-sm font-medium transition",
          pathname === "/admin/observability"
            ? "bg-primary-dim text-primary"
            : "text-muted hover:bg-surface-2 hover:text-text",
        )}
      >
        Observability
      </Link>
    </nav>
  );
}
