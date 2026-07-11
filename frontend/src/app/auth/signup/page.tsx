"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { saveAuthSession } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { API_BASE, formatApiDetail } from "@/lib/alphaedge-api";

export default function SignupPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agree, setAgree] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const strength = scorePassword(password);
  const canSubmit = email.includes("@") && password.length >= 8 && password === confirm && agree;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // H-SEC-02: store the httpOnly session cookie the server sets.
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
        toast({
          title: "Signup failed",
          body: formatApiDetail(body.detail, "Unable to create account"),
          tone: "error",
        });
        return;
      }
      const body = (await response.json()) as { access_token: string };
      saveAuthSession(body.access_token, email);
      router.replace("/portfolio");
    } catch {
      toast({
        title: "Signup failed",
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
        <h1 className="text-2xl font-black text-text">Join AlphaEdge</h1>
        <p className="mt-1 text-sm text-muted">Start with $100,000 in paper money.</p>

        <form className="mt-6 space-y-4" onSubmit={submit}>
          <Field label="Email" htmlFor="signup-email">
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
              placeholder="you@example.com"
            />
          </Field>
          <Field label="Password" htmlFor="signup-password">
            <input
              id="signup-password"
              type="password"
              autoComplete="new-password"
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
          <Field label="Confirm password" htmlFor="signup-confirm">
            <input
              id="signup-confirm"
              type="password"
              autoComplete="new-password"
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
              className="mt-0.5 accent-[#14B8A6]"
            />
            I agree to the Terms and understand this is a paper-trading simulation.
          </label>

          <button
            type="submit"
            disabled={!canSubmit || submitting}
            className="w-full rounded-xl bg-accent py-2.5 text-sm font-bold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Creating account…" : "Create account"}
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
          border-radius: 0.625rem;
          border: 1px solid #243430;
          background: #0C1210;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          color: #F2F4F8;
        }
        .input:focus {
          outline: none;
          border-color: #14B8A6;
          box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.18);
        }
      `}</style>
    </main>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-semibold uppercase tracking-wider text-muted-2"
      >
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
