"use client";

import { AdminMarketsTable } from "@/components/admin/AdminMarketsTable";
import { AdminStatsCard } from "@/components/admin/AdminStatsCard";
import { AdminUsersTable } from "@/components/admin/AdminUsersTable";
import { SystemHealthCard } from "@/components/admin/SystemHealthCard";
import { WC2026AdminCard } from "@/components/admin/WC2026AdminCard";
import { useAdminApiKey } from "@/lib/admin-context";

export default function AdminDashboardPage() {
  const apiKey = useAdminApiKey();

  return (
    <>
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
          Overview
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-text">
          Admin Dashboard
        </h1>
        <p className="mt-2 text-sm text-muted">
          Paper-market operations, system stats, user controls, and worker health.
        </p>
      </header>

      <AdminStatsCard apiKey={apiKey} />
      <WC2026AdminCard apiKey={apiKey} />
      <AdminMarketsTable apiKey={apiKey} />
      <AdminUsersTable apiKey={apiKey} />
      <SystemHealthCard apiKey={apiKey} />
    </>
  );
}
