"use client";

import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { AdminNav } from "@/components/admin/AdminNav";
import { AdminKeyProvider } from "@/lib/admin-context";
import { readAdminApiKey, writeAdminApiKey } from "@/lib/admin-auth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState("");
  const [draftKey, setDraftKey] = useState("");
  const [ready, setReady] = useState(false);
  const [needsPrompt, setNeedsPrompt] = useState(false);

  useEffect(() => {
    const stored = readAdminApiKey();
    if (stored) {
      setApiKey(stored);
      setDraftKey(stored);
      setNeedsPrompt(false);
    } else {
      setNeedsPrompt(true);
    }
    setReady(true);
  }, []);

  function handleSaveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draftKey.trim();
    if (!trimmed) {
      return;
    }
    writeAdminApiKey(trimmed);
    setApiKey(trimmed);
    setNeedsPrompt(false);
  }

  if (!ready) {
    return null;
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row lg:px-8">
      <aside className="w-full shrink-0 lg:w-52">
        <AdminNav />
      </aside>
      <div className="min-w-0 flex-1 space-y-6">
        {needsPrompt ? (
          <section className="rounded-xl border border-border bg-surface p-5">
            <h1 className="text-xl font-semibold text-text">Admin API Key</h1>
            <p className="mt-2 text-sm text-muted">
              Enter the admin API key to access dashboard controls. It is stored in
              localStorage on this browser only.
            </p>
            <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={handleSaveKey}>
              <label className="sr-only" htmlFor="admin-api-key">
                Admin API key
              </label>
              <input
                id="admin-api-key"
                className="min-h-11 flex-1 rounded-xl border border-border bg-bg px-3 font-mono text-sm text-text outline-none transition focus:border-accent"
                type="password"
                autoComplete="off"
                placeholder="X-Admin-API-Key"
                value={draftKey}
                onChange={(event) => setDraftKey(event.target.value)}
              />
              <button
                className="min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
                disabled={!draftKey.trim()}
                type="submit"
              >
                Save Key
              </button>
            </form>
          </section>
        ) : (
          <div className="flex justify-end">
            <button
              className="text-xs font-semibold text-muted-2 underline-offset-2 hover:text-primary hover:underline"
              onClick={() => setNeedsPrompt(true)}
              type="button"
            >
              Change API key
            </button>
          </div>
        )}
        <AdminKeyProvider apiKey={apiKey}>{children}</AdminKeyProvider>
      </div>
    </div>
  );
}
