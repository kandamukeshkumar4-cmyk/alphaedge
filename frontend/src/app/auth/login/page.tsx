"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { saveAuthSession } from "@/hooks/useAuth";
import { API_BASE, formatApiDetail } from "@/lib/alphaedge-api";

export default function LoginPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
        toast({
          title: "Login failed",
          body: formatApiDetail(body.detail, "Invalid email or password"),
          tone: "error",
        });
        return;
      }
      const body = (await response.json()) as { access_token: string };
      saveAuthSession(body.access_token, email);
      router.replace("/signals");
    } catch {
      toast({
        title: "Login failed",
        body: "Unable to reach the server.",
        tone: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-2xl border border-border bg-surface p-6">
        <h1 className="text-2xl font-black text-text">Welcome back</h1>
        <p className="mt-1 text-sm text-muted">Log in to save research preferences and history.</p>

        <form className="mt-6 space-y-4" onSubmit={submit}>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
              placeholder="you@example.com"
              required
            />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
                Password
              </label>
              <button type="button" className="text-[11px] text-accent hover:underline">
                Forgot?
              </button>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
              placeholder="Your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-accent py-2.5 text-sm font-bold text-white transition hover:brightness-110 disabled:cursor-wait disabled:opacity-50"
          >
            {submitting ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted">
          Need an account?{" "}
          <Link href="/auth/signup" className="font-semibold text-accent hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </main>
  );
}
