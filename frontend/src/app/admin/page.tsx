"use client";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminPage() {
  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">Admin</h1>
      <p className="mt-2 text-sm text-slate-400">
        Agent toggle, manual run, lock/resolve — uses admin API key server-side in production.
      </p>
      <ul className="mt-6 space-y-2 text-sm">
        <li>API health: {API}/health</li>
        <li>Run agent: POST {API}/admin/agents/run/nba-2025-01-15-lal-bos</li>
        <li>Create market: POST {API}/admin/markets</li>
      </ul>
    </main>
  );
}
