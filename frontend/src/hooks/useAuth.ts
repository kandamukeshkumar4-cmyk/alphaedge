"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { ACCESS_TOKEN_KEY } from "@/lib/portfolio-api";

export const USER_EMAIL_KEY = "alphaedge.userEmail";

export function saveAuthSession(accessToken: string, userEmail: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(USER_EMAIL_KEY, userEmail);
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
    const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    setToken(storedToken);
    setEmail(localStorage.getItem(USER_EMAIL_KEY));
    setIsReady(true);

    if (storedToken) {
      void refreshBalance();
    }
  }, [refreshBalance]);

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);
    setToken(null);
    setEmail(null);
    setPaperBalance(null);
    router.replace("/auth/login");
  }, [router]);

  return { token, email, paperBalance, logout, isReady, refreshBalance };
}
