"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";

type ToastTone = "success" | "error" | "info";
type Toast = { id: number; title: string; body?: string; tone: ToastTone };

type ToastContextValue = {
  toast: (t: { title: string; body?: string; tone?: ToastTone }) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) return { toast: () => undefined };
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback(
    ({ title, body, tone = "info" }: { title: string; body?: string; tone?: ToastTone }) => {
      const id = Date.now() + Math.random();
      setToasts((prev) => [...prev, { id, title, body, tone }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3600);
    },
    [],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* M-A11Y-03: announce toasts to assistive tech. Errors assert, others
          are polite so a screen reader isn't interrupted for a success note. */}
      <div
        className="pointer-events-none fixed right-4 top-20 z-50 flex w-[min(92vw,360px)] flex-col gap-2"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            aria-live={t.tone === "error" ? "assertive" : "polite"}
            className={cn(
              "pointer-events-auto animate-slide-in-right rounded-lg border bg-surface-2 p-3 shadow-lift",
              t.tone === "success" && "border-primary/40",
              t.tone === "error" && "border-danger/40",
              t.tone === "info" && "border-border-light",
            )}
          >
            <div className="flex items-start gap-2">
              <span
                className={cn(
                  "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                  t.tone === "success" && "bg-primary",
                  t.tone === "error" && "bg-danger",
                  t.tone === "info" && "bg-accent",
                )}
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-text">{t.title}</p>
                {typeof t.body === "string" && t.body ? (
                  <p className="mt-0.5 text-xs text-muted">{t.body}</p>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
