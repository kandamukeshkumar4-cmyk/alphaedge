"use client";

import { AdminMarketsTable } from "@/components/admin/AdminMarketsTable";
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
          WC2026 market seeding, resolution, catalog status, and worker health.
        </p>
      </header>

      <WC2026AdminCard apiKey={apiKey} />
      <AdminMarketsTable apiKey={apiKey} />
      <SystemHealthCard apiKey={apiKey} />
    </>
  );
}
