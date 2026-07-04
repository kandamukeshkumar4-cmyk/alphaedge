"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { CloneBuilderWizard } from "@/components/clones/CloneBuilderWizard";

function NewClonePageInner() {
  const { token, isReady } = useAuth();

  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-1.5 text-xs text-muted" aria-label="Breadcrumb">
          <Link href="/clones" className="hover:text-text">
            Clones
          </Link>
          <span>/</span>
          <span className="text-text">New clone</span>
        </nav>

        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text">Build a clone</h1>
          <p className="mt-1 text-sm text-muted">
            Compose a paper-mode agent from the vetted node set. Takes about 1 minute.
          </p>
        </div>

        {/* Auth gate */}
        {isReady && !token && (
          <div className="rounded-xl border border-border bg-surface p-8 text-center">
            <p className="text-sm text-muted">
              Please{" "}
              <Link href="/auth/login" className="font-semibold text-accent underline">
                log in
              </Link>{" "}
              to build clones.
            </p>
          </div>
        )}

        {/* Loading auth */}
        {!isReady && (
          <div className="h-64 animate-pulse rounded-xl bg-surface" />
        )}

        {/* Wizard */}
        {isReady && token && <CloneBuilderWizard token={token} />}
      </div>
    </main>
  );
}

export default function NewClonePage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-bg">
          <div className="mx-auto max-w-2xl px-4 py-8">
            <div className="h-8 w-48 animate-pulse rounded bg-surface" />
          </div>
        </main>
      }
    >
      <NewClonePageInner />
    </Suspense>
  );
}
