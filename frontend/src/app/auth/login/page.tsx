"use client";

import Link from "next/link";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";

export default function LoginPage() {
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    toast({ title: "Logged in", body: "Welcome back to AlphaEdge.", tone: "success" });
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-2xl border border-border bg-surface p-6">
        <h1 className="text-2xl font-black text-text">Welcome back</h1>
        <p className="mt-1 text-sm text-muted">Log in to your paper-trading account.</p>

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
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-bold text-white transition hover:bg-accent"
          >
            Log in
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
