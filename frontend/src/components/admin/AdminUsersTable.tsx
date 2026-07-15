"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  fetchAdminUsers,
  suspendAdminUser,
  unsuspendAdminUser,
  type AdminUserRow,
} from "@/lib/admin-dashboard-api";

export function AdminUsersTable({ apiKey }: { apiKey: string }) {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    if (!apiKey.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const result = await fetchAdminUsers(apiKey, { q: activeQuery, limit: 50 });
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setUsers([]);
      return;
    }
    setError(null);
    setUsers(result.data.users);
    setTotal(result.data.total);
  }, [activeQuery, apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveQuery(query.trim());
  }

  async function toggleSuspension(user: AdminUserRow) {
    if (!user.is_suspended && !window.confirm(`Suspend ${user.email}? Suspended users cannot place paper trades.`)) return;
    setActionId(user.id);
    setError(null);
    const result = user.is_suspended
      ? await unsuspendAdminUser(apiKey, user.id)
      : await suspendAdminUser(apiKey, user.id);
    setActionId(null);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setUsers((current) =>
      current.map((entry) => entry.id === user.id ? { ...entry, is_suspended: result.data.is_suspended } : entry),
    );
  }

  return (
    <section className="rounded-xl border border-border bg-surface" id="users">
      <header className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <section>
          <h2 className="text-sm font-black text-text">User administration</h2>
          <p className="mt-1 text-xs text-muted">{total.toLocaleString()} users · suspension blocks paper orders</p>
        </section>
        <form className="flex gap-2" onSubmit={submit}>
          <label className="sr-only" htmlFor="admin-user-search">Search users</label>
          <input id="admin-user-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search email or name" className="min-h-10 w-52 rounded-lg border border-border bg-bg px-3 text-xs text-text outline-none focus:border-accent" />
          <button type="submit" className="min-h-10 rounded-lg bg-accent px-3 text-xs font-black text-bg transition hover:brightness-110">Search</button>
        </form>
      </header>
      {error ? <p role="alert" className="p-4 text-sm text-danger">{error}</p> : (
        <section className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2"><tr><th className="px-4 py-3 font-semibold">User</th><th className="px-4 py-3 font-semibold">Balance</th><th className="px-4 py-3 font-semibold">Trades</th><th className="px-4 py-3 font-semibold">Status</th><th className="px-4 py-3 font-semibold">Action</th></tr></thead>
            <tbody className="divide-y divide-border">
              {loading ? <tr><td className="px-4 py-8 text-center text-muted" colSpan={5}>Loading users…</td></tr> : users.length ? users.map((user) => (
                <tr key={user.id}>
                  <td className="px-4 py-3"><p className="font-semibold text-text">{user.display_name ?? "Unnamed trader"}</p><p className="font-mono text-xs text-muted-2">{user.email}</p></td>
                  <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted">${user.paper_balance.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted">{user.trade_count}</td>
                  <td className="px-4 py-3"><span className={user.is_suspended ? "rounded border border-danger/40 bg-danger-dim px-2 py-1 text-xs font-bold text-danger" : "rounded border border-primary/40 bg-primary-dim px-2 py-1 text-xs font-bold text-primary"}>{user.is_suspended ? "Suspended" : "Active"}</span></td>
                  <td className="px-4 py-3"><button type="button" disabled={actionId === user.id} onClick={() => void toggleSuspension(user)} className={user.is_suspended ? "min-h-9 rounded-lg border border-primary/40 px-3 text-xs font-bold text-primary hover:border-primary disabled:opacity-50" : "min-h-9 rounded-lg border border-danger/40 px-3 text-xs font-bold text-danger hover:border-danger disabled:opacity-50"}>{actionId === user.id ? "Saving…" : user.is_suspended ? "Unsuspend" : "Suspend"}</button></td>
                </tr>
              )) : <tr><td className="px-4 py-8 text-center text-muted" colSpan={5}>No users matched. Try a different search.</td></tr>}
            </tbody>
          </table>
        </section>
      )}
    </section>
  );
}
