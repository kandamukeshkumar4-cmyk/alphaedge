"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { ACCESS_TOKEN_KEY } from "@/lib/portfolio-api";

export const USER_EMAIL_KEY = "alphaedge.userEmail";

// Same-tab auth sync: localStorage "storage" events only fire in OTHER tabs,
// so login/signup dispatch this event to update the persistent SiteHeader
// without a hard refresh.
export const AUTH_CHANGED_EVENT = "alphaedge:auth-changed";

function notifyAuthChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  }
}

export function saveAuthSession(accessToken: string, userEmail: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(USER_EMAIL_KEY, userEmail);
  notifyAuthChanged();
}

type MeResponse = {
  paper_balance: number;
};

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [paperBalance, setPaperBalance] = useState<number | null>(null);
  const [isReady, setIsReady] = useState(false);

  const refreshBalance = useCallback(async () => {
    const currentToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!currentToken) {
      setPaperBalance(null);
      return null;
    }

    const apiBase = API_BASE || "http://localhost:8000";
    const response = await fetch(`${apiBase}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${currentToken}` },
      cache: "no-store",
    });

    if (!response.ok) {
      setPaperBalance(null);
      return null;
    }

    const body = (await response.json()) as MeResponse;
    setPaperBalance(body.paper_balance);
    return body.paper_balance;
  }, []);

  useEffect(() => {
    const sync = () => {
      const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
      setToken(storedToken);
      setEmail(localStorage.getItem(USER_EMAIL_KEY));
      setIsReady(true);
      if (storedToken) {
        void refreshBalance();
      } else {
        setPaperBalance(null);
      }
    };

    sync();
    window.addEventListener(AUTH_CHANGED_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [refreshBalance]);

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    // H-SEC-02: also clear the httpOnly session cookie server-side (best-effort).
    const apiBase = API_BASE || "http://localhost:8000";
    void fetch(`${apiBase}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => undefined);
    setToken(null);
    setEmail(null);
    setPaperBalance(null);
    notifyAuthChanged();
    router.replace("/auth/login");
  }, [router]);

  return { token, email, paperBalance, logout, isReady, refreshBalance };
}
