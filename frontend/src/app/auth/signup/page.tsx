"use client";

import Link from "next/link";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { cn } from "@/lib/cn";

export default function SignupPage() {
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agree, setAgree] = useState(false);

  const strength = scorePassword(password);
  const canSubmit = email.includes("@") && password.length >= 8 && password === confirm && agree;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    toast({
      title: "Account created",
      body: "Welcome to AlphaEdge — $100,000 paper balance granted.",
      tone: "success",
    });
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-2xl border border-border bg-surface p-6">
        <h1 className="text-2xl font-black text-text">Join AlphaEdge</h1>
        <p className="mt-1 text-sm text-muted">Start with $100,000 in paper money.</p>

        <form className="mt-6 space-y-4" onSubmit={submit}>
          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
              placeholder="you@example.com"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              placeholder="At least 8 characters"
            />
            <div className="mt-1.5 flex gap-1">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className={cn(
                    "h-1 flex-1 rounded-full transition",
                    i < strength
                      ? strength <= 1
                        ? "bg-danger"
                        : strength === 2
                          ? "bg-gold"
                          : "bg-primary"
                      : "bg-border-light",
                  )}
                />
              ))}
            </div>
          </Field>
          <Field label="Confirm password">
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="input"
              placeholder="Re-enter password"
            />
          </Field>

          <label className="flex items-start gap-2 text-xs text-muted">
            <input
              type="checkbox"
              checked={agree}
              onChange={(e) => setAgree(e.target.checked)}
              className="mt-0.5 accent-[#24C66D]"
            />
            I agree to the Terms and understand this is a paper-trading simulation.
          </label>

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-bold text-bg transition hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Create account
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link href="/auth/login" className="font-semibold text-accent hover:underline">
            Log in
          </Link>
        </p>
      </div>

      <style jsx>{`
        .input {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid #243039;
          background: #090c0f;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          color: #f2f7f3;
        }
        .input:focus {
          outline: none;
          border-color: #58e28c;
        }
      `}</style>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

function scorePassword(pw: string): number {
  let score = 0;
  if (pw.length >= 8) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw)) score += 1;
  if (/[^A-Za-z0-9]/.test(pw)) score += 1;
  return score;
}
